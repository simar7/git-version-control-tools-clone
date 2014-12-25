#!/usr/bin/python
# Copyright (C) 2011 Mozilla Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import random
import os
from lockfiles import getlock, unlock
from subprocess import Popen, PIPE, STDOUT
from time import sleep
import urllib
import shlex
import yaml
import signal

random.seed()
# Set by signal handlers:
exit_requested = False

class MirrorJob:
    def __init__(self, host, path, config, fh, verbose=False):
        self.host = host
        self.path = path
        self.config = config
        self.verbose = verbose
        self.child = None
        self.command = self.make_command()

    # Given a host and path to clone, return the command used to trigger a
    # pull.
    def make_command(self):
        ssh_id = get_config_key(self.config, ['daemon', 'ssh-id'])
        if ssh_id:
            id_str = "-i%s" % ssh_id
        else:
            id_str = ""
        return "/usr/bin/ssh -n %s %s hg pull %s" % (id_str, self.host, self.path)

    # Spawn a child process for the given command
    def spawn_child(self):
        self.child = Popen(shlex.split(self.command), stdout=PIPE, stderr=STDOUT)
        if self.verbose:
            print "Spawned [%s] as pid %i" % (self.command, self.child.pid)
        
# Spawn subprocesses for each of the given commands, up to
# max_children.  Returns two lists of MirrorJob objects, one
# containing the running jobs, and one containing jobs that
# were not spawned for some reason.
def spawn_children(commands, running_jobs, max_children, verbose=False):
    procs = running_jobs
    skipped_jobs = []
    # while len(procs) < max_children and len(commands) > 0:
    for i in range(0, len(commands)):
        if(len(procs) >= max_children or
           check_dup_jobs(commands[i], running_jobs)):
               skipped_jobs.append(commands[i])
        else:
            commands[i].spawn_child()
            procs.append(commands[i])
    if verbose:
        print "Spawned %i processes, %i pending" % ( len(procs), len(skipped_jobs) )
    return (procs, skipped_jobs)

# Check to see if a running job already exists for the
# given host/repo pair.  Returns boolean
def check_dup_jobs(job, running_jobs):
    for cur in running_jobs:
        if(job.host == cur.host and
           job.path == cur.path):
            return True
    return False

# check each child process, gather any output, 
def reap_children(jobs, verbose=False):
    if verbose:
        print "in reap_children, nchildren = %i" % len(jobs)
    for job in jobs:
        output = None
        rcode = job.child.poll()
        if(rcode != None):
            output = job.child.communicate()
            if(rcode == 0):
                print "Successfully pushed %s to %s" % (job.path, job.host)
            else:
                print "ERROR: Push of %s to %s returned %i" % (job.path, job.host, rcode)
            if verbose:
                if output:
                    print "Output: %s" % output[0]
            jobs.remove(job)
    return jobs

# Different repositories might get mirrored to different hosts.  For a
# given repository, return a list of hosts that should receive push
# notifications.
def get_hosts_for_repo(repo, config):
    hosts = get_config_key(config, [repo, 'mirrors'])
    if hosts:
        return hosts
    else:
        return []

# Look for repositories that have been updated. Return a list of
# commands to run to notify the appropriate mirrors that they should
# update.
def get_more_commands(directory, config, verbose=False):
    cmnds = []
    if verbose:
        print "Looking for files in %s" % directory
    dirh = os.listdir(directory)
    for f in dirh:
        fullpath = "%s/%s" % (directory, f)
        lck = getlock(fullpath, verbose)
        if lck:
            fh = file(fullpath, 'r')
            os.unlink(fullpath)
            unlock(fullpath, lck, verbose)
            for host in get_hosts_for_repo(urllib.unquote(f), config):
                cmnds.append(MirrorJob(host, 
                                       urllib.unquote(f), 
                                       config,
                                       fh))
                if verbose:
                    print "Appended a command to the queue. ",
                    print "qlen: %i" % len(cmnds)
            fh.close()
        else:
            print "Couldn't lock %s" % fullpath
    return cmnds

# Read the config file. Returns a dictionary object, which may be empty
def read_config(configfile):
    try:
        f = file(configfile)
    except IOError, e:
        print "WARNING: mirror config %s: %s" % (configfile, e)
        return {}
    y = yaml.load(f)
    f.close()
    if y == None:
        y = {}
    return y

# get the config value specified by the given path array.
# Returns the requested value or None if it's not present.
def get_config_key(config, path):
    try:
        if len(path) == 0:
            return config
        current = path[0]
        del path[0]
        return get_config_key(config[current], path)
    except KeyError:
        return None

def main():
    global exit_requested
    running_jobs = []
    pending_jobs = []
    configfile = "/etc/mercurial/repo-mirrors.yaml"
    cfg = read_config(configfile)

    # Read some global values from the config file, filling in
    # some sane-ish defaults for missing values.
    verbose = get_config_key(cfg, ['daemon', 'verbose'])
    dir = get_config_key(cfg, ['daemon', 'watch-dir'])
    if not dir:
        dir = "/dev/shm/hg_pushes"
    maxchildren = get_config_key(cfg, ['daemon', 'maxchildren'])
    if not maxchildren:
        maxchildren = 3

    def sighandler(signum, frame):
        print "Caught signal %i" % signum
        global exit_requested
        exit_requested = True
        if(len(running_jobs) > 0 or len(pending_jobs) > 0):
            print "WARNING: There are %i running jobs and %i queued jobs" % (len(running_jobs), 
                                                                             len(pending_jobs))
            print "WARNING: To ensure a clean exit, will terminate after the queue is emptied"

    signal.signal(signal.SIGTERM, sighandler)

    while True:
        if not exit_requested:
            pending_jobs = pending_jobs + get_more_commands(dir, cfg, verbose)
        running_jobs = reap_children(running_jobs, verbose)
        (running_jobs, pending_jobs) = spawn_children(pending_jobs, running_jobs,
                                                      maxchildren - len(running_jobs), 
                                                      verbose)
        if(exit_requested and
           len(running_jobs) == 0 and 
           len(pending_jobs) == 0):
            break
        sleep(1)
    print "Exiting..."

if __name__ == "__main__":
    main()

