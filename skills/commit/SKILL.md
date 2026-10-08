---
name: commit
description: >
  Stages pending changes and writes one `git commit` whose message matches
  the repo's own commit convention, falling back to Conventional Commits
  (preferably via `npx gitzy`, otherwise hand-written) when the repo has no
  detectable style. Use when the user says "commit", "commit this", "stage
  and commit", "write a commit message", "ship this", a request for commit
  by name, or shares a diff and asks what the commit should say. Not for
  amending (opt-in via "amend"), rewriting history, splitting a change into
  multiple commits, or pushing.
compatibility: Requires git and python3 (body linter); npx and gitzy are optional and used when reachable, with a hand-written fallback otherwise.
---

# commit

## Principle

Detect every value. Sources, highest precedence first:

1. Instructions: the repo's agent docs (`AGENTS.md`, plus agent-specific files such as `CLAUDE.md`, `GEMINI.md`, and `.github/copilot-instructions.md`), then the user's own instructions and saved preferences, in whatever form the agent has them. Repo docs win on conflict; they describe the team.
2. The repo itself: `.gitzyrc*`/`gitzy` config, commitlint config, `.gitmessage`/`commit.template`, commit-msg hooks, and the dominant shape of recent human commits.
3. Fallback: Conventional Commits, built by `npx gitzy commit` when it runs successfully, otherwise hand-written and applied with `git commit -F`. gitzy is a preference for how the fallback message gets produced, never a requirement for the skill to work.

When a source has a convention, follow it. When none does, use the fallback and say so in the confirmation step.

**gitzy is optional.** Try it first on the fallback path (step 5). If `npx gitzy` isn't reachable, no `npx`, no network, the one-time package install prompt can't be answered non-interactively, or the command errors or times out, fall back silently to writing the identical Conventional Commits message by hand and committing with `git commit -F`. Don't block the commit on gitzy being installed; mention once in the confirmation block which path was used ("via gitzy" or "written directly") so the user can tell.

**Attribution line.** If the agent is set up to add a `Co-Authored-By:` trailer, it ranks below all three sources above. Leave it out when any of them says to: agent docs, or a user instruction or preference about attribution, co-author trailers, or AI credit. Otherwise it goes last.

**Auto-commit guard.** This skill never runs `git commit` unless the current user message asked for a commit. A plan, a prior approval, or "looks good" about something else does not count. Step 4 always waits for explicit go-ahead on the commit action itself, every time.

## Process

### 0. Preflight

**Mode.**

- **amend**: the user said "amend", "amend the last commit", or "fix up the last commit".
- **message**: the user asked only "what should the commit say" or "draft a message". Produce text; don't run `git commit` on this path or any other without a go-ahead.
- **create**: otherwise.

```bash
git status --porcelain=v1
git branch --show-current
ls -1 .husky/commit-msg .husky/pre-commit lefthook.yml 2>/dev/null
```

- Nothing staged and nothing unstaged: stop, "nothing to commit".
- Current branch is `main`, `master`, `trunk`, `develop`, or matches `release/*`: stop and ask once before proceeding.
- Note any hook files found. Never pass `--no-verify` unless the user asks.

Read exactly one reference file before running any gitzy or git-write command: [references/gitzy.md](references/gitzy.md). It holds every gitzy flag, the JSON schema, and config-detection gotchas.

### 1. Detect conventions

Run these probes in one turn (parallel, independent). Record each value and its source for step 4.

