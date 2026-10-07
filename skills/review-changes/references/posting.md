# Posting findings as PR comments

Read this only when the user asks to post ("post these", "comment on the PR", "leave inline"). The default is still to report and stop.

Every command here uses `scripts/pr.py` in this skill's directory. Resolve it to an absolute path, and run it with the repo as the working directory, because `gh` and `glab` find the project from there. Run `python3 scripts/pr.py --help` if a flag is unclear.

## Before the first post

- Posting writes to a shared system. If the agent is in a read-only or planning mode, ask the user to leave it first.
- Use the head SHA from the preflight `state` call. Pass it as `--head` on every post. The script exits 3 when the PR has moved since the review. Then stop, say so, and offer to re-review the new head.
- The script exits 4 for a closed or merged PR. Comments there are visible but nobody acts on them. A draft is fine when the user asked.
- Re-check every `file:line` at the head with `python3 <skill-dir>/scripts/check_quotes.py --rev <head> <findings.json>`, the same file §4 used. Hunks drift under rebase, and the file at head wins. Fix a `moved` line before posting. Don't post a `missing` one.
- Post the numbered findings only. Left-out items (judgment calls, unverified, refuted, overflow from "Worth an issue") stay off the PR unless the user names them.

## Post each finding

Write each finding's body to its own temp file, then:

```bash
python3 <skill-dir>/scripts/pr.py post <pr> --head <sha> \
  --path <file> --line <N or N-M> --body-file <tmp> [--marker]
```

- Pass `--marker` on the first post of the round only. It adds `<!-- review-changes: <head_sha> -->`, which the next preflight reads to spot "already reviewed at this SHA".
- The body is the full finding: title, label line with its evidence label, `file:line`, prose, the `Evidence:` line, and the fix. The evidence tells the author what was run and what was only read.
- A finding about a new test, with no line yet, anchors on the nearest sibling test and names it in the body ("sibling of `test_x`").
- A finding with no file (for example "the description is empty") leaves out `--path` and `--line` and becomes one general comment.
- A line outside the diff can't take an inline comment. The script posts a general comment instead and says why in `reason`. The body already names the `file:line`, so nothing is lost.
- A retry is safe: an identical comment at the same spot comes back as `"posted": "skipped"`.
- `--dry-run` prints what would be posted without posting it. Use it when the user wants to see the comments first.

Report what landed in one block:

```text
Posted 4 to #285: 3 inline, 1 general (src/find.ts:52 is outside the diff).
```

## Fix or remove a posted comment

The `id` from `post` addresses the comment.

- GitHub: `gh api -X PATCH repos/{owner}/{repo}/pulls/comments/<id> -F body=@<tmp>` for inline, `.../issues/comments/<id>` for general. Use `-X DELETE` without the body to remove one.
- GitLab: `glab api -X PUT projects/:fullpath/merge_requests/<n>/notes/<note_id> -f "body=$(cat <tmp>)"`, or `-X DELETE` without the body. The `id` from an inline post is a discussion id; the note id is in `notes[0].id` of `glab api projects/:fullpath/merge_requests/<n>/discussions/<id>`.

Then stop. Never commit, push, open a PR, approve, or merge.
