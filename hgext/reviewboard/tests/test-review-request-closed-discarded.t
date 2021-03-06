#require docker
  $ . $TESTDIR/hgext/reviewboard/tests/helpers.sh
  $ commonenv rb-test-review-request-closed-discarded
  $ bugzilla create-bug-range TestProduct TestComponent 123
  created 123 bugs

  $ cd client
  $ echo 'foo0' > foo
  $ hg commit -A -m 'root commit'
  adding foo
  $ hg push --noreview
  pushing to ssh://user@dummy/$TESTTMP/server
  searching for changes
  remote: adding changesets
  remote: adding manifests
  remote: adding file changes
  remote: added 1 changesets with 1 changes to 1 files
  $ hg phase --public -r .

  $ echo 'foo1' > foo
  $ hg commit -m 'Bug 123 - Foo 1'
  $ echo 'foo2' > foo
  $ hg commit -m 'Bug 123 - Foo 2'
  $ hg push
  pushing to ssh://user@dummy/$TESTTMP/server
  searching for changes
  remote: adding changesets
  remote: adding manifests
  remote: adding file changes
  remote: added 2 changesets with 2 changes to 1 files
  submitting 2 changesets for review
  
  changeset:  1:bb41178fa30c
  summary:    Bug 123 - Foo 1
  review:     http://localhost:$HGPORT1/r/2 (pending)
  
  changeset:  2:9d24f6cb513e
  summary:    Bug 123 - Foo 2
  review:     http://localhost:$HGPORT1/r/3 (pending)
  
  review id:  bz://123/mynick
  review url: http://localhost:$HGPORT1/r/1 (pending)
  (visit review url to publish this review request so others can see it)

  $ rbmanage publish $HGPORT1 1
  $ bugzilla dump-bug 123
  Bug 123:
    attachments:
    - attacher: admin@example.com
      content_type: text/x-review-board-request
      data: http://example.com/r/1/
      description: 'MozReview Request: bz://123/mynick'
      flags: []
      id: 1
      is_obsolete: false
      summary: 'MozReview Request: bz://123/mynick'
    comments:
    - author: admin@example.com
      id: 123
      tags: []
      text: ''
    - author: admin@example.com
      id: 124
      tags: []
      text: 'Created attachment 1
  
        MozReview Request: bz://123/mynick
  
  
        /r/2 - Bug 123 - Foo 1
  
        /r/3 - Bug 123 - Foo 2
  
  
        Pull down these commits:
  
  
        hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/'
    summary: Range 123

Close the squashed review request as discarded, which should close all of the
child review requests.

  $ rbmanage closediscarded $HGPORT1 1

Squashed review request with ID 1 should be closed as discarded and have
no Commit ID set.

  $ rbmanage dumpreview $HGPORT1 1
  Review: 1
    Status: discarded
    Public: True
    Bugs: 123
    Commit ID: None
    Summary: bz://123/mynick
    Description:
      /r/2 - Bug 123 - Foo 1
      /r/3 - Bug 123 - Foo 2
      
      Pull down these commits:
      
      hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/
      
    Extra:
      p2rb: True
      p2rb.commits: [["bb41178fa30c323500834d0368774ef4ed412d7b", "2"], ["9d24f6cb513e7a5b4e19b684e863304b47dfe4c9", "3"]]
      p2rb.discard_on_publish_rids: []
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: True
      p2rb.unpublished_rids: []

Child review request with ID 2 should be closed as discarded...

  $ rbmanage dumpreview $HGPORT1 2
  Review: 2
    Status: discarded
    Public: True
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 1
    Description:
      Bug 123 - Foo 1
    Extra:
      p2rb: True
      p2rb.commit_id: bb41178fa30c323500834d0368774ef4ed412d7b
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False

Child review request with ID 3 should be closed as discarded...

  $ rbmanage dumpreview $HGPORT1 3
  Review: 3
    Status: discarded
    Public: True
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 2
    Description:
      Bug 123 - Foo 2
    Extra:
      p2rb: True
      p2rb.commit_id: 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False

The review attachment should be marked as obsolete

  $ bugzilla dump-bug 123
  Bug 123:
    attachments:
    - attacher: admin@example.com
      content_type: text/x-review-board-request
      data: http://example.com/r/1/
      description: 'MozReview Request: bz://123/mynick'
      flags: []
      id: 1
      is_obsolete: true
      summary: 'MozReview Request: bz://123/mynick'
    comments:
    - author: admin@example.com
      id: 123
      tags: []
      text: ''
    - author: admin@example.com
      id: 124
      tags: []
      text: 'Created attachment 1
  
        MozReview Request: bz://123/mynick
  
  
        /r/2 - Bug 123 - Foo 1
  
        /r/3 - Bug 123 - Foo 2
  
  
        Pull down these commits:
  
  
        hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/'
    summary: Range 123

Re-opening the parent review request should re-open all of the children,
and they should be non-public.

  $ rbmanage reopen $HGPORT1 1