- **gitzy config**: `.gitzyrc`, `.gitzyrc.{json,js,cjs,mjs}`, `gitzy.config.{js,cjs,mjs,ts,mts}` (optionally under `.config/`), or a `gitzy` key in `package.json`. Hit: gitzy mode, repo config drives type/scope enums and header/body limits.
- **commitlint config**: `commitlint.config.{js,cjs,mjs,ts}`, `.commitlintrc.{json,js,cjs,mjs,yml}`, or a `commitlint` key in `package.json`. Hit: still gitzy mode, gitzy auto-detects and merges over it (see [references/gitzy.md](references/gitzy.md)). Note the enforced `type-enum`, `scope-enum`, or `header-max-length` if trivially readable.
- **`.gitmessage` / `commit.template`**: `git config --get commit.template` or a `.gitmessage` file. Hit: use it as a body skeleton.
- **commit-msg hook**: if `.husky/commit-msg` or lefthook's commit-msg step runs something other than commitlint or gitzy, surface it and stop before guessing at its rules.
- **Recent commit shape**, bots and merges excluded:

  ```bash
  git log --no-merges --format='%an|%s' -n 50 \
    | awk -F'|' '$1 !~ /\[bot\]/ && $1 !~ /dependabot/ && $1 !~ /renovate/ {print $2}' \
    | head -20
  ```

  Extract the dominant shape: `type(scope):` vs `type:` vs plain English; emoji presence and position (gitzy's own format puts it right after the colon, e.g. `fix(create-pr): 🐛 keep bot blocks`); ticket-id form if any; breaking marker style (`!`, footer, or both); subject casing; imperative check (flag `added`/`fixed`/`updated`/etc.); whether non-trivial commits in the sample carry a body at all, this feeds the body decision in step 3.
- **Ticket id**. Extract from the branch name, then recent commit subjects. Patterns:
  - `[A-Z][A-Z0-9]+-\d+`: Jira or Linear style.
  - `#\d+`: an issue on the host.

  Discard look-alikes such as `UTF-8`, `ISO-8601`, `ES-2015`. Never invent an id.
- **Co-author / attribution policy**: covered by Principle; a user instruction or memory always wins (default: omit).

### 2. Gather context

```bash
git diff --cached --stat
git diff --stat
```

If nothing is staged yet, decide what to stage:

- Tracked-only changes: confirm, then `git add -u`.
- Untracked files present: list them. Flag anything matching `*.env*`, `*secret*`, `*.key`, `*.pem`, `credentials*`, `*.p12`, or anything over 1MB. Wait for the user to approve `git add -A` or name specific paths.

```bash
git diff --cached -- . ':(exclude,glob)**/*.lock' ':(exclude,glob)pnpm-lock.yaml'
```

Use this for subject, scope, and type inference.

**Multi-concern check.** Group the staged diff by top-level directory or package and by whether each group's change is additive, fixing, or mechanical (formatting, deps, config). More than one concern, not just more than one file, means stop before drafting anything. Name each concern found, for example "A: fixes the recent-commit filter in `commit`" and "B: adds the new linter script", and ask the user to pick one, pick several to combine deliberately, or describe their own framing. Never guess a dominant concern and draft against it silently. One coherent concern spread across many files is not a multi-concern diff; don't flag on file count alone.

### 3. Decide the parts

**Type.** Requires an explicit behavior signal, never line or file count alone, this is the single most common way an AI gets `type` wrong.

- `test`: diff is test files only.
- `docs`: diff is docs or comments only.
- `feat`: a new exported function, class, CLI flag, or API surface appears, or a capability a caller didn't have before is added. The diff must show the new surface, not just "a lot changed".
- `fix`: the diff corrects behavior that was wrong, a bug keyword in the branch name or an in-progress message, or an issue reference; or the diff removes or guards a code path that produced an incorrect result. Not "touched a function that has bugs in general".
- `chore` / `refactor`: everything else, including internal restructuring, deps, tooling, config, or formatting with no behavior change. This is the default when neither `feat` nor `fix` has a real signal; never stretch to `feat` or `fix` to seem more substantial.

Must be a member of the detected `type-enum` if one exists.

**Verb/type cross-check.** After drafting the subject, check its leading verb against the chosen type. "add", "support", "introduce" implies `feat`; "correct", "guard", "stop" implies `fix`. If the verb and type disagree, that's a signal the type was guessed wrong, not that the verb needs rewording. Re-derive the type from the behavior signal above before showing step 4.

**Scope.** The single top-level directory under `skills/`, `src/`, or `packages/*` touched. Omit if ambiguous or if repo history shows no scopes.

**Subject.** Imperative mood, matches the repo's casing, under the detected (or gitzy default 50-char) header max. States the effect of the change for a caller or reader, what changed for whom, not the mechanics ("changed function signature") and not a summary of the whole diff when the diff has one coherent concern (the multi-concern check in step 2 runs first).

**Confidence check.** If the diff supports more than one reasonable framing of the same concern (for example "guard against empty input" vs "return early on empty input", same change, different emphasis), or the scope or wording choice is genuinely close, draft 2-3 candidate subjects instead of one, each a complete valid header, and let the user pick or edit. A diff with one obvious effect and one obvious scope gets exactly one subject; don't manufacture alternatives to seem thorough.

**Body.** Optional, and convention decides first. Check step 1's recent-commit sample: if most non-trivial commits (ones whose diff isn't a one-liner) carry a body, draft one to match that habit. If the repo's commits are consistently subject-only, default to no body without asking. Only when neither signal is clear (mixed history, or this is the first commit) and the diff isn't self-evident from the subject alone, ask the user once in step 4: "add a body explaining why?" Never pad a body just to have one. When a body is written: why over what, one or two short lines, specific nouns, no filler.

