# Posting findings as PR comments

Read this only when the user asks to post ("post these", "comment on the PR", "leave inline"). The default is still to report and stop.

Every command here uses `scripts/pr.py` in this skill's directory. Resolve it to an absolute path, and run it with the repo as the working directory, because `gh` and `glab` find the project from there. Run `python3 scripts/pr.py --help` if a flag is unclear.

## Before the first post

- Post only through `scripts/pr.py`. When it refuses, never edit it and never post another way (a connector, an MCP tool, a raw API call). Say why it refused and offer what the refusal allows.
- Posting writes to a shared system. If the agent is in a read-only or planning mode, ask the user to leave it first.
- Use the head SHA from the preflight `state` call. Pass it as `--head` on every post. The script exits 3 when the PR has moved since the review. Then stop, say so, and offer to re-review the new head.
- The script exits 4 for a closed or merged PR. Offer, in this order: post anyway, which still notifies the author; file an issue with the findings; a follow-up change in Apply mode, if the code is the user's; or drop them. Post anyway only on an explicit yes, by rerunning with `--allow-closed`, and say in the summary comment that these are post-merge follow-ups. File an issue only after a yes. A draft is fine when the user asked.
- Re-check every `file:line` at the head: pipe the findings to `python3 <skill-dir>/scripts/check_quotes.py --rev <head> -` as in §4, with ids matching the report's numbers. Hunks drift under rebase, and the file at head wins. Fix a `moved` line before posting. Don't post a `missing` one.
- Post the numbered findings only. Left-out items (judgment calls, unverified, refuted, overflow from "Worth an issue") stay off the PR unless the user names them.

## Post each finding

Write each finding's body to its own temp file, then:

```bash
python3 <skill-dir>/scripts/pr.py post <pr> --head <sha> \
  --path <file> --line <N or N-M> --body-file <tmp>
```

- The body is the full finding: title, label line with its evidence label, `file:line`, prose, the `Evidence:` line, and the fix. The evidence tells the author what was run and what was only read.
- A finding about a new test, with no line yet, anchors on the nearest sibling test and names it in the body ("sibling of `test_x`").
- A finding with no file (for example "the description is empty") leaves out `--path` and `--line` and becomes one general comment.
- A line outside the diff can't take an inline comment. The script posts a general comment instead and says why in `reason`. The body already names the `file:line`, so nothing is lost.
- A retry is safe: an identical comment at the same spot comes back as `"posted": "skipped"`.
- `--dry-run` prints what would be posted without posting it. Use it when the user wants to see the comments first.

After the findings, post one summary comment: the same command without `--path` and `--line`, plus `--marker`. The marker adds `<!-- review-changes: <head_sha> -->`, which the next preflight reads to spot "already reviewed at this SHA". The body is the verdict line, recounted over the posted findings, the `Reviewed:` line, the Standards and Spec verdicts if the report has them, and one line per posted finding: number, title, `file:line`. Leave out the `Left out:` line and the agent handoff line.

```text
Not ready: 1 Major (1), 1 missing from issue #41 (3).
Reviewed at 1a2b3c4 against AGENTS.md and issue #41.

Spec (issue #41)
Missing or partial: 3.
Scope creep: none. Only `tabs.ts` and `types.ts` change; settings and routing are untouched.
Implemented but wrong: none. `activate` restores the caret on every path the issue names.

1. Fall back to the previous tab when the last one closes, `src/store/tabs.ts:88`
2. Delete the comment that restates the code, `src/store/tabs.ts:70-74`
3. Keep the tab's scroll position, which the issue asks for, `src/store/tabs.ts:40`
```

Then report what landed in one block:

```text
Posted 4 to #285: 3 inline, 1 general (src/find.ts:52 is outside the diff), plus the summary.
```

## Fix or remove a posted comment

The `id` from `post` addresses the comment.

- GitHub: `gh api -X PATCH repos/{owner}/{repo}/pulls/comments/<id> -F body=@<tmp>` for inline, `.../issues/comments/<id>` for general. Use `-X DELETE` without the body to remove one.
- GitLab: `glab api -X PUT projects/:fullpath/merge_requests/<n>/notes/<note_id> -f "body=$(cat <tmp>)"`, or `-X DELETE` without the body. The `id` from an inline post is a discussion id; the note id is in `notes[0].id` of `glab api projects/:fullpath/merge_requests/<n>/discussions/<id>`.

Then stop. Never commit, push, open a PR, approve, or merge.
