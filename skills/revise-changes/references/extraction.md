# Extraction

Read this in SKILL.md §3, once per unresolved thread. Turns one thread's prose into the finding shape [reviewer-common.md](reviewer-common.md) defines, for that same section's verifier.

- Apply the user's exclusions first ("ignore the duplicate-code one and the speculative-generality one"). An excluded thread never gets extracted or verified: it becomes a `Skipped (user excluded)` line in the final report.
- No rigid parser. Read the thread's full notes and map by hand:
  - `id`: synthesized in thread order (`T1`, `T2`, ...), not the provider's own id.
  - `path`, `line`: the thread's position. Note when the anchor's line no longer matches the file at the current HEAD; the verifier gets both the anchor and the current line.
  - `quote`: re-read from the file at the **current** HEAD, not the SHA the comment was left against. The branch may have moved since the comment was posted.
  - `trigger`, `does`, `sees`: paraphrase from the comment body, one sentence each, same as a reviewer would write them.
  - `fix`: only if the comment proposed one, as a diff or a one-sentence approach. Leave null otherwise; the verifier and the fix step work from the claim, not a parroted suggestion.
  - `severity`/`effort`: assign the same way [reviewer-common.md](reviewer-common.md) defines them, from your own read of the claim. A thread rarely states these explicitly.
- Every thread gets a finding, bot-authored or human, verified the same way. No separate bar for either.
- A thread whose claim cites a rule, quote, or fact that doesn't exist in the repo (a fabricated standard, a misquoted line) still gets extracted and sent to verification. It should come back **Refuted** there, with evidence like "no such text found via grep + git log", never silently dropped before verification.
- Misreading a human's intent is a real risk with no rigid schema to catch it. The mitigation is downstream, not here: a misextracted finding fails to reproduce in §3 and gets caught as Unverified or Refuted, same as a reviewer's bad finding would.
