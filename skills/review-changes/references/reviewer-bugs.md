# Bugs: what the code does

Read [reviewer-common.md](reviewer-common.md) first.

- Read the callers of every changed function and the tests that cover them, always, before judging a change.
- Find wrong behavior: missed edge cases (empty, last item, concurrent, failure path), errors swallowed where they should fail loud, data loss, unchecked input at a trust boundary, missing or flaky tests for new logic, and claims ("faster", "fixes the flake") with no measurement or failing test behind them.
- For numeric, tiered, or branchy logic, don't compute outcomes by hand: pick the boundary set (zero, the minimum, the maximum, each threshold exactly, and one past it) and run the function on those inputs the way [reviewer-verifier.md](reviewer-verifier.md) does (existing tests in place, anything new in a temporary worktree) — but only when the call is side-effect-free there (no DB write, billing, notification, or other call outside the process) and cheap to set up (a short, direct call, not one needing framework reactivity, async orchestration, or an environment rebuilt first); a worktree isolates files, not external calls or setup cost. In Suggest mode, only if the user allowed running their code. Otherwise, or when you have a concrete reason to suspect a boundary is wrong but haven't settled it, put it in `probe` with the reason in `does` instead of hand-tracing it — don't probe every boundary, only the ones you suspect.
- Find fixes that patch a symptom: the same guard in several places, a special case for the one path the report named, a pinned version or disabled check standing in for a fix. Point at the shared cause.
- For each async call the diff adds: what happens if the thing it belongs to changed, or the user acted, before it settled?
- For each new handler, key binding, or route: can input reach it, or does an earlier branch take it first?
- When the change adds or leans on a dependency, check what it actually does: run it, or read the source of the pinned version for the defaults the change relies on.
