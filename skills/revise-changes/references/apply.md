# Apply and re-verify

Read this once §3 has labeled every finding. Section numbers point to SKILL.md. Adapted from review-changes' apply.md: the "concern" here is already given by the thread, so there's no numbered-list picking step, but the fix discipline is identical.

- Re-resolve the PR now: re-run `pr.py state`. If the head moved since §1's fetch (a rebase, a force-push, new commits landed), say so and ask whether to re-run §1-3 against the new diff before continuing. The pre-apply/post-apply diff below only catches regressions from the fix itself.
- Before editing, take a snapshot the same way review-changes does: `git commit-tree` of the current index over HEAD. Call it the pre-apply snapshot.
- Fix only Reproduced and Traced findings. Refuted and Unverified ones are explained, not fixed, in §5's reply.
- Keep each change minimal. A bug fix gets a test that fails without it, when the repo has tests; for a fix that scopes or filters data per key, that test needs two keys whose correct values differ, not one shared fixture both paths would satisfy. If §3 reproduced the claim with a new test, bring that test over.
- Run the repo's own checks afterward. Find them in agent docs first, then in the scripts of `package.json`, `Makefile`, `justfile`, or the equivalent.
- Snapshot again; the post-apply snapshot is the revision for this round. Re-review only `git diff <pre-apply> <post-apply>` against the thread's own claim, not a fresh full review.

```text
Fixed T1, T3. Refuted: T2. Skipped (user excluded): T4.

Ran `pnpm check` and `pnpm test`: both pass.
```

Never commit, push, switch branches, or open a PR on your own. After §5's replies land, ask: `Commit these fixes? Say "commit", or name a different message.` Commit only on an explicit yes.
