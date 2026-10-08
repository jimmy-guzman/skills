# Reviewer briefs

Briefs for the reviewers in SKILL.md §3 and the verifier in §4. A reviewer reads "All reviewers", its own section, and "Reviewer output". A verifier reads only "Verifier".

## All reviewers

- Read around the diff: the callers of every changed function and the tests that cover them. Take line numbers from the file at the reviewed revision, not from diff output.
- Before returning a finding, reread the lines and follow the caller. Drop what doesn't survive that.
- Skip anything a linter, formatter, or type checker already enforces.
- Never suggest a fix that needs a lint rule disabled, a shorter form that reads worse, or deleting a test because it is small.
- A choice the spec made on purpose, which causes no wrong behavior and breaks no rule, is a judgment call, not a finding. A comment calling something deliberate, or older code doing the same, excuses neither wrong behavior nor a broken rule.
- When existing thread anchors are passed in (file:line and first line), drop any finding that matches one on file:line and subject, unless you materially extend it.
- Return every finding, worst first, as in "Reviewer output".

## Bugs: what the code does

- Find wrong behavior: missed edge cases (empty, last item, concurrent, failure path), errors swallowed where they should fail loud, data loss, unchecked input at a trust boundary, missing or flaky tests for new logic, and claims ("faster", "fixes the flake") with no measurement or failing test behind them.
- Find fixes that patch a symptom: the same guard in several places, a special case for the one path the report named, a pinned version or disabled check standing in for a fix. Point at the shared cause.
- For each async call the diff adds: what happens if the thing it belongs to changed, or the user acted, before it settled?
- For each new handler, key binding, or route: can input reach it, or does an earlier branch take it first?
- When the change adds or leans on a dependency, check what it actually does: run it, or read the source of the pinned version for the defaults the change relies on.

## Standards: the written rules

- Walk the rules in the source files one at a time against each changed file. Report every break and name the file and the rule. A break is a finding even when older code does the same, and so is a new lint suppression. Count what you walked for `coverage`.
- Then apply this baseline, which any repo rule overrides:
  - Cuts. Code the change adds that doesn't need to exist: dead code, options nobody sets, an abstraction with one implementation, a layer with one caller, hand-rolled code the standard library or platform ships, a dependency added for what a few lines do, compatibility shims with nothing to be compatible with, and code working around a framework the repo already uses where it has the feature built in. Return them in `cuts`.
  - Comments. A comment that restates the code goes. If the code doesn't tell the story, the fix is the code (a name, a smaller function), not a comment. A comment stays when it carries what the code can't: why, a non-obvious fix, or a doc comment stating a contract. A comment should read correctly to someone with only the file.

## Spec: what was asked for

- Compare the diff with the spec sources and name the line each finding rests on. Unrelated config edits and a refactor riding along with a fix are scope creep.
- Then check the words against the code: every factual claim the diff adds to docs or comments, and every doc that described behavior the diff changed (grep for it). Docs should be plain, factual, and short; flag filler, restated rationale, and em dashes.
- Answer each question in `verdicts` with the ids of the findings that answer it, or "none" plus one sentence on what you checked. A bare "none" is not an answer.
  - Completeness: is anything the spec asked for not done?
  - Scope: did anything change that the spec didn't ask for?
  - Correctness: does anything built behave unlike the spec?
  - Consistency (only when the diff touches docs or documented behavior): do they disagree?

## Reviewer output

Return one JSON object and nothing else: no preamble, no summary, no code fence. The main agent reads it as data, and every extra word costs its context.

```json
{
  "findings": [
    {
      "id": "B1",
      "path": "src/store/tabs.ts",
      "line": "88",
      "quote": "const active = next[index] ?? null;",
      "removed": false,
      "severity": "Major",
      "effort": "Quick win",
      "source": null,
      "trigger": "Closing the last tab.",
      "does": "Reads `next[index]`, which is past the end after the removal.",
      "sees": "Tabs open and none active.",
      "fix": "-  const active = next[index] ?? null;\n+  const active = next[Math.min(index, next.length - 1)] ?? null;",
      "ran": "`pnpm test tabs -t \"closes last tab\"` fails: expected \"t2\", received null."
    }
  ],
  "cuts": [
    {"id": "C1", "path": "src/lib/retry.ts", "line": "1-40", "quote": "export async function withRetry(", "tag": "yagni", "replace": "Call `readNote` directly."}
  ],
  "left_out": ["src/editor/find.ts:52: not from this change: hidden matches show \"0 / 0\" in source mode."]
}
```

- `id`: B, S, or P (Spec), plus a number. Cuts use C.
- `path` and `line`: null for a finding with no file, such as an empty description. `line` is N or N-M at the reviewed revision.
- `quote`: the one line of code the finding rests on, exactly. For removed code, the line at the revision where it used to sit, with `removed` true.
- `severity`: Critical is data loss, a security hole, or a crash on a path users commonly take. Major is wrong behavior a user will hit, or a failure with no way back. Minor is the rest, and most findings.
- `effort`: Quick win is a contained change of a few lines. Heavy lift needs a design decision.
- `source`: Standards and Spec only, the rule or spec line in a few words.
- `trigger`, `does`, `sees`: concrete inputs or state, what the code does, what the user ends up seeing. One sentence each.
- `fix`: a diff when it is a few lines, otherwise the approach in a sentence. `ran`: the command and result, or null.
- `tag`: delete, stdlib, native, yagni, or shrink.
- `left_out`: judgment calls and problems the diff didn't cause, one string each: file:line, kind, why.
- Standards adds `"coverage": "Walked 12 rules from AGENTS.md against 6 changed files."`
- Spec adds `"verdicts"`: `{"Completeness": ["P1"], "Scope": "none: only tabs.ts and types.ts change."}` and so on.
- Keep every key, with empty lists when there's nothing.

## Verifier

- You get findings from another reviewer. For each one, try to prove it wrong before you accept it, and judge each on its own.
- Check that the trigger can happen: follow the callers and the guards before the line.
- For a broken rule, check that the rule says what the finding claims and that the line breaks it. For a cut, check the callers, settings, or platform feature it relies on.
- When running code is cheap and allowed, reproduce it: an existing test, a new test, or a short script. In Suggest mode, run nothing unless you were told the user allowed it. Run existing tests in place. Put anything new in a temporary worktree, never the user's tree: `git worktree add --detach <tmp> <rev>`, then `git worktree remove --force <tmp>` after. For uncommitted changes the revision is the output of `git stash create` (HEAD if it prints nothing), plus the untracked files from the diff copied in. If it can't run, trace instead.
- Label each finding:
  - Reproduced: something you ran fails at the revision. Evidence is the command and the failing line of output.
  - Traced: you followed it from trigger to wrong result, or from the rule to the line that breaks it, without running anything. Evidence is the file:line steps.
  - Unverified: you can't settle it either way. Evidence is what would.
  - Refuted: evidence is the proof. Either the file:line of the guard or caller that makes the trigger unreachable, or a run that passes on the exact trigger. A passing test counts only if you read it and it asserts the outcome for that trigger. Reasoning alone is not a refutation: label it Unverified.
- Change a finding's severity, up or down, only with evidence.

Return a JSON list and nothing else, one object per finding:

```json
[{"id": "B1", "label": "Reproduced", "evidence": "`pnpm test tabs -t \"closes last tab\"` fails: expected \"t2\", received null.", "severity": null, "why": null}]
```

Set `severity` and `why` (one line) only when you changed the severity.
