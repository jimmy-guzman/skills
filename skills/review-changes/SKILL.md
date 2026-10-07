---
name: review-changes
description: >
  Reviews a code change, the user's own or someone else's, with three
  independent reviewers: bugs, the repo's written standards, and the spec the
  change came from. Tries to disprove every finding and reports only what
  holds, labeled by its evidence. For
  the user's own working change it then applies what they name and
  re-reviews; for anyone else's it leaves each fix as a suggestion a person or
  an agent can act on, and posts findings as PR comments when asked. Use when
  the user asks to review, check, or take a second look at a change: "review
  this", "review my changes", "review our work on this branch", "review PR
  285" or "!482", "review their PR and suggest fixes", "review against
  DESIGN.md" or a guidelines URL, a request for review-changes by name, or
  "is this ready?" after finishing a change. Also use when the user pastes
  review findings from a bot or a person and wants them handled. Not for
  whole-repo audits, writing a PR description, explaining what a diff does,
  or when the user names another review tool.
compatibility: >
  Requires git and python3. A PR by number or URL also needs an authenticated
  gh (GitHub) or glab (GitLab). Runs reviewers as parallel subagents where the
  agent supports them, one at a time otherwise.
---

# review-changes

"PR" below means a GitHub pull request or a GitLab merge request.

If the user pasted findings from a bot or a person, read [references/pasted-findings.md](references/pasted-findings.md) and follow it instead of the process below.

## In any agent

- Paths like `scripts/pr.py` are relative to this skill's directory. Resolve them to absolute paths, and run them with the repo as the working directory.
- To ask the user something, use the agent's question tool if it has one. Otherwise ask in plain text with numbered choices, and wait for the answer.
- In a read-only or planning mode, print everything in the conversation and write no files.

## Gotchas

- `gh pr view` and `glab mr view` don't return thread state or comment anchors. `scripts/pr.py state` does, for both.
- Diff line numbers drift. Take them from the file at the reviewed revision.
- Some shell wrappers condense or truncate long output. Get the raw diff.
- `gh pr diff` and `glab mr diff` don't fetch the head commit, so `git show <sha>:<path>` fails on a PR that isn't checked out. Fetch it first: `git fetch <remote> pull/<n>/head` on GitHub, `git fetch <remote> merge-requests/<n>/head` on GitLab.

## Process

### 1. Pin the diff, read the PR, and pick the mode

First hit wins. The user's words override the order: "this branch" means the branch diff plus anything uncommitted.

1. A PR, commit, or range the user named: `gh pr diff <n>`, `glab mr diff <n>`, or `git diff <range>`.
2. Uncommitted changes: `git diff HEAD`, plus untracked files from `git status --porcelain`, read whole.
3. A clean tree: `git diff <remote>/<base>...HEAD` after `git fetch <remote> <base>`, never the local base. The base is the open PR's base if there is one, else the default branch, on the branch's upstream remote. With no remote or a failed fetch, use the local default branch and say so.

Leave out lockfiles, generated code, snapshots, and vendored files. Confirm the diff is not empty before going further.

For a PR, also run `python3 scripts/pr.py state <pr>`, where `<pr>` is the number, `#285`, `!482`, or the URL. It prints JSON: state, draft, head SHA, title, author, description, open and resolved thread anchors, and `reviewed_at_head`. Keep it for the preflight, the reviewers, and posting. If the script fails, say why, read state and description with `gh pr view` or `glab mr view`, and treat thread state as unknown.

Preflight, PR only. It triggers when any of these hold:

- The PR is closed or merged.
- The PR is a draft, and the user didn't say to review it anyway. Asking for a review, or invoking this skill, doesn't count.
- `reviewed_at_head` is true.
- `threads.open` is above zero.

On a trigger, ask the user to pick one, and name what triggered:

- **Skip**: print the Context-only report from §5. Nothing else runs.
- **Novel only**: review, and pass the thread anchors to the reviewers so findings already raised drop out.
- **Full review**: review as if there were no threads.

When `truncated` is true, say the thread list may be incomplete. No trigger, no question.

Then pick the mode. The user's words win ("just suggest", "don't apply", "for the author"). Otherwise:

