"""Push commits to Review Board.

This module contains code for taking commits from version control (Git,
Mercurial, etc) and adding them to Review Board.

It is intended for this module to be generic and applicable to any
Review Board install. Please abstract away Mozilla implementation
details.
"""

import json

from rbtools.api.client import RBClient
from rbtools.api.errors import APIError


def post_reviews(url, repoid, identifier, commits, username=None, password=None,
                 userid=None, cookie=None):
    """Post a set of commits to Review Board.

    Repository hooks can use this function to post a set of pushed commits
    to Review Board. Each commit will become its own review request.
    Additionally, a review request with a diff encompassing all the commits
    will be created; This "squashed" review request will represent the push
    for the provided ``identifier``.

    The ``identifier`` is a unique string which represents a series of pushed
    commit sets. This identifier is used to update review requests with a new
    set of diffs from a new push. Generally this identifier will represent
    some unit of work, such as a bug.

    The ``commits`` argument takes the following form::

        {
            'squashed': {
                'diff': <squashed-diff-string>,
            },
            'individual': [
                {
                    'id': <commit-id>,
                    'precursors': [<previous changeset>],
                    'message': <commit-message>,
                    'diff': <diff>,
                    'parent_diff': <diff-from-base-to-commit>,
                },
                {
                    ...
                },
                ...
            ]
        }

    When representing the commits on Review Board, we store meta data in the
    extra_data dictionaries. We use a number of fields to keep track of review
    requests and the state they are in.

    The following ASCII Venn Diagram represents sets the related review requests
    may be in and how they overlap.

    Legend:

    * "unpublished_rids" = squashed_rr.extra_data['p2rb.unpublished_rids']
    * "discard_on_publish_rids" = squashed_rr.extra_data['p2rb.discard_on_publish_rids']
    * "squashed.commits" = squashed_rr.extra_data['p2rb.commits']
    * "draft.commits" = squashed_rr.draft.extra_data['p2rb.commits']

    * A = unpublished_rids - draft.commits
    * B = draft.commits - squashed.commits
    * C = draft.commits - unpublished rids
    * D = delete_on_publish_rids

    Diagram::

                unpublished_rids                       squashed.commits
         ________________________________________________________________
        |                             |                                  |
        |                             |                                  |
        |                _____________|_____________                     |
        |               |             |             |                    |
        |        A      |       draft.commits       |           D        |
        |               |             |             |                    |
        |               |             |             |                    |
        |               |      B      |        C    |                    |
        |               |             |             |                    |
        |               |             |             |                    |
        |               |_____________|_____________|                    |
        |                             |                                  |
        |                             |         discard_on_publish_rids  |
        |                             |                                  |
        |_____________________________|__________________________________|


    The following rules should apply to the review request sets when publishing
    or discarding.

    When publishing the squashed review request:

    * A: close "discarded" because it was never used
    * B: publish draft
    * C: publish draft
    * D: close "discarded" because it is obsolete
    * set unpublished_rids to empty '[]'
    * set discard_on_publish_rids to empty '[]'

    When discarding the draft of a published squashed review request:

    * A: close "discarded" because it was never used (so it does not appear in
      the owners dashboard)
    * B: close "discarded" because it was never used (so it does not appear in
      the owners dashboard)
    * C: DELETE the review request draft
    * D: do nothing
    * set unpublished_rids to empty '[]'
    * set discard_on_publish_rids to empty '[]'

    When discarding an unpublished squashed review request (always a close "discarded"):

    * TODO Bug 1047465
    """
    rbc = None

    if userid and cookie:
        # TODO: This is bugzilla specific code that really shouldn't be inside
        # of this file. The whole bugzilla cookie resource is a hack anyways
        # though so we'll deal with this for now.
        rbc = RBClient(url)
        login_resource = rbc.get_path(
            'extensions/rbbz.extension.BugzillaExtension/'
            'bugzilla-cookie-logins/')
        login_resource.create(login_id=userid, login_cookie=cookie)
    else:
        rbc = RBClient(url, username=username, password=password)

    api_root = rbc.get_root()

    # This assumes that we pushed to the repository/URL that Review Board is
    # configured to use. This assumption may not always hold.
    repo = api_root.get_repository(repository_id=repoid)
    repo_url = repo.path

    # Retrieve the squashed review request or create it.
    previous_commits = []
    squashed_rr = None
    rrs = api_root.get_review_requests(commit_id=identifier,
                                       repository=repoid)

    if rrs.total_results > 0:
        squashed_rr = rrs[0]
    else:
        # A review request for that identifier doesn't exist - this
        # is the first push to this identifier and we'll need to create
        # it from scratch.
        squashed_rr = rrs.create(**{
            "extra_data.p2rb": "True",
            "extra_data.p2rb.is_squashed": "True",
            "extra_data.p2rb.identifier": identifier,
            "extra_data.p2rb.discard_on_publish_rids": '[]',
            "extra_data.p2rb.unpublished_rids": '[]',
            "commit_id": identifier,
            "repository": repoid,
        })

    squashed_rr.get_diffs().upload_diff(commits["squashed"]["diff"])

    def update_review_request(rid, commit):
        rr = api_root.get_review_request(review_request_id=rid)
        draft = rr.get_or_create_draft(**{
            "summary": commit['message'].splitlines()[0],
            "description": commit['message'],
            "extra_data.p2rb.commit_id": commit['id'],
        })
        rr.get_diffs().upload_diff(commit['diff'],
                                   parent_diff=commit['parent_diff'])

        return rr

    # TODO: We need to take into account the commits data from the squashed
    # review request's draft. This data represents the mapping from commit
    # to rid in the event that we would have published. We're overwritting
    # this data. This will only come into play if we start trusting the server
    # isntead of the client when matching review request ids. Bug 1047516
    previous_commits = get_previous_commits(squashed_rr)

    # A mapping from previously pushed node, which has not been processed
    # yet, to the review request id associated with that node.
    remaining_nodes = dict((t[0], t[1]) for i, t in enumerate(previous_commits))

    # A list of review request ids that should be discarded when publishing.
    # Adding to this list will mark a review request as to-be-discarded when
    # the squashed draft is published on Review Board.
    discard_on_publish_rids = rid_list_to_str(json.loads(
        squashed_rr.extra_data['p2rb.discard_on_publish_rids']))

    # A list of review request ids that have been created for individual commits
    # but have not been published. If this list contains an item, it should be
    # re-used for indiviual commits instead of creating a brand new review
    # request.
    unpublished_rids = rid_list_to_str(json.loads(
        squashed_rr.extra_data['p2rb.unpublished_rids']))

    # Set of review request ids which have not been matched to a commit
    # from the current push. We use a list to represent this set because
    # if any entries are left over we need to process them in order.
    # This list includes currently published rids that were part of the
    # previous push and rids which have been used for drafts on this
    # reviewid but have not been published.
    unclaimed_rids = [t[1] for t in previous_commits]

    for rid in (discard_on_publish_rids + unpublished_rids):
        if rid not in unclaimed_rids:
            unclaimed_rids.append(rid)

    # Previously pushed nodes which have been processed and had their review
    # request updated or did not require updating.
    processed_nodes = set()

    node_to_rid = {}

    # A mapping from review request id to the corresponding review request
    # API object.
    review_requests = {}

    # Do a pass and find all commits that map cleanly to old review requests.
    for commit in commits['individual']:
        node = commit['id']

        if node not in remaining_nodes:
            continue

        # If the commit appears in an old review request, by definition of
        # commits deriving from content, the commit has not changed and there
        # is nothing to update. Update our accounting and move on.
        rid = remaining_nodes[node]
        del remaining_nodes[node]
        unclaimed_rids.remove(rid)
        processed_nodes.add(node)
        node_to_rid[node] = rid

        rr = api_root.get_review_request(review_request_id=rid)
        review_requests[rid] = rr

        try:
            discard_on_publish_rids.remove(rid)
        except ValueError:
            pass

    # Find commits that map to a previous version.
    for commit in commits['individual']:
        node = commit['id']
        if node in processed_nodes:
            continue

        # The client may have sent obsolescence data saying which commit this
        # commit has derived from. Use that data (if available) to try to find
        # a mapping to an old review request.
        for precursor in commit['precursors']:
            rid = remaining_nodes.get(precursor)
            if not rid:
                continue

            del remaining_nodes[precursor]
            unclaimed_rids.remove(rid)

            rr = update_review_request(rid, commit)
            processed_nodes.add(node)
            node_to_rid[node] = rid
            review_requests[rid] = rr

            try:
                discard_on_publish_rids.remove(rid)
            except ValueError:
                pass

            break

    # Now do a pass over the commits that didn't map cleanly.
    for commit in commits['individual']:
        node = commit['id']
        if node in processed_nodes:
            continue

        # We haven't seen this commit before *and* our mapping above didn't
        # do anything useful with it.

        # This is where things could get complicated. We could involve
        # heuristic based matching (comparing commit messages, changed
        # files, etc). We may do that in the future.

        # For now, match the commit up against the next one in the index.
        # The unclaimed rids list contains review requests which were created
        # when previously updating this review identifier, but not published.
        # If we have more commits than were previously published we'll start
        # reusing these private review requests before creating new ones.
        if unclaimed_rids:
            assumed_old_rid = unclaimed_rids[0]
            unclaimed_rids.pop(0)
            rr = update_review_request(assumed_old_rid, commit)
            processed_nodes.add(commit['id'])
            node_to_rid[node] = assumed_old_rid
            review_requests[assumed_old_rid] = rr

            try:
                discard_on_publish_rids.remove(assumed_old_rid)
            except ValueError:
                pass

            continue

        # There are no more unclaimed review request IDs. This means we have
        # more commits than before. Create new review requests as appropriate.
        rr = rrs.create(**{
            'extra_data.p2rb': 'True',
            'extra_data.p2rb.is_squashed': 'False',
            'extra_data.p2rb.identifier': identifier,
            'extra_data.p2rb.commit_id': commit['id'],
            'repository': repoid,
        })
        rr.get_diffs().upload_diff(commit['diff'],
                                   parent_diff=commit['parent_diff'])
        draft = rr.get_or_create_draft(
            summary=commit['message'].splitlines()[0],
            description=commit['message'])
        processed_nodes.add(commit['id'])
        # Normalize all review request identifiers to strings.
        assert isinstance(rr.id, int)
        rid = str(rr.id)
        node_to_rid[node] = rid
        review_requests[rid] = rr
        unpublished_rids.append(rid)

    # At this point every incoming commit has been accounted for.
    # If there are any remaining review requests, they must belong to
    # deleted commits. (Or, we made a mistake and updated the wrong review
    # request)
    for rid in unclaimed_rids:
        rr = api_root.get_review_request(review_request_id=rid)

        if rr.public and rid not in discard_on_publish_rids:
            # This review request has already been published so we'll need to
            # discard it when we publish the squashed review request.
            discard_on_publish_rids.append(rid)
        elif not rr.public and rid not in unpublished_rids:
            # We've never published this review request so it may be reused in
            # the future for *any* commit. Keep track of it.
            unpublished_rids.append(rid)
        else:
            # This means we've already marked the review request properly
            # in a previous push, so do nothing.
            pass


    squashed_description = []
    for commit in commits['individual']:
        squashed_description.append('/r/%s - %s' % (
            node_to_rid[commit['id']],
            commit['message'].splitlines()[0]))

    squashed_description.extend(['', 'Pull down '])
    if len(commits['individual']) == 1:
        squashed_description[-1] += 'this commit:'
    else:
        squashed_description[-1] += 'these commits:'

    squashed_description.extend([
        '',
        'hg pull -r %s %s' % (commits['individual'][-1]['id'], repo_url),
    ])

    commit_list = []
    for commit in commits['individual']:
        node = commit['id']
        commit_list.append([node, node_to_rid[node]])

    commit_list_json = json.dumps(commit_list)
    depends = ','.join(str(i) for i in sorted(node_to_rid.values()))

    squashed_draft = squashed_rr.get_or_create_draft(**{
        'summary': identifier,
        'description': '%s\n' % '\n'.join(squashed_description),
        'depends_on': depends,
        'extra_data.p2rb.commits': commit_list_json,
    })

    squashed_rr.update(**{
        'extra_data.p2rb.discard_on_publish_rids': json.dumps(
            discard_on_publish_rids),
        'extra_data.p2rb.unpublished_rids': json.dumps(
            unpublished_rids),
    })

    review_requests[str(squashed_rr.id)] = squashed_rr

    return str(squashed_rr.id), node_to_rid, review_requests


