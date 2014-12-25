# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

"""Post changeset URLs to Bugzilla.

This extension will post the URLs of pushed changesets to Bugzilla
automatically.

To use, activate this extension by adding the following to your
hgrc:

    [extensions]
    bzpost = /path/to/version-control-tools/hgext/bzpost

You will also want to define your Bugzilla credentials in your hgrc to
avoid prompting:

    [bugzilla]
    username = foo@example.com
    password = password

After successfully pushing to a known Firefox repository, this extension
will add a comment to the first referenced bug in all pushed changesets
containing the URLs of the pushed changesets.

Limitations
===========

We currently only post comments to integration/non-release repositories.
This is because pushes to release repositories involve updating other
Bugzilla fields. This extension could support these someday - it just
doesn't yet.

User Repositories
=================

By default, we do not post pushes to user repositories. To enable posting
to user repositories, set the following in your hgrc:

    [bzpost]
    updateuserrepo = True
"""

import os

from mercurial import demandimport
from mercurial import exchange
from mercurial import extensions
from mercurial import phases
from mercurial.i18n import _

OUR_DIR = os.path.dirname(__file__)
execfile(os.path.join(OUR_DIR, '..', 'bootstrap.py'))

# requests doesn't like lazy module loading.
demandimport.disable()
from bugsy import Bugsy
demandimport.enable()
from mozautomation.commitparser import parse_bugs
from mozautomation import repository
from mozhg.auth import getbugzillaauth

testedwith = '3.0 3.1 3.2'
buglink = 'https://bugzilla.mozilla.org/enter_bug.cgi?product=Developer%20Services&component=Mercurial:%20bzpost'


def wrappedpushbookmark(orig, pushop):
    result = orig(pushop)

    # pushop.ret was renamed to pushop.cgresult in Mercurial 3.2. We can drop
    # this branch once we drop <3.2 support.
    if hasattr(pushop, 'cgresult'):
        origresult = pushop.cgresult
    else:
        origresult = pushop.ret

    # Don't do anything if error from push.
    if not origresult:
        return result

    remoteurl = pushop.remote.url()
    tree = repository.resolve_uri_to_tree(remoteurl)
    # We don't support release trees (yet) because they have special flags
    # that need to get updated.
    if tree and tree in repository.RELEASE_TREES:
        return result

    ui = pushop.ui

    if tree:
        baseuri = repository.resolve_trees_to_uris([tree])[0][1]
        assert baseuri
    else:
        # This isn't a known Firefox tree. Fall back to resolving URLs by
        # hostname.

        # Only attend Mozilla's server.
        if not updateunknown(remoteurl, repository.BASE_WRITE_URI, ui):
            return result

        baseuri = remoteurl.replace(repository.BASE_WRITE_URI, repository.BASE_READ_URI).rstrip('/')

    bugsmap = {}
    lastbug = None
    lastnode = None

    for node in pushop.outgoing.missing:
        ctx = pushop.repo[node]

        # Don't do merge commits.
        if len(ctx.parents()) > 1:
            continue

        # Our bug parser is buggy for Gaia bump commit messages.
        if '<release+b2gbumper@mozilla.com>' in ctx.user():
            continue

        # Pushing to Try (and possibly other repos) could push unrelated
        # changesets that have been pushed to an official tree but aren't yet
        # on this specific remote. We use the phase information as a proxy
        # for "already pushed" and prune public changesets from consideration.
        if tree == 'try' and ctx.phase() == phases.public:
            continue

        bugs = parse_bugs(ctx.description())

        if not bugs:
            continue

        bugsmap.setdefault(bugs[0], []).append(ctx.hex()[0:12])
        lastbug = bugs[0]
        lastnode = ctx.hex()[0:12]

    if not bugsmap:
        return result

    bzauth = getbugzillaauth(ui)
    if not bzauth or not bzauth.username or not bzauth.password:
        return result

    bzurl = ui.config('bugzilla', 'url', 'https://bugzilla.mozilla.org/rest')

    bugsy = Bugsy(username=bzauth.username, password=bzauth.password,
            bugzilla_url=bzurl)

    # If this is a try push, we paste the Treeherder link for the tip commit, because
    # the per-commit URLs don't have much value.
    # TODO roll this into normal pushing so we get a Treeherder link in bugs as well.
    if tree == 'try' and lastbug:
        treeherderurl = repository.treeherder_url(tree, lastnode)

        bug = bugsy.get(lastbug)
        comments = bug.get_comments()
        for comment in comments:
            if treeherderurl in comment.text:
                return result

        ui.write(_('recording Treeherder push in bug %s\n') % lastbug)
        bug.add_comment(treeherderurl)
        return result

    for bugnumber, nodes in bugsmap.items():
        bug = bugsy.get(bugnumber)

        comments = bug.get_comments()
        missing_nodes = []

        # When testing whether this changeset URL is referenced in a
        # comment, we only need to test for the node fragment. The
        # important side-effect is that each unique node for a changeset
        # is recorded in the bug.
        for node in nodes:
            if not any(node in comment.text for comment in comments):
                missing_nodes.append(node)

        if not missing_nodes:
            ui.write(_('bug %s already knows about pushed changesets\n') %
                bugnumber)
            continue

        lines = ['%s/rev/%s' % (baseuri, node) for node in missing_nodes]

        comment = '\n'.join(lines)

        ui.write(_('recording push in bug %s\n') % bugnumber)
        bug.add_comment(comment)

    return result


def extsetup(ui):
    extensions.wrapfunction(exchange, '_pushbookmark', wrappedpushbookmark)


def updateunknown(remoteurl, base, ui):
    if not remoteurl.startswith(base):
        return False

    return not remoteurl.startswith(base + 'users/') or ui.configbool('bzpost', 'updateuserrepo', False)
