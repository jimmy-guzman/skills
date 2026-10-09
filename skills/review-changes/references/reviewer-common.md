# Reviewer common ground

Read by every reviewer in SKILL.md §3, alongside its own role file.

## All reviewers

- Read the diff and the changed files at the reviewed revision. Take line numbers from the file at the reviewed revision, not from diff output.
- Before returning a finding, reread the lines and follow the caller. Drop what doesn't survive that.
- Skip anything a linter, formatter, or type checker already enforces.
- Never suggest a fix that needs a lint rule disabled, a shorter form that reads worse, or deleting a test because it is small.
- A choice the spec made on purpose, which causes no wrong behavior and breaks no rule, is a judgment call, not a finding. A comment calling something deliberate, or older code doing the same, excuses neither wrong behavior nor a broken rule.
- When existing thread anchors are passed in (file:line and first line), drop any finding that matches one on file:line and subject, unless you materially extend it.
- Cap yourself at three tries for anything unsettled, finding or not: reconciling two sources, tracing a lead, reproducing a result. Stop at three. Return it with what would settle it (an input, for Bugs; a file or line, for Standards or Spec), in `probe` if there's something left to run or trace, `left_out` otherwise.
- Return every finding, worst first, as in "Reviewer output".

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
      "ran": "`pnpm test tabs -t \"closes last tab\"` fails: expected \"t2\", received null.",
      "probe": null
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
- `probe`: `{"inputs": [...], "expected": "...", "why": "..."}` when you want the verifier to run or trace something you didn't settle yourself, null otherwise. `why` is the concrete reason to suspect this input, not every boundary gets one.
- `tag`: delete, stdlib, native, yagni, or shrink.
- `left_out`: judgment calls and problems the diff didn't cause, one string each: file:line, kind, why.
- Standards adds `"coverage": "Walked 12 rules from AGENTS.md against 6 changed files."`, and, when covering for a Spec reviewer that isn't running, `"verdicts": {"Consistency": [...]}`.
- Spec adds `"verdicts"`: `{"Completeness": ["P1"], "Scope": "none: only tabs.ts and types.ts change."}` and so on.
- Keep every key, with empty lists when there's nothing.
