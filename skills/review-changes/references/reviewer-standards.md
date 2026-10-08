# Standards: the written rules

Read [reviewer-common.md](reviewer-common.md) first.

- Walk the rules in the source files one at a time against each changed file, skipping rules that don't apply to that file's type (no CSS rules against a Python-only diff). Report every break and name the file and the rule. A break is a finding even when older code does the same, and so is a new lint suppression. Count only the rules you actually walked for `coverage`.
- Read callers only when a cut's claim depends on them ("one caller", "nobody sets it").
- Then apply this baseline, which any repo rule overrides:
  - Cuts. Code the change adds that doesn't need to exist: dead code, options nobody sets, an abstraction with one implementation, a layer with one caller, hand-rolled code the standard library or platform ships, a dependency added for what a few lines do, compatibility shims with nothing to be compatible with, and code working around a framework the repo already uses where it has the feature built in. Return them in `cuts`.
  - Comments. A comment that restates the code goes. If the code doesn't tell the story, the fix is the code (a name, a smaller function), not a comment. A comment stays when it carries what the code can't: why, a non-obvious fix, or a doc comment stating a contract. A comment should read correctly to someone with only the file.

## When you're told Spec isn't running

The orchestrator tells you when there's no issue, plan, or PR description to review against (SKILL.md §3, rule 2). In that case, also do Spec's docs-vs-code check: every factual claim the diff adds to docs or comments, and every doc that described behavior the diff changed (grep for it). Docs should be plain, factual, and short; flag filler, restated rationale, and em dashes. Answer the Consistency question in your own `verdicts`, the same shape Spec would use: the ids of the findings that answer it, or "none" plus one sentence on what you checked.
