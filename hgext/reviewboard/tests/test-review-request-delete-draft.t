#require docker

  $ . $TESTDIR/hgext/reviewboard/tests/helpers.sh
  $ commonenv rb-test-draft-delete

  $ bugzilla create-user submitter@example.com password 'Dummy Submitter'
  created user 2
  $ exportbzauth submitter@example.com password
  $ bugzilla create-bug TestProduct TestComponent 'Initial Bug'

  $ cd client
  $ echo foo > foo
  $ hg commit -A -m 'root commit'
  adding foo
  $ hg phase --public -r .

  $ echo foo1 > foo
  $ hg commit -m 'Bug 1 - Initial commit'
  $ hg --config bugzilla.username=submitter@example.com push
  pushing to ssh://user@dummy/$TESTTMP/server
  searching for changes
  remote: adding changesets
  remote: adding manifests
  remote: adding file changes
  remote: added 2 changesets with 2 changes to 1 files
  submitting 1 changesets for review
  
  changeset:  1:8c2be86a13c9
  summary:    Bug 1 - Initial commit
  review:     http://localhost:$HGPORT1/r/2 (pending)
  
  review id:  bz://1/mynick
  review url: http://localhost:$HGPORT1/r/1 (pending)
  (visit review url to publish this review request so others can see it)

Now publish the review and create a new draft

  $ rbmanage publish $HGPORT1 1
  $ echo foo3 > foo
  $ hg commit --amend > /dev/null
  $ hg --config bugzilla.username=submitter@example.com push
  pushing to ssh://user@dummy/$TESTTMP/server
  searching for changes
  remote: adding changesets
  remote: adding manifests
  remote: adding file changes
  remote: added 1 changesets with 1 changes to 1 files (+1 heads)
  submitting 1 changesets for review
  
  changeset:  1:c1eb96801052
  summary:    Bug 1 - Initial commit
  review:     http://localhost:$HGPORT1/r/2 (pending)
  
  review id:  bz://1/mynick
  review url: http://localhost:$HGPORT1/r/1 (pending)
  (visit review url to publish this review request so others can see it)

We should have a disagreement between published and draft

  $ rbmanage dumpreview $HGPORT1 1
  Review: 1
    Status: pending
    Public: True
    Bugs: 1
    Commit ID: bz://1/mynick
    Summary: bz://1/mynick
    Description:
      /r/2 - Bug 1 - Initial commit
      
      Pull down this commit:
      
      hg pull -r 8c2be86a13c96ceb24c3eaa50cc6ef214c656d50 http://localhost:$HGPORT/
      
    Extra:
      p2rb: True
      p2rb.commits: [["8c2be86a13c96ceb24c3eaa50cc6ef214c656d50", "2"]]
      p2rb.discard_on_publish_rids: []
      p2rb.identifier: bz://1/mynick
      p2rb.is_squashed: True
      p2rb.unpublished_rids: []
  Draft: 1
    Bugs: 1
    Commit ID: bz://1/mynick
    Summary: bz://1/mynick
    Description:
      /r/2 - Bug 1 - Initial commit
      
      Pull down this commit:
      
      hg pull -r c1eb968010521027f51dd6d901d92dc44bfdcd5d http://localhost:$HGPORT/
      
    Extra:
      p2rb: True
      p2rb.commits: [["c1eb968010521027f51dd6d901d92dc44bfdcd5d", "2"]]
      p2rb.discard_on_publish_rids: []
      p2rb.identifier: bz://1/mynick
      p2rb.is_squashed: True
      p2rb.unpublished_rids: []
  Diff: 3
    Revision: 2
  diff -r 3a9f6899ef84 -r c1eb96801052 foo
  --- a/foo	Thu Jan 01 00:00:00 1970 +0000
  +++ b/foo	Thu Jan 01 00:00:00 1970 +0000
  @@ -1,1 +1,1 @@
  -foo
  +foo3
  

  $ rbmanage dumpreview $HGPORT1 2
  Review: 2
    Status: pending
    Public: True
    Bugs: 1
    Commit ID: None
    Summary: Bug 1 - Initial commit
    Description:
      Bug 1 - Initial commit
    Extra:
      p2rb: True
      p2rb.commit_id: 8c2be86a13c96ceb24c3eaa50cc6ef214c656d50
      p2rb.identifier: bz://1/mynick
      p2rb.is_squashed: False
  Draft: 2
    Bugs: 1
    Commit ID: None
    Summary: Bug 1 - Initial commit
    Description:
      Bug 1 - Initial commit
    Extra:
      p2rb: True
      p2rb.commit_id: c1eb968010521027f51dd6d901d92dc44bfdcd5d
      p2rb.identifier: bz://1/mynick
      p2rb.is_squashed: False
  Diff: 4
    Revision: 2
  diff -r 3a9f6899ef84 -r c1eb96801052 foo
  --- a/foo	Thu Jan 01 00:00:00 1970 +0000
  +++ b/foo	Thu Jan 01 00:00:00 1970 +0000
  @@ -1,1 +1,1 @@
  -foo
  +foo3
  

Discarding the parent review request draft should discard draft on children

  $ rbmanage discard-review-request-draft $HGPORT1 1
  Discarded draft for review request 1

  $ rbmanage dumpreview $HGPORT1 1
  Review: 1
    Status: pending
    Public: True
    Bugs: 1
    Commit ID: bz://1/mynick
    Summary: bz://1/mynick
    Description:
      /r/2 - Bug 1 - Initial commit
      
      Pull down this commit:
      
      hg pull -r 8c2be86a13c96ceb24c3eaa50cc6ef214c656d50 http://localhost:$HGPORT/
      
    Extra:
      p2rb: True
      p2rb.commits: [["8c2be86a13c96ceb24c3eaa50cc6ef214c656d50", "2"]]
      p2rb.discard_on_publish_rids: []
      p2rb.identifier: bz://1/mynick
      p2rb.is_squashed: True
      p2rb.unpublished_rids: []

  $ rbmanage dumpreview $HGPORT1 2
  Review: 2
    Status: pending
    Public: True
    Bugs: 1
    Commit ID: None
    Summary: Bug 1 - Initial commit
    Description:
      Bug 1 - Initial commit
    Extra:
      p2rb: True
      p2rb.commit_id: 8c2be86a13c96ceb24c3eaa50cc6ef214c656d50
      p2rb.identifier: bz://1/mynick
      p2rb.is_squashed: False

  $ cd ..

Cleanup

  $ rbmanage stop rbserver
  $ dockercontrol stop-bmo rb-test-draft-delete > /dev/null