Squashed review request with ID 1 should be re-opened and have its
Commit ID re-instated.

  $ rbmanage dumpreview $HGPORT1 1
  Review: 1
    Status: pending
    Public: False
    Bugs: 123
    Commit ID: bz://123/mynick
    Summary: bz://123/mynick
    Description:
      /r/2 - Bug 123 - Foo 1
      /r/3 - Bug 123 - Foo 2
      
      Pull down these commits:
      
      hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/
      
    Extra:
      p2rb: True
      p2rb.commits: [["bb41178fa30c323500834d0368774ef4ed412d7b", "2"], ["9d24f6cb513e7a5b4e19b684e863304b47dfe4c9", "3"]]
      p2rb.discard_on_publish_rids: []
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: True
      p2rb.unpublished_rids: []
  Draft: 1
    Bugs: 123
    Commit ID: bz://123/mynick
    Summary: bz://123/mynick
    Description:
      /r/2 - Bug 123 - Foo 1
      /r/3 - Bug 123 - Foo 2
      
      Pull down these commits:
      
      hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/
      
    Extra:
      p2rb: True
      p2rb.commits: [["bb41178fa30c323500834d0368774ef4ed412d7b", "2"], ["9d24f6cb513e7a5b4e19b684e863304b47dfe4c9", "3"]]
      p2rb.discard_on_publish_rids: []
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: True
      p2rb.unpublished_rids: []

Child review request with ID 2 should be re-opened...

  $ rbmanage dumpreview $HGPORT1 2
  Review: 2
    Status: pending
    Public: False
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 1
    Description:
      Bug 123 - Foo 1
    Extra:
      p2rb: True
      p2rb.commit_id: bb41178fa30c323500834d0368774ef4ed412d7b
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False
  Draft: 2
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 1
    Description:
      Bug 123 - Foo 1
    Extra:
      p2rb: True
      p2rb.commit_id: bb41178fa30c323500834d0368774ef4ed412d7b
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False

Child review request with ID 3 should be re-opened...

  $ rbmanage dumpreview $HGPORT1 3
  Review: 3
    Status: pending
    Public: False
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 2
    Description:
      Bug 123 - Foo 2
    Extra:
      p2rb: True
      p2rb.commit_id: 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False
  Draft: 3
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 2
    Description:
      Bug 123 - Foo 2
    Extra:
      p2rb: True
      p2rb.commit_id: 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False

There should still not be a visible attachment on the bug

  $ bugzilla dump-bug 123
  Bug 123:
    attachments:
    - attacher: admin@example.com
      content_type: text/x-review-board-request
      data: http://example.com/r/1/
      description: 'MozReview Request: bz://123/mynick'
      flags: []
      id: 1
      is_obsolete: true
      summary: 'MozReview Request: bz://123/mynick'
    comments:
    - author: admin@example.com
      id: 123
      tags: []
      text: ''
    - author: admin@example.com
      id: 124
      tags: []
      text: 'Created attachment 1
  
        MozReview Request: bz://123/mynick
  
  
        /r/2 - Bug 123 - Foo 1
  
        /r/3 - Bug 123 - Foo 2
  
  
        Pull down these commits:
  
  
        hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/'
    summary: Range 123

Should be able to publish these review requests again by publishing the
squashed review request.

  $ rbmanage publish $HGPORT1 1

Squashed review request should be published.

  $ rbmanage dumpreview $HGPORT1 1
  Review: 1
    Status: pending
    Public: True
    Bugs: 123
    Commit ID: bz://123/mynick
    Summary: bz://123/mynick
    Description:
      /r/2 - Bug 123 - Foo 1
      /r/3 - Bug 123 - Foo 2
      
      Pull down these commits:
      
      hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/
      
    Extra:
      p2rb: True
      p2rb.commits: [["bb41178fa30c323500834d0368774ef4ed412d7b", "2"], ["9d24f6cb513e7a5b4e19b684e863304b47dfe4c9", "3"]]
      p2rb.discard_on_publish_rids: []
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: True
      p2rb.unpublished_rids: []

Child review request with ID 2 should be published.

  $ rbmanage dumpreview $HGPORT1 2
  Review: 2
    Status: pending
    Public: True
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 1
    Description:
      Bug 123 - Foo 1
    Extra:
      p2rb: True
      p2rb.commit_id: bb41178fa30c323500834d0368774ef4ed412d7b
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False

Child review request with ID 3 should be published.

  $ rbmanage dumpreview $HGPORT1 3
  Review: 3
    Status: pending
    Public: True
    Bugs: 123
    Commit ID: None
    Summary: Bug 123 - Foo 2
    Description:
      Bug 123 - Foo 2
    Extra:
      p2rb: True
      p2rb.commit_id: 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9
      p2rb.identifier: bz://123/mynick
      p2rb.is_squashed: False

The attachment for the review request should be unobsoleted

  $ bugzilla dump-bug 123
  Bug 123:
    attachments:
    - attacher: admin@example.com
      content_type: text/x-review-board-request
      data: http://example.com/r/1/
      description: 'MozReview Request: bz://123/mynick'
      flags: []
      id: 1
      is_obsolete: false
      summary: 'MozReview Request: bz://123/mynick'
    comments:
    - author: admin@example.com
      id: 123
      tags: []
      text: ''
    - author: admin@example.com
      id: 124
      tags: []
      text: 'Created attachment 1
  
        MozReview Request: bz://123/mynick
  
  
        /r/2 - Bug 123 - Foo 1
  
        /r/3 - Bug 123 - Foo 2
  
  
        Pull down these commits:
  
  
        hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/'
    - author: admin@example.com
      id: 125
      tags: []
      text: 'Comment on attachment 1
  
        MozReview Request: bz://123/mynick
  
  
        /r/2 - Bug 123 - Foo 1
  
        /r/3 - Bug 123 - Foo 2
  
  
        Pull down these commits:
  
  
        hg pull -r 9d24f6cb513e7a5b4e19b684e863304b47dfe4c9 http://localhost:$HGPORT/'
    summary: Range 123

  $ cd ..
  $ rbmanage stop rbserver

  $ dockercontrol stop-bmo rb-test-review-request-closed-discarded
  stopped 2 containers
