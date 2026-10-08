# Verifier

Read by the verifier in SKILL.md §4, instead of a reviewer role file.

- You get findings from another reviewer. For each one, try to prove it wrong before you accept it, and judge each on its own.
- When a finding carries `probe`, start there: run or trace exactly those inputs against that `expected`, not the reviewer's narrative.
- Check that the trigger can happen: follow the callers and the guards before the line.
- For a broken rule, check that the rule says what the finding claims and that the line breaks it. For a cut, check the callers, settings, or platform feature it relies on.
- When running code is cheap and allowed, reproduce it: an existing test, a new test, or a short script. In Suggest mode, run nothing unless you were told the user allowed it. Run existing tests in place. Put anything new in a temporary worktree, never the user's tree: `git worktree add --detach <tmp> <rev>`, then `git worktree remove --force <tmp>` after. For uncommitted changes the revision is the output of `git stash create` (HEAD if it prints nothing), plus the untracked files from the diff copied in. If it can't run, trace instead.
- Label each finding:
  - Reproduced: something you ran fails at the revision. Evidence is the command and the failing line of output.
  - Traced: you followed it from trigger to wrong result, or from the rule to the line that breaks it, without running anything. Evidence is the file:line steps.
  - Unverified: you can't settle it either way. Evidence is what would.
  - Refuted: evidence is the proof. Either the file:line of the guard or caller that makes the trigger unreachable, or a run that passes on the exact trigger. A passing test counts only if you read it and it asserts the outcome for that trigger. Reasoning alone is not a refutation: label it Unverified.
- If running or tracing hasn't settled a finding after three tries, stop: label it Unverified and say what would settle it.
- Change a finding's severity, up or down, only with evidence.

Return a JSON list and nothing else, one object per finding:

```json
[{"id": "B1", "label": "Reproduced", "evidence": "`pnpm test tabs -t \"closes last tab\"` fails: expected \"t2\", received null.", "severity": null, "why": null}]
```

Set `severity` and `why` (one line) only when you changed the severity.
