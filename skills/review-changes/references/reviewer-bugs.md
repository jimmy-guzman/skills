# Bugs: what the code does

Read [reviewer-common.md](reviewer-common.md) first.

- Read the callers of every changed function, the functions it calls, and the tests that cover them, always, before judging a change.
- Find wrong behavior: missed edge cases (empty, last item, concurrent, failure path), errors swallowed where they should fail loud, data loss, unchecked input at a trust boundary, missing or flaky tests for new logic, and claims ("faster", "fixes the flake") with no measurement or failing test behind them.
- Security, by name: injection (SQL, shell, path, template), weak randomness for anything secret, secrets in code or logs, and input from users or the network used before it is checked.
- Scale. Find the load the repo expects (README, deploy config, test fixtures): one person running a script, or many users and processes at once. Judge against that load, and return it as `load` (see [reviewer-common.md](reviewer-common.md)). Check for: a check-then-write that races under two callers, work every process repeats that one could do, a list or map that only grows, a query or request per item, O(n²) on input that can be big, and state kept per process that must be shared.
- Speed. A change that makes a common path much slower is a finding. Work repeated in a hot loop is Minor; §5 puts it under Nice to have.
- For a fix that scopes or filters data per key (per layer, per request, per user, per geometry, and so on), check that its test has a case where two keys would produce different correct values. A fixture where every key's correct answer is the same can't tell a correctly scoped fix from one still pooling data across keys; flag that as a missing test, not a passing one.
- For numeric, tiered, or branchy logic, don't compute outcomes by hand. Pick the boundary set: zero, the minimum, the maximum, each threshold exactly, and one past it.
- Run only a scratch call of the function on that set, in a temporary worktree as [reviewer-verifier.md](reviewer-verifier.md) describes, and only when the call is side-effect-free (no DB write, billing, notification, or other call outside the process), cheap to set up, and running is allowed (in Suggest mode, only if the user allowed it). Never run the existing test suite or reproduce findings: §4 does that.
- Otherwise, or when you suspect a boundary but haven't settled it, put it in `probe` with the reason. Probe only boundaries you have a concrete reason to suspect.
- Find fixes that patch a symptom: the same guard in several places, a special case for the one path the report named, a pinned version or disabled check standing in for a fix. Point at the shared cause.
- For each state, field, or flag the diff adds: find every consumer, and every place that copies or clones the thing holding it, and check each one sets it or handles it unset.
- For each async call the diff adds: what happens if the thing it belongs to changed, or the user acted, before it settled?
- For each new handler, key binding, or route: can input reach it, or does an earlier branch take it first?
- When the change adds or leans on a dependency, check only the specific behavior it relies on: the pinned version's docs or changelog first, its source only if those don't cover it. Don't re-derive the library's general semantics (event bubbling, lifecycle, scheduling) from first principles. If the specific check doesn't settle in [reviewer-common.md](reviewer-common.md)'s three tries, drop it into `probe` or `left_out`.
