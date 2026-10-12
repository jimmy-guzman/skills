# Apply and re-review

Read this when the user says "apply" or names numbers after a report in Apply mode. Section numbers point to SKILL.md.

"apply" means every numbered item still on the list; "apply 1-4" or "all except 3" means those. Left-out items and "Worth an issue" lines are acted on only when named, as in "apply 2, L1".

- Before editing, take a snapshot as in §1. Call it the pre-apply snapshot.
- Apply only what was picked. Fix what your own change broke; anything else you find goes through §4 unfixed, then into this round's report: a new number if this change caused it, "Worth an issue" if not.
- Keep each change minimal. A bug fix gets a test that fails without it, when the repo has tests. If §4 reproduced the bug with a new test, bring that test over.
- Run the repo's own checks afterward. Find them in agent docs first, then in the scripts of `package.json`, `Makefile`, `justfile`, or the equivalent.
- Snapshot again; the post-apply snapshot is the revision for this round. Re-review only `git diff <pre-apply> <post-apply>`, with the same briefs from [reviewer-common.md](reviewer-common.md) and its role files, and the §4 verification, and report by number. New findings take the §5 shape and continue the numbering.

```text
Applied 1-3. Not applied: 4.
Closed: 1, 2. Added a test for 1.
Still open: 3. Scroll is restored, but only after the first paint, so the view jumps.

Ran `pnpm check` and `pnpm test`: both pass.
```

Then stop again, and say what you didn't run. On "apply until clean", keep applying new findings and re-reviewing without stopping, three rounds at most, then report what is left.

Never commit, push, switch branches, or open a PR. File an issue only after a yes.
