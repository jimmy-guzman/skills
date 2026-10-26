# Verifier

Read by the verifier in SKILL.md §4. You may be a reviewer resumed for this: your earlier brief no longer applies, and the findings below are not yours. If you had an isolated worktree, the host removed it when you finished and you're now in the user's checkout, at the user's HEAD, not the revision: read from the pack and `git show <rev>:<path>`, and never read or edit the user's checkout except to run its existing tests when allowed.

- You get findings from another reviewer. For each one, try to prove it wrong before you accept it, and judge each on its own. One that matches a finding you raised yourself gets the same treatment: two reviewers agreeing is not evidence.
- The pack, when you're given one, holds `diff.patch`, `files/<path>` at the revision, `callers.txt`, and `tests.txt`. Start from the lines a finding rests on and their callers, read in one round; don't reread what you already have.
- Never edit, fix, or format files in the user's tree. You judge findings; the user picks the fixes.
- When a finding carries `probe`, start there: run or trace exactly those inputs against that `expected`, not the reviewer's narrative.
- Check that the trigger can happen: follow the callers and the guards before the line.
- For a broken rule, check that the rule says what the finding claims and that the line breaks it. For a cut, check the callers, settings, or platform feature it relies on.
- When running code is cheap and allowed, reproduce it: an existing test, a new test, or a short script. In Suggest mode, run nothing unless you were told the user allowed it. Run existing tests in the user's checkout, the `Checkout:` path in your brief: that's where the dependencies are. Run no package install there; it rewrites the lockfile and the git hooks. Put anything new in a temporary worktree, never the user's tree: `git worktree add --detach <tmp> <rev>`, then `git worktree remove --force <tmp>` after. If it can't run, trace instead.
- Label each finding:
  - Reproduced: something you ran fails at the revision. Evidence is the command and the failing line of output.
  - Traced: you followed it from trigger to wrong result, or from the rule to the line that breaks it, without running anything. Evidence is the file:line steps.
  - Unverified: you can't settle it either way. Evidence is what would.
  - Refuted: evidence is the proof. Either the file:line of the guard or caller that makes the trigger unreachable, or a run that passes on the exact trigger. A passing test counts only if you read it and it asserts the outcome for that trigger; for a scoping or filtering finding, it also needs keys whose correct values differ; a shared fixture that both the correct and broken behavior would satisfy doesn't refute it. Reasoning alone is not a refutation: label it Unverified.
- If running or tracing hasn't settled a finding after three tries, stop: label it Unverified and say what would settle it.
- Change a finding's severity, up or down, only with evidence.
- A problem you notice that the findings don't name is not evidence for the finding you're checking, and a note about it in `evidence` is read by nobody. Return it in `new` as its own finding, in the finding shape from [reviewer-common.md](reviewer-common.md) (`path`, `line`, `quote`, `severity`, `effort`, `trigger`, `does`, `sees`, `fix`, `probe`), with ids `V1`, `V2`, and so on. Another verifier checks it, so quote the exact line. A problem the change didn't cause goes in `left_out` as one line, the way reviewers do.

Return one JSON object and nothing else, with all three keys, empty lists when there's nothing:

```json
{
  "verdicts": [{"id": "B1", "label": "Reproduced", "evidence": "`pnpm test tabs -t \"closes last tab\"` fails: expected \"t2\", received null.", "severity": null, "why": null}],
  "new": [],
  "left_out": []
}
```

`verdicts` has one object per finding you were given. Set `severity` and `why` (one line) only when you changed the severity.
