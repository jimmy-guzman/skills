# Apply and re-review

Read this when the user says "apply" or names numbers after a report in Apply mode. Section numbers point to SKILL.md.

"apply" means every numbered item still on the list; "apply 1-4" or "all except 3" means those. Left-out items and "Worth an issue" lines are acted on only when named, as in "apply 2, L1".

- Keep each change minimal. A bug fix gets a test that fails without it, when the repo has tests. If §4 reproduced the bug with a new test, bring that test over.
- Run the repo's own checks afterward. Find them in agent docs first, then in the scripts of `package.json`, `Makefile`, `justfile`, or the equivalent.
- Re-review only what you just changed, with the same briefs from [reviewers.md](reviewers.md) and the §4 verification, and report by number. New findings take the §5 shape and continue the numbering.

```text
Applied 1-3. Not applied: 4.
Closed: 1, 2. Added a test for 1.
Still open: 3. Scroll is restored, but only after the first paint, so the view jumps.

Ran `pnpm check` and `pnpm test`: both pass.
```

Then stop again, and say what you didn't run. On "apply until clean", keep applying new findings and re-reviewing without stopping, three rounds at most, then report what is left.

Never commit, push, switch branches, or open a PR. File an issue only after a yes.
