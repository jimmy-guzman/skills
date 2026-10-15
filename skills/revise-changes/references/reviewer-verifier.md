# Verifier

Read in SKILL.md §3. The findings come from PR threads, extracted per [extraction.md](extraction.md); the "reviewer" is whoever wrote the thread, bot or human.

- For each finding, try to prove it wrong before you accept it, and judge each on its own.
- Never edit, fix, or format files in the user's tree. You judge findings; the fix step comes after.
- When a finding carries `probe`, start there: run or trace exactly those inputs against that `expected`, not the thread's narrative.
- Check that the trigger can happen: follow the callers and the guards before the line.
- For a broken rule, check that the rule says what the finding claims and that the line breaks it. A rule or quote the thread cites that isn't in the repo is checked with grep and `git log`; not found is evidence for Refuted. For a cut, check the callers, settings, or platform feature it relies on.
- When running code is cheap and allowed, reproduce it: an existing test, a new test, or a short script. Run existing tests in place. Put anything new in a temporary worktree, never the user's tree: `git worktree add --detach <tmp> <rev>`, then `git worktree remove --force <tmp>` after. If it can't run, trace instead.
- Label each finding:
  - Reproduced: something you ran fails at the revision. Evidence is the command and the failing line of output.
  - Traced: you followed it from trigger to wrong result, or from the rule to the line that breaks it, without running anything. Evidence is the file:line steps.
  - Unverified: you can't settle it either way. Evidence is what would.
  - Refuted: evidence is the proof. Either the file:line of the guard or caller that makes the trigger unreachable, a run that passes on the exact trigger, or the search that found no such rule or quote. A passing test counts only if you read it and it asserts the outcome for that trigger; for a scoping or filtering finding, it also needs keys whose correct values differ. A shared fixture that both the correct and broken behavior would satisfy doesn't refute it. Reasoning alone is not a refutation: label it Unverified.
- If running or tracing hasn't settled a finding after three tries, stop: label it Unverified and say what would settle it.
- Change a finding's severity, up or down, only with evidence.

As a subagent, return a JSON list and nothing else, one object per finding:

```json
[{"id": "T1", "label": "Reproduced", "evidence": "`pnpm test tabs -t \"closes last tab\"` fails: expected \"t2\", received null.", "severity": null, "why": null}]
```

Set `severity` and `why` (one line) only when you changed the severity.
