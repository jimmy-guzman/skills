# Preflight

Read this from SKILL.md §1 when the revision is a PR, after `scripts/pr.py state` has run.

First match wins:

1. **Re-review**: `last_reviewed_sha` is set, `reviewed_at_head` is false, and the PR is open and not a draft. Don't ask; run the Re-review below. The user's words override ("full review" runs a full one).
2. **Ask**: any of these hold:
   - The PR is closed or merged.
   - The PR is a draft, and the user didn't say to review it anyway. Asking for a review, or invoking this skill, doesn't count.
   - `reviewed_at_head` is true.
   - `threads.open` is above zero.
3. Otherwise, no question: review as usual.

On Ask, have the user pick one, and say what triggered it:

- **Skip**: print the Context-only report below. Nothing else runs.
- **Novel only**: review, and pass the thread anchors to the reviewers so findings already raised drop out. The report takes the Supplemental shape below. Leave this choice out when `reviewed_at_head` triggered: nothing has changed since the last review.
- **Full review**: review as if there were no threads.

When `threads.unknown` is above zero, say that many threads may be open or resolved: the host's API didn't say which. Review as if there were no threads unless the user says otherwise.

## Thread check

Used by Novel only and Re-review. Before the verdict, check each open thread against the new head. A thread blocks only when the head still has the problem it names and it was raised against this change. Add the blocking ones to the verdict line, as in `Not ready: 1 Major (2), 2 open threads.` The rest don't count toward the verdict. List each one under the verdict, one line per thread: `fixed at <short sha>: <file:line>, can be resolved`, `still open: <file:line>`, or `not from this change`.

## Re-review

The earlier rounds already reviewed the code up to `last_reviewed_sha`, which below is `<last>`. A full review every round finds new opinions on code nobody touched, and the rounds never end. So only new code gets a full review; old code is checked only for bugs that block the merge.

1. Fetch it: `git fetch <remote> <last>`. If the fetch fails, `git merge-base --is-ancestor <last> <head_sha>` exits non-zero, or `git merge-base <remote>/<base_ref> <last>` differs from `git merge-base <remote>/<base_ref> <head_sha>`, the branch was rebased, force-pushed, or had its base merged in. Run a full review instead, and say so on the `Reviewed:` line: `Full review: <short last> is no longer in the branch.`, or `Full review: <base_ref> was merged in since <short last>.` when only the merge-base check tripped.
2. **Delta**: diff `<last>...<head_sha>` with §1's exclusions, build its pack, and pick reviewers from §3's rules sized on this diff. Its findings take every group.
3. **Full PR**: build a second pack from the full PR diff and run one Bugs reviewer on it, with the thread anchors. From its batch, keep only findings that would land in Must fix. The rest go to the left-out file as `earlier code, not must fix`, before §4, so nobody verifies them.
4. Run the Thread check above.
5. Verify both batches as in §4. Report as in §5, titled `Re-review since <short last>`. The `Reviewed:` line names both scopes: `delta <short last>..<short head> (3 files), full PR for must-fix bugs.`

## Novel only

Use the mode's report from SKILL.md §5, titled `Supplemental review (<N> existing threads skipped)`, and add this above the mode's last line:

```text
Existing threads cover prior rounds; the findings above are novel only.
```

Run the Thread check above.

## Skip

The report is only the PR's state, from `scripts/pr.py state`:

```text
Context-only: <state> PR <ref>, head <short_sha>
Title: `<title>`
Author: `<author>`
Threads: <open> open, <resolved> resolved, <unknown> unknown (leave out when 0). Last review: <short last_reviewed_sha, or "none">.

No review run.
```

Then stop.
