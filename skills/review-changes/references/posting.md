# Posting findings as PR comments

Read this only when the user asks to post ("post these", "comment on the PR", "leave inline"). The default is still to report and stop.

Every command here uses `scripts/pr.py` in this skill's directory. Resolve it to an absolute path, and run it with the repo as the working directory, because `gh` and `glab` find the project from there. Run `python3 scripts/pr.py --help` if a flag is unclear.

## Before the first post

- Post only through `scripts/pr.py`. When it refuses, never edit it and never post another way (a connector, an MCP tool, a raw API call). Say why it refused and offer what the refusal allows.
- Posting writes to a shared system. If the agent is in a read-only or planning mode, ask the user to leave it first.
- Use the head SHA from the preflight `state` call. Pass it as `--head` on every post. The script exits 3 when the PR has moved since the review. Then stop, say so, and offer to re-review the new head.
- The script exits 4 for a closed or merged PR. Offer, in this order: post anyway, which still notifies the author; file an issue with the findings; a follow-up change in Apply mode, if the code is the user's; or drop them. Post anyway only on an explicit yes, by rerunning with `--allow-closed`, and say in the summary comment that these are post-merge follow-ups. File an issue only after a yes. A draft is fine when the user asked.
- Re-check every `file:line` at the head: write the findings to a temp file and run `python3 <skill-dir>/scripts/check_quotes.py --rev <head> --base <base> <file>` as in §4, with ids matching the report's numbers. Hunks drift under rebase, and the file at head wins. Fix a `moved` line before posting. Don't post a `missing` one.
- Post the numbered findings only. Left-out items (judgment calls, unverified, refuted, overflow from "Worth an issue") stay off the PR unless the user names them.

## Post each finding

Write each finding's body to its own temp file, and the summary's too (below). List every post in one JSON file, findings in report order and the summary last, and post them in one call. Don't loop over posts in the shell: one call checks every entry and the head before anything posts, and there's no loop variable to collide with one the shell owns (`path` in zsh is tied to `PATH`).

```json
[
  {"body_file": "/tmp/rc/1.md", "path": "src/store/tabs.ts", "line": "88"},
  {"body_file": "/tmp/rc/2.md", "path": "src/store/tabs.ts", "line": "40"},
  {"body_file": "/tmp/rc/3.md", "path": "src/lib/load.ts", "line": "12", "removed": true},
  {"body_file": "/tmp/rc/summary.md"}
]
```

A finding with `removed` true carries it into its entry, so the comment lands on the deleted line (its `line` is the old file's).

```bash
python3 <skill-dir>/scripts/pr.py post <pr> --head <sha> --batch /tmp/rc/posts.json
```

The inline findings land the way a human review does, in one request with one notification. On GitHub they post as one review whose body is the summary. On GitLab they post as draft notes and then publish together, and the summary posts after as a general comment. It prints one JSON line per entry with its `index`: `posted` (`inline`, `general`, `review` for a GitHub summary, or `skipped`), `reason`, and the `id` the follow-up commands below take. A single comment (a late fix, one more finding) uses `--path <file> --line <N or N-M> --body-file <tmp>` (plus `--removed` for a finding with `removed` true) in place of `--batch`.

On GitLab, exit 7 means the user already has unpublished draft notes on the MR, and publishing would send those too. Nothing posted. Say so and ask them to publish or delete their drafts first; never delete them yourself.

- The body is the full finding: title, label line with its evidence label, `file:line`, prose, the `Evidence:` line, and the fix. The evidence tells the author what was run and what was only read.
- Shape it for the host's markdown, not the report's. The title is `**3. Title**`, keeping the report number the summary points to. Nothing is indented. Put a blank line between parts: GitLab joins lines split by a single newline into one paragraph.

  ````markdown
  **1. Fall back to the previous tab when the last one closes**

  Major | Quick win | Reproduced

  `src/store/tabs.ts:88`

  Closing the last tab reads `next[index]`, which is past the end after the removal. The app is left with tabs open and none active.

  Evidence: `pnpm test tabs -t "closes last tab"` fails: expected "t2", received null.

  ```diff
  -  const active = next[index] ?? null;
  +  const active = next[Math.min(index, next.length - 1)] ?? null;
  ```
  ````
- A question posts as the report shows it: the question title and both `If` lines, so the author picks the side. When the user answered it ("2a" or "2b"), post only that side, with a command title like any finding.
- A finding about a new test, with no line yet, anchors on the nearest sibling test and names it in the body ("sibling of `test_x`").
- A finding with no file (for example "the description is empty") leaves out `--path` and `--line` and becomes one general comment.
- A line outside the diff can't take an inline comment. The script posts a general comment instead, outside the review, and says why in `reason`. The body already names the `file:line`, so nothing is lost.
- A retry is safe: an identical comment at the same spot comes back as `"posted": "skipped"`.
- `--dry-run` prints what would be posted without posting it. Use it when the user wants to see the comments first.
- `pr.py post` starts every post, finding or summary, with `<!-- review-changes: <head_sha> -->`; don't write it in the body. The next preflight reads it to spot "already reviewed at this SHA", so a run that posts findings without a summary still counts.
- Post the summary comment unless the user said "no summary" (or otherwise declined it) in the §5 ask.

Unless the user declined it, the summary is the batch's last entry, with no `path` or `line`. The body is two lines: the verdict, recounted over the posted findings, then `Reviewed at <short sha> against <sources>.` Nothing else: the threads already carry the findings, so leave out the `Change:` line, the Standards and Spec footer, any list of findings, the `Left out:` line, and the agent handoff line. A post-merge batch (`--allow-closed`) adds a third line saying these are post-merge follow-ups. Put a blank line between lines, as in the findings, and keep it when patching the summary later.

```text
Not ready: 1 Major (1). 1 question (2).

Reviewed at 1a2b3c4 against AGENTS.md and issue #41.
```

Then report what landed in one block:

```text
Posted 4 to #285: 3 inline, 1 general (src/find.ts:52 is outside the diff), plus the summary.
```

When the user declined the summary:

```text
Posted 3 to #285: 3 inline (no summary posted).
```

## Fix or remove a posted comment

Pass the `id` from `post` as `--comment`, plus `--general` when `post` said `general`, or `--review` when it said `review`:

```bash
python3 <skill-dir>/scripts/pr.py edit <pr> --comment <id> --body-file <tmp>
python3 <skill-dir>/scripts/pr.py delete <pr> --comment <id>
```

A GitHub review's body takes `edit --review` only: GitHub can't delete a submitted review. To retract a summary there, edit it down to a line saying why.

`reply` and `resolve` take `--general` on GitLab, where a general comment is a resolvable thread that `state` counts as open. On GitHub they refuse it, since a general comment there has no thread.

## Downgrade or dismiss a posted finding

When the user decides a posted finding no longer holds as scored (lower severity, not a real issue, already fixed elsewhere), do these, in order:

1. Reply on the finding's thread saying so, in a few words: `pr.py reply <pr> --comment <id> --body-file <tmp>`.
2. Resolve the thread: `pr.py resolve <pr> --comment <id>`.
3. If a summary was posted, patch it (the review body on GitHub, or the general comment on GitLab, that starts with the `<!-- review-changes: <sha> -->` marker) with `pr.py edit <pr> --comment <summary-id> --review --body-file <tmp>` (`--general` in place of `--review` when `post` said `general`), so its verdict still matches what the threads show: recount it and note the change in a few words, e.g. `Ready. 3 findings. 1 question (2). (1 downgraded to nice to have, resolved.)` Don't leave it stale.
