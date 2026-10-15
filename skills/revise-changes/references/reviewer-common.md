# Finding shape

The shape [extraction.md](extraction.md) produces per thread, and [reviewer-verifier.md](reviewer-verifier.md) judges. Adapted from review-changes' reviewer-common.md: revise-changes has no reviewer subagents, so only the output shape carries over, not the reviewer behavior rules.

```json
{
  "id": "T1",
  "path": "src/store/tabs.ts",
  "line": "88",
  "quote": "const active = next[index] ?? null;",
  "removed": false,
  "severity": "Major",
  "effort": "Quick win",
  "trigger": "Closing the last tab.",
  "does": "Reads `next[index]`, which is past the end after the removal.",
  "sees": "Tabs open and none active.",
  "fix": "-  const active = next[index] ?? null;\n+  const active = next[Math.min(index, next.length - 1)] ?? null;",
  "ran": null,
  "probe": null
}
```

- `id`: `T` plus the thread's order (`T1`, `T2`, ...).
- `path` and `line`: null for a thread with no file anchor (a general comment). `line` is N or N-M at the thread's position; note separately when it no longer matches current HEAD.
- `quote`: the one line of code the finding rests on, read fresh at current HEAD, exactly. For removed code, the line at the revision where it used to sit, with `removed` true.
- `severity`: Critical is data loss, a security hole, or a crash on a path users commonly take. Major is wrong behavior a user will hit, or a failure with no way back. Minor is the rest, and most findings.
- `effort`: Quick win is a contained change of a few lines. Heavy lift needs a design decision.
- `trigger`, `does`, `sees`: concrete inputs or state, what the code does, what the user ends up seeing. One sentence each, paraphrased from the thread.
- `fix`: a diff when the thread proposed one and it's a few lines, otherwise the approach in a sentence, or null when the thread made no concrete proposal.
- `ran`: the command and result if already run, or null.
- `probe`: `{"inputs": [...], "expected": "...", "why": "..."}` when there's something to run or trace you didn't settle yourself, null otherwise.
