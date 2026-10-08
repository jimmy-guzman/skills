# Bugs: what the code does

Read [reviewer-common.md](reviewer-common.md) first.

- Read the callers of every changed function and the tests that cover them, always, before judging a change.
- Find wrong behavior: missed edge cases (empty, last item, concurrent, failure path), errors swallowed where they should fail loud, data loss, unchecked input at a trust boundary, missing or flaky tests for new logic, and claims ("faster", "fixes the flake") with no measurement or failing test behind them.
- Find fixes that patch a symptom: the same guard in several places, a special case for the one path the report named, a pinned version or disabled check standing in for a fix. Point at the shared cause.
- For each async call the diff adds: what happens if the thing it belongs to changed, or the user acted, before it settled?
- For each new handler, key binding, or route: can input reach it, or does an earlier branch take it first?
- When the change adds or leans on a dependency, check what it actually does: run it, or read the source of the pinned version for the defaults the change relies on.