def rid_list_to_str(rids):
    """Convert a list of rids loaded from json to a list of rid strings.

    Using unicode strings, or ints, could cause problems interacting with
    other code, so we need to make sure each rid is represented using a
    string.
    """
    rv = []
    for rid in rids:
        if isinstance(rid, unicode):
            rid = rid.encode('utf-8')
        elif isinstance(rid, int):
            rid = str(rid)

        rv.append(rid)

    return rv

def get_previous_commits(squashed_rr):
    """Retrieve the previous commits from a squashed review request.

    This will return a list of tuples specifying the previous commit
    id as well as the review request it is represented by. ex::

        [
            # (<commit-id>, <review-request-id>),
            ('d4bd89322f54', '13'),
            ('373537353134', '14'),
        ]
    """
    extra_data = None

    if not squashed_rr.public:
        extra_data = squashed_rr.get_draft().extra_data
    else:
        extra_data = squashed_rr.extra_data

    if 'p2rb.commits' not in extra_data:
        return []

    commits = []
    for node, rid in json.loads(extra_data['p2rb.commits']):
        # JSON decoding likes to give us unicode types. We speak str
        # internally, so convert.
        if isinstance(node, unicode):
            node = node.encode('utf-8')

        if isinstance(rid, unicode):
            rid = rid.encode('utf-8')
        elif isinstance(rid, int):
            rid = str(rid)

        assert isinstance(node, str)
        assert isinstance(rid, str)

        commits.append((node, rid))

    return commits
