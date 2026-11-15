# Evidence

Read at §3, for evidence the session can't supply. The before runs in a worktree; nothing here changes the user's files.

## Contents

- Worktrees
- Dependencies
- Tests
- Screens
- Workloads and output
- Clean up

## Worktrees

`<head>` below is `HEAD` in create and update. In describe mode, once the user said yes, fetch the PR head to a named ref (`+pull/<n>/head:refs/remotes/<remote>/pr-<n>` on GitHub, `+merge-requests/<n>/head:refs/remotes/<remote>/mr-<n>` on GitLab) and use that ref. A PR in a repo with no local clone gets no evidence; say so in §5.

The before runs at the merge base, in a detached worktree inside `<tmp>`:

```bash
git merge-base <remote>/<base> <head>
git worktree add --detach <tmp>/base <merge-base>
```

The after runs in the user's tree for create and update, the way any test run does: §0 checked it is clean and at `HEAD`. Describe mode adds a second worktree at `<tmp>/head` from the fetched ref.

## Dependencies

A worktree has no installed dependencies. Install them fresh in each worktree with the repo's package manager and its frozen-lockfile flag. Never link them from the main tree: workspace packages and editable installs resolve through a link to the main tree's source, so the before would run the after's code.

Build output (`target/`, `dist/`, `.next/`) is not a dependency: let the build make it.

## Tests

1. Copy the new and changed test files from `<head>` into the base worktree at the same paths, with any fixture they read that is new in the diff.
2. Run only those tests with the repo's own test command, at base and then at the after.
3. Keep each command and its one deciding line: the failure at base, the pass after.

A pass at base means the test doesn't pin the fix. A failure at base for another reason (an import of code that doesn't exist yet, a missing fixture) isn't the bug either: say what failed, and don't call it evidence.

For a refactor, run the existing tests that cover the moved code, unchanged, on both sides.

## Screens

Launch the app with what the repo has, first hit wins: a story or e2e scenario for the state, a project skill or agent doc that says how to run it, the dev script. When none says how, ask the user once.

1. List each affected state: route, dialog, breakpoint, theme. A shared component or global style needs several consumers, not one.
2. Capture each state at base and after with the same viewport, theme, locale, data, and ready condition. Demo data only, never real user content.
3. Save to `<tmp>/shots/base/<id>.png` and `<tmp>/shots/head/<id>.png`.
4. Look at every image. Retake a blank, loading, error, or wrong-page capture unless that state is the change.
5. A state new in this change has no before; a removed one has no after. Say so in the body.
6. Stop every server you started.

The host reference file says how the images get into the body.

## Workloads and output

The same command with the same input on both sides. A timing runs at least three times a side; report the median. Paste output as captured, never retyped.

## Clean up

Once the runs finish, and before §6: `git worktree remove --force <tmp>/base`, and `<tmp>/head` if there is one. §7 deletes `<tmp>`.