- **Apply**: the change is the user's own and sits in the working tree or on the current branch. Report, wait, then §6.
- **Suggest**: anything else, such as someone else's PR, a branch that isn't checked out, or a merged commit. Read files at the head with `git show <sha>:<path>`, edit nothing, and post nothing unless asked. Asked to apply to a head that isn't checked out, say it has to be checked out first.

Novel only filters findings. It doesn't change the mode.

### 2. Find the sources

- **Standards**: `AGENTS.md`, the agent-specific instruction files the repo has (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/`), `CONTRIBUTING.md`, the docs they point to, and any file or URL the user named, as in "review against taste.md".
- **Spec**: issues referenced in the commits or the PR (fetch them), the PR description, a plan file, a path the user passed, and the repo's own spec, design, and decision docs. If there is no issue or plan, say so in the report; the Spec reviewer then checks only the repo's docs against the code.

### 3. Run three reviewers

Each reviewer starts with fresh context: a subagent where the agent has them, all three at once where it can run them in parallel. Give each the diff command, the revision to read at, the mode, its source files, the thread anchors for Novel only, the "All reviewers" block, and its own brief, both pasted in full. Don't give it the conversation: a reviewer who didn't write the change catches what the author explains away.

Without subagents, make the three passes yourself, one at a time. Reread the diff for each pass and judge the code as written, not as you meant it.

**All reviewers**

```text
Read around the diff: the callers of every changed function and the tests that cover them. Take line numbers from the file at the reviewed revision, not from diff output.
Before returning a finding, reread the lines and follow the caller. Drop what doesn't survive that.
Skip anything a linter, formatter, or type checker already enforces.
Never suggest a fix that needs a lint rule disabled, a shorter form that reads worse, or deleting a test because it is small.
A choice the spec made on purpose, which causes no wrong behavior and breaks no rule, is a judgment call, not a finding. A comment calling something deliberate, or older code doing the same, excuses neither wrong behavior nor a broken rule.
Return every finding, worst first, with: file:line; the one line of code it rests on, quoted exactly; the trigger, as concrete inputs or state; what the code does; what the user ends up seeing; the fix, as a diff when it is a few lines; and anything you ran, with the command.
List judgment calls and problems the diff didn't cause separately, one line each.
When existing thread anchors are passed in (file:line and first line), drop any finding that matches one on file:line and subject, unless you materially extend it.
```

**Bugs: what the code does**

```text
Find wrong behavior: missed edge cases (empty, last item, concurrent, failure path), errors swallowed where they should fail loud, data loss, unchecked input at a trust boundary, missing or flaky tests for new logic, and claims ("faster", "fixes the flake") with no measurement or failing test behind them.
Find fixes that patch a symptom: the same guard in several places, a special case for the one path the report named, a pinned version or disabled check standing in for a fix. Point at the shared cause.
For each async call the diff adds: what happens if the thing it belongs to changed, or the user acted, before it settled?
For each new handler, key binding, or route: can input reach it, or does an earlier branch take it first?
When the change adds or leans on a dependency, check what it actually does: run it, or read the source of the pinned version for the defaults the change relies on.
```

**Standards: the written rules**

```text
Walk the rules in the source files one at a time against each changed file. Report every break and name the file and the rule. A break is a finding even when older code does the same, and so is a new lint suppression.
Then apply this baseline, which any repo rule overrides:
- Cuts. Code the change adds that doesn't need to exist: dead code, options nobody sets, an abstraction with one implementation, a layer with one caller, hand-rolled code the standard library or platform ships, a dependency added for what a few lines do, compatibility shims with nothing to be compatible with, and code working around a framework the repo already uses where it has the feature built in. Return each cut as one line: file:line, a tag (delete, stdlib, native, yagni, or shrink), what replaces it, and how many lines it removes.
- Comments. A comment that restates the code goes. If the code doesn't tell the story, the fix is the code (a name, a smaller function), not a comment. A comment stays when it carries what the code can't: why, a non-obvious fix, or a doc comment stating a contract. A comment should read correctly to someone with only the file.
```

**Spec: what was asked for**

```text
Compare the diff with the spec sources and name the line each finding rests on. Report what the spec asked for that is missing or partial, behavior nobody asked for (unrelated config edits, a refactor riding along with a fix), and what looks implemented but is wrong.
Then check the words against the code: every factual claim the diff adds to docs or comments, and every doc that described behavior the diff changed (grep for it). Docs should be plain, factual, and short; flag filler, restated rationale, and em dashes.
```

When the user asks for a thorough review, run the Bugs reviewer twice, each with fresh context, and merge both lists. Two runs catch bugs one run misses, and §4 removes what doesn't hold.

### 4. Verify every finding

The reviewer that found an issue is the worst judge of it. Before reporting, check each finding.

1. Merge duplicates into the group that found the cause. A bug and a cut on the same lines are one finding. Write the findings to a temp JSON file (`id`, `path`, `line`, `quote`) and run `python3 scripts/check_quotes.py --rev <sha> <file>`. Leave out `--rev` for uncommitted changes. Fix the line of a `moved` finding. For a `missing` one, re-quote once from the `near` lines the script prints and rerun; drop it only if it's still missing. Drop a `no-file` one. Exit 1 only means something needs fixing.
2. Hand the survivors, cuts included, to a verifier with fresh context: a subagent where the agent has them, several findings per verifier when there are many. Give it the findings, the revision, the mode, and the brief below. Don't give it the reviewer's reasoning or the conversation. Without subagents, verify each finding yourself, one at a time, starting from the quoted line rather than the reviewer's explanation.
3. Keep Reproduced and Traced findings. Refuted and Unverified findings go to the left-out count in §5 with their reasons, beside the reviewers' judgment calls.

**Verifier**

```text
You get findings from another reviewer. For each one, try to prove it wrong before you accept it, and judge each on its own.
Check that the trigger can happen: follow the callers and the guards before the line.
For a broken rule, check that the rule says what the finding claims and that the line breaks it. For a cut, check the callers, settings, or platform feature it relies on.
When running code is cheap, reproduce it: an existing test, a new test, or a short script. Run existing tests in place. Put anything new in a temporary worktree, never the user's tree: `git worktree add --detach <tmp> <rev>`, then `git worktree remove --force <tmp>` after. For uncommitted changes the revision is the output of `git stash create` (HEAD if it prints nothing), plus the untracked files from the diff copied in. If the worktree can't run, for example dependencies are missing, trace instead.
Return one label per finding, with evidence:
- Reproduced: something you ran fails at the revision. Give the command and the failing line of output.
- Traced: you followed it from trigger to wrong result, or from the rule to the line that breaks it, without running anything. Give the file:line steps.
- Unverified: you can't settle it either way. Say what would.
- Refuted: cite the proof. Either the file:line of the guard or caller that makes the trigger unreachable, or a run that passes on the exact trigger. A passing test counts only if you read it and it asserts the outcome for that trigger. Reasoning alone is not a refutation: label it Unverified.
Change a finding's severity, up or down, only with evidence, and say why in one line.
```

### 5. Report and stop

Group the findings by reviewer in this order: Bugs, Standards, Spec, Cuts. Number straight through so "apply 1-4" spans groups, and don't rerank across groups.

Each finding has:

- A title that is the fix, as a command.
- A label line: category | severity | effort | evidence.
- `file:line`.
- Up to three plain sentences: what triggers it, what the code does, what the user ends up seeing. Then the fix. A Standards or Spec finding names its source in a few words, with no quote.
- An `Evidence:` line: the command and the failing output for Reproduced, or the file:line steps for Traced. Leave it out when the prose already shows the whole path. When §4 changed the severity, say why here.
- A diff of the fix when it is a few lines. A heavy lift gets the approach in a sentence. In Suggest mode, name the file, the symbol, and the change precisely enough that someone without this conversation can make it.

Labels:

- Category: Functional Correctness, Data Integrity & Integration, Stability & Availability, Security & Privacy, Performance & Scalability, or Maintainability & Code Quality. Pick by what goes wrong for the user. Broken rules that don't change behavior, comments, scope creep, and missing tests are Maintainability & Code Quality.
- Severity: Critical is data loss, a security hole, or a crash, on a path users commonly take. Major is wrong behavior a user will hit, or a failure with no way back. Minor is everything else, including faults that are rare or cosmetic. Most findings are Minor.
- Effort: Quick win is a contained change of a few lines. Heavy lift needs a design decision.
- Evidence: Reproduced or Traced, from §4. Nothing else reaches the numbered list.

```text
Reviewed: uncommitted changes (6 files, lockfile left out) against AGENTS.md and issue #41. Ran the tab tests; nothing else was run.

Bugs
1. Fall back to the previous tab when the last one closes
   Functional Correctness | Major | Quick win | Reproduced
   `src/store/tabs.ts:88`
   Closing the last tab reads `next[index]`, which is past the end after the removal. The app is left with tabs open and none active.
   Evidence: `pnpm test tabs -t "closes last tab"` fails: expected "t2", received null.

   -  const active = next[index] ?? null;
   +  const active = next[Math.min(index, next.length - 1)] ?? null;

Standards
2. Delete the comment that restates the code
   Maintainability & Code Quality | Minor | Quick win | Traced
   `src/store/tabs.ts:70-74`
   AGENTS.md allows doc comments only, and this one repeats the next four lines.

Spec
3. Keep the tab's scroll position, which the issue asks for
   Functional Correctness | Minor | Heavy lift | Traced
   `src/store/tabs.ts:40`
   Issue #41 asks for scroll and caret to survive a tab switch. The change saves the caret only, so switching back lands at the top. Store `scrollTop` beside the caret in `TabState` and restore both in `activate`.
   Evidence: `activate` (`tabs.ts:52`) restores the caret only, and `TabState` (`types.ts:12`) has no scroll field.

Cuts
4. `src/lib/retry.ts:1-40` yagni: retry wrapper around a local, idempotent call with one caller. Call `readNote` directly.

Worth an issue
- `src/editor/find.ts:52`: hidden matches show "0 / 0" in source mode. Not from this change.

Left out: 1 judgment call, 2 unverified, 1 refuted. Say "show left out" to see them.
net: -40 lines possible.
Say "apply", or name the numbers.
```

`net` counts only what the cuts delete. Leave out any group or line that is empty. With nothing to report, write the `Reviewed:` line, the `Left out:` line if it has anything, and `Lean already. Ship.`

The report holds only what to act on. Judgment calls, unverified, and refuted findings get no section of their own; the `Left out:` line counts each kind. "Worth an issue" lists at most three; the rest show in that line as "N more worth an issue". On "show left out", print each one as a single line: `file:line`, its kind, and why. For an unverified one, say what would settle it. For a refuted one, give the proof.

Don't trim the report. When it runs past eight numbered items, add this above the last line, and treat what the user keeps as the list:

```text
This is long. Anything to cut? For example "drop the Minor ones", "bugs only", or numbers.
```

In Suggest mode the report must stand alone, because it gets handed to the author or pasted to their agent. Don't refer to the conversation, reprint it after any cut, and replace the last line:

```text
Nothing applied. For an agent: verify each item against the current code, fix the ones that still hold, and skip the rest with a one-line reason.
```

With Novel only, title the report `Supplemental review (<N> existing threads skipped)`, and add this above the mode's last line:

```text
Existing threads cover prior rounds; the findings above are novel only.
```

When the preflight picked Skip, the report is only the PR's state:

```text
Context-only: <state> PR <ref>, head <short_sha>
Title: <title>
Author: <author>
Threads: <open> open, <resolved> resolved. Last review: <short sha from reviewed_shas, or "none">.

No review run.
```

Then stop. Don't edit anything yet. If the user asks to post, see §7.

### 6. Apply and re-review

Apply mode only. "apply" means every numbered item still on the list; "apply 1-4" or "all except 3" means those. Judgment calls and issues are only acted on when named.

- Keep each change minimal. A bug fix gets a test that fails without it, when the repo has tests. If §4 reproduced the bug with a new test, bring that test over.
- Run the repo's own checks afterward. Find them in agent docs first, then in the scripts of `package.json`, `Makefile`, `justfile`, or the equivalent.
- Re-review only what you just changed, with the same three briefs and the §4 verification, and report by number. New findings take the §5 shape and continue the numbering.

```text
Applied 1-3. Not applied: 4.
Closed: 1, 2. Added a test for 1.
Still open: 3. Scroll is restored, but only after the first paint, so the view jumps.

Ran `pnpm check` and `pnpm test`: both pass.
```

Then stop again, and say what you didn't run. On "apply until clean", keep applying new findings and re-reviewing without stopping, three rounds at most, then report what is left.

Never commit, push, switch branches, or open a PR. File an issue only after a yes.

### 7. Post findings as comments

Only when the user asks ("post these", "comment on the PR", "leave inline"). Read [references/posting.md](references/posting.md) first and follow it.
