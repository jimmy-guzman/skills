# Preflight reports

Read this when the preflight in SKILL.md §1 picked Skip or Novel only.

## Novel only

Use the mode's report from SKILL.md §5, titled `Supplemental review (<N> existing threads skipped)`, and add this above the mode's last line:

```text
Existing threads cover prior rounds; the findings above are novel only.
```

## Skip

The report is only the PR's state, from `scripts/pr.py state`:

```text
Context-only: <state> PR <ref>, head <short_sha>
Title: <title>
Author: <author>
Threads: <open> open, <resolved> resolved. Last review: <short sha from reviewed_shas, or "none">.

No review run.
```

Then stop.