**Breaking.** Only when a public export, signature, or behavior a caller relies on changed. Use whatever marker style step 1 detected (`!`, footer, or both).

**Issues.** Only if step 1 found a ticket id.

### 4. Confirm inline

Write the drafted message to a file, then lint it. Fix every flagged line and rerun until it exits 0, before showing the user.

```bash
body="$(git rev-parse --git-dir)/COMMIT_BODY.md"
# Write the drafted subject and body to $body here.
python3 <skill-dir>/scripts/lint_commit.py "$body"
```

Each shell command may start a fresh shell, so a variable from one command is gone in the next. Recompute `body` with the same line in every command that uses it. The file sits inside `.git`, so it is never committed.

Print one block, then wait:

```
mode: create | branch: <name> | convention: gitzy (repo config) | conventional (fallback) | <repo custom>
type: fix (behavior signal: corrects recent-commit filter) | scope: commit (touched dir)
message: fix(commit): skip reverts when sampling recent titles
via: gitzy | written directly (gitzy unavailable)
stage: 3 files via `git add -u` | hooks: commit-msg (will run)
```

When step 3 produced 2-3 candidates instead of one, list them numbered in place of the single `message:` line and ask which to use, or let the user supply their own. When step 2's multi-concern check stopped earlier, that question is already answered before this block is printed; this block always reflects one chosen concern.

**Never run `git commit` from this step without an explicit go-ahead in the current turn.** If the user's own message already said "commit this" or "ship it", that message is the go-ahead, print the block and continue to step 5. A plan or an unrelated earlier approval is not enough.

If the user corrects a detected convention, apply it to this commit. If it sounds durable ("we always skip scopes"), offer once to add it to agent docs: the repo's `AGENTS.md` for team conventions, the user's personal agent instructions for personal defaults. Don't write either without a yes.

### 5. Commit

Three paths. Try them in order; each one's failure falls through to the next without stalling on gitzy being present.

- **Custom hook or template gitzy can't satisfy** (flagged in step 0 or 1): skip gitzy entirely. Write to `$body` from step 4 and run `git commit -F "$body"`.
- **gitzy path** (everything else, matched gitzy config or the plain fallback): preview first with `--dry-run --json` during step 4 so the confirmation block already shows the exact header. At commit time:

  ```bash
  npx -y gitzy commit \
    --type "<type>" \
    [--scope "<scope>"] \
    --subject "<subject>" \
    [--body "<body>"] \
    [--breaking "<message>"] \
    [--issue "<id>" ...]
  ```

  If this exits non-zero, times out, or `npx` can't run at all (no npx, no network, install prompt unanswerable), don't retry and don't ask the user to install anything. Fall through to the hand-written path below with the same parts, and note in the final report that gitzy wasn't used.
- **Hand-written fallback** (gitzy unreachable): compose the identical Conventional Commits string (`type(scope): subject`, blank line, body, blank line, footers) into `$body` and run `git commit -F "$body"`. The message format stays the same; only the tool that produced it differs.

`--amend` mode: add `--amend` to the gitzy invocation (it pre-fills from HEAD), or `git commit --amend -F "$body"` on the other two paths.

Never pass `--no-verify` unless asked. Never pass `--co-author` or add a trailer per the Principle's attribution rule.

### 6. Verify

```bash
git log -1 --format='%H%n%s%n%b'
```

Show the subject and first body line. If a hook rejected or rewrote the message, report its output verbatim and stop, don't retry blindly. Delete the `COMMIT_BODY.md` scratch file.

## Voice

- **Specificity over category.** Name the file, symbol, package, or flag. Never "updated things".
- **Effect, not mechanics, and not a diff summary.** The subject says what changed for a caller or reader ("accept optional timeout"), not the implementation step ("changed function signature") and not an umbrella restatement of every file touched.
- **Why is for the reader, not the ticket.** Plain prose, short sentences, concrete nouns, no "This commit introduces".
- **Imperative, lowercase first word**, unless repo history says otherwise.
- **No filler.** No em dashes, en dashes, middle dots, curly quotes, sign-offs, or emoji in the body text (gitzy supplies the type emoji itself when it's the one writing the header).
- **Don't attribute to a role you can't verify.** No "reviewer flagged", "per discussion" unless a named person actually said it.
- **Length scales with the change, then stops.** One or two short body lines; most commits need no body at all.
