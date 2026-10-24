# Preflight

Read this from SKILL.md §1 when the revision is a PR, after `scripts/pr.py state` has run.

It triggers when any of these hold:

- The PR is closed or merged.
- The PR is a draft, and the user didn't say to review it anyway. Asking for a review, or invoking this skill, doesn't count.
- `reviewed_at_head` is true.
- `threads.open` is above zero.

On a trigger, ask the user to pick one, and name what triggered:

- **Skip**: print the Context-only report below. Nothing else runs.
- **Novel only**: review, and pass the thread anchors to the reviewers so findings already raised drop out. The report takes the Supplemental shape below.
- **Full review**: review as if there were no threads.

When `truncated` is true, say the thread list may be incomplete. No trigger, no question.

## Novel only

Use the mode's report from SKILL.md §5, titled `Supplemental review (<N> existing threads skipped)`, and add this above the mode's last line:

```text
Existing threads cover prior rounds; the findings above are novel only.
```

Open threads block too. Add them to the verdict line, as in `Not ready: 1 Major (2), 2 open threads.`

## Skip

The report is only the PR's state, from `scripts/pr.py state`:

```text
Context-only: <state> PR <ref>, head <short_sha>
Title: `<title>`
Author: `<author>`
Threads: <open> open, <resolved> resolved. Last review: <short sha from reviewed_shas, or "none">.

No review run.
```

Then stop.
