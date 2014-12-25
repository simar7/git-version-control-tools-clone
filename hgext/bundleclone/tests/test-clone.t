  $ cat >> $HGRCPATH << EOF
  > [extensions]
  > bundleclone = $TESTDIR/hgext/bundleclone
  > EOF

  $ hg init server
  $ cd server
  $ touch foo
  $ hg commit -A -m 'add foo'
  adding foo
  $ touch bar
  $ hg commit -A -m 'add bar'
  adding bar

  $ hg serve -d -p $HGPORT --pid-file hg.pid
  $ cat hg.pid >> $DAEMON_PIDS
  $ cd ..

Clone with no available bundles falls back to regular behavior

  $ hg -v clone http://localhost:$HGPORT no-manifest-file
  no bundles available; using normal clone
  requesting all changes
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  updating to branch default
  resolving manifests
  getting bar
  getting foo
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

Empty bundle manifest file

  $ touch server/.hg/bundleclone.manifest
  $ hg -v clone http://localhost:$HGPORT empty-manifest-file
  no bundles available; using normal clone
  requesting all changes
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  updating to branch default
  resolving manifests
  getting bar
  getting foo
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

Manifest file with invalid URL

  $ echo 'http://does.not.exist/bundle.hg' >> server/.hg/bundleclone.manifest
  $ hg clone http://localhost:$HGPORT invalid-bundle-url
  downloading bundle http://does.not.exist/bundle.hg
  error fetching bundle; using normal clone: [Errno * (glob)
  requesting all changes
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

Server is not running

  $ echo "http://localhost:$HGPORT1/bundle.hg" > server/.hg/bundleclone.manifest
  $ hg clone http://localhost:$HGPORT server-not-runner
  downloading bundle http://localhost:$HGPORT1/bundle.hg
  error fetching bundle; using normal clone: [Errno *] Connection refused (glob)
  requesting all changes
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

Server returns 404

  $ python $TESTDIR/hgext/bundleclone/tests/httpserver.py $HGPORT1 2> server.log &
  $ while [ ! -f listening ]; do sleep 0; done
  $ hg clone http://localhost:$HGPORT server-404
  downloading bundle http://localhost:$HGPORT1/bundle.hg
  HTTP error fetching bundle; using normal clone: HTTP Error 404: File not found
  requesting all changes
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

Bundle with partial content works

  $ hg -R server bundle --type gzip --base null -r 53245c60e682 53245c60e682.hg
  1 changesets found

  $ echo "http://localhost:$HGPORT1/53245c60e682.hg" > server/.hg/bundleclone.manifest
  $ python $TESTDIR/hgext/bundleclone/tests/httpserver.py $HGPORT1 2> server.log &
  $ while [ ! -f listening ]; do sleep 0; done
  $ hg clone http://localhost:$HGPORT partial-bundle
  downloading bundle http://localhost:$HGPORT1/53245c60e682.hg
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files
  finishing applying bundle; pulling
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

Bundle with full content works

  $ hg -R server bundle --type gzip --base null -r tip aaff8d2ffbbf.hg
  2 changesets found

  $ echo "http://localhost:$HGPORT1/aaff8d2ffbbf.hg" > server/.hg/bundleclone.manifest
  $ python $TESTDIR/hgext/bundleclone/tests/httpserver.py $HGPORT1 2> server.log &
  $ while [ ! -f listening ]; do sleep 0; done
  $ hg clone http://localhost:$HGPORT full-bundle
  downloading bundle http://localhost:$HGPORT1/aaff8d2ffbbf.hg
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  finishing applying bundle; pulling
  searching for changes
  no changes found
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

Clone will copy manifest from server

  $ python $TESTDIR/hgext/bundleclone/tests/httpserver.py $HGPORT1 2> server.log &
  $ while [ ! -f listening ]; do sleep 0; done
  $ hg --config bundleclone.pullmanifest=True clone http://localhost:$HGPORT clone-copy-manifest
  downloading bundle http://localhost:$HGPORT1/aaff8d2ffbbf.hg
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  finishing applying bundle; pulling
  searching for changes
  no changes found
  pulling bundleclone manifest
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cat clone-copy-manifest/.hg/bundleclone.manifest
  http://localhost:$HGPORT1/aaff8d2ffbbf.hg

Pull will copy manifest from server

  $ python $TESTDIR/hgext/bundleclone/tests/httpserver.py $HGPORT1 2> server.log &
  $ while [ ! -f listening ]; do sleep 0; done
  $ hg clone http://localhost:$HGPORT pull-copy-manifest
  downloading bundle http://localhost:$HGPORT1/aaff8d2ffbbf.hg
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files
  finishing applying bundle; pulling
  searching for changes
  no changes found
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ hg -R pull-copy-manifest --config bundleclone.pullmanifest=True pull
  pulling from http://localhost:$HGPORT/
  searching for changes
  no changes found
  pulling bundleclone manifest
  $ cat clone-copy-manifest/.hg/bundleclone.manifest
  http://localhost:$HGPORT1/aaff8d2ffbbf.hg
