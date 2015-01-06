"""%prog [-p|--props-file] [-r|--rev revision] [-b|--branch branch]
         [-s|--shared-dir shared_dir] [--check-outgoing] repo [dest]

Tool to do safe operations with hg.

revision/branch on commandline will override those in props-file"""

# Import snippet to find tools lib
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/python"))

from util.hg import mercurial, out, remove_path

def main():
    import argparse
    import logging

    parser = argparse.ArgumentParser(description='Tool to do safe operations with hg.')

    parser.add_argument(
        "-v", "--verbose", dest="loglevel", action="store_const",
        const=logging.DEBUG, help="verbose logging",
        default=logging.INFO)

    parser.add_argument(
        "-r", "--rev", dest="revision", help="which revision to update to",
        default=os.environ.get('HG_REV'))

    parser.add_argument(
        "-b", "--branch", dest="branch", help="which branch to update to",
        default=os.environ.get('HG_BRANCH', None))

    parser.add_argument(
        "-p", "--props-file", dest="propsfile",
        help="build json file containing revision information",
        default=os.environ.get('PROPERTIES_FILE'))

    parser.add_argument(
        "-s", "--shared-dir", dest="shared_dir",
        help="clone to a shared directory",
        default=os.environ.get('HG_SHARE_BASE_DIR'))

    parser.add_argument(
        "--check-outgoing", dest="outgoing", action="store_true",
        help="check for and clobber outgoing changesets",
        default=False)

    parser.add_argument(
        "--clone-by-revision", dest="clone_by_rev", action="store_true",
        help="do initial clone with -r <rev> instead of cloning the entire repo. "
             "This is slower but is useful when cloning repositories with many "
             "heads which may timeout otherwise.",
        default=False)

    parser.add_argument(
        "--mirror", dest="mirrors", action="append",
        help="add a mirror to try cloning/pulling from before repo",
        default=None)

    parser.add_argument(
        "--bundle", dest="bundles", action="append",
        help="add a bundle to try downloading/unbundling from before doing a full clone",
        default=None)

    parser.add_argument(
        "--purge", dest="auto_purge", action="store_true",
        help="Purge the destination directory (if it exists).",
        default=False)

    parser.add_argument(
        "--dest", dest="dest", action="store",
        help="Destination path.",
        default=None)

    parser.add_argument(
        "--repo", dest="repo", action="store",
        help="Repo path.", required=True,
        default=None)


    options = parser.parse_args()

    if options.repo is None:
        parser.error("No repo argument specified.")

    if options.dest is None:
        options.dest = os.path.basename(options.repo)

    logging.basicConfig(level=options.loglevel, format="%(message)s")

    # Parse propsfile
    if options.propsfile:
        try:
            import json
        except ImportError:
            import simplejson as json
        js = json.load(open(options.propsfile))
        if options.revision is None:
            options.revision = js['sourcestamp']['revision']
        if options.branch is None:
            options.branch = js['sourcestamp']['branch']

    # look for and clobber outgoing changesets
    if options.outgoing:
        if out(options.dest, options.repo):
            remove_path(options.dest)
        if options.shared_dir and out(options.shared_dir, options.repo):
            remove_path(options.shared_dir)

    got_revision = mercurial(options.repo, options.dest, options.branch, options.revision,
                             shareBase=options.shared_dir,
                             clone_by_rev=options.clone_by_rev,
                             mirrors=options.mirrors,
                             bundles=options.bundles,
                             autoPurge=options.auto_purge)

    print "Got revision %s" % got_revision


if __name__ == '__main__':
    main()

