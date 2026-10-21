---
name: commit-changes
description: >
  Stages pending changes and writes one `git commit` whose message matches
  the repo's own commit convention, falling back to Conventional Commits when
  the repo has no detectable style. Use when the user says "commit", "commit
  this", "stage and commit", "write a commit message", "ship this", a request
  for commit-changes by name, or shares a diff and asks what the commit should
  say. Not for amending (opt-in via "amend"), rewriting history, splitting a
  change into multiple commits, or pushing.
compatibility: Requires git and python3.
---

# commit-changes

## Principle

Detect every value. Sources, highest precedence first:

1. Instructions: the repo's agent docs (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`), then the user's own instructions and saved preferences. Repo docs win on conflict.
2. The repo: what `detect.py` reports (hooks, gitzy and commitlint config, commit template, recent human commits). Config is read, never run.
3. Fallback: Conventional Commits, written by hand. Say so in the confirmation block.

This covers the `Co-Authored-By:` trailer too: instructions first, then whether human commits carry one (`co-author N/20`), then append it if the sample is empty.

**Go-ahead.** Run `git commit` only when the current user message asked for a commit. A plan or an earlier approval of something else does not count. Never pass `--no-verify` unless asked.

## Process

### 1. Detect

**Mode.** `amend` when the user said "amend" or "fix up the last commit". `message` when they asked only what the commit should say: produce text, never commit. Otherwise `create`.

```bash
python3 <skill-dir>/scripts/detect.py
```

Stop and ask once when it shows: `changes: nothing to commit`, `(protected)` branch, `commit-msg: custom (...)` (show the command, don't guess its rules), any `untracked` files, or a `secret?` / `>1MB` flag. Otherwise carry on with no stop.

### 2. Read the diff

What gets committed: the staged files, or all tracked changes (`git add -u`) if nothing is staged.

```bash
git diff --cached -- . ':(exclude,glob)**/*.lock' ':(exclude,glob)pnpm-lock.yaml'
```

Use `git diff HEAD` with the same excludes when nothing is staged.

**Multi-concern check.** Group the diff by top-level directory and by kind (adds, fixes, mechanical). More than one concern means stop: name each ("A: fixes the recent-commit filter", "B: adds the linter script") and let the user pick one, combine on purpose, or reframe. Many files with one concern is fine.

### 3. Decide the parts

**Type.** Classify by the effect on whoever consumes the change (a caller, a CLI user, a doc reader, an agent following a skill), never by file type or line count. A markdown-only diff can be `feat`; a `src/` diff can be `chore`.

- `feat`: a consumer gains something new (export, flag, API, a skill rule or mode). The diff must show the new surface.
- `fix`: something a consumer relied on gave a wrong or hard-to-use result, and this corrects it.
- `docs`: explains or reorganizes; nothing a consumer does or sees changes.
- `test`: test files only.
- `chore` / `refactor`: everything else. The default when `feat`/`fix` has no real signal.

Must be in the commitlint `type-enum` if one exists.

**Verb cross-check.** "add", "support", "introduce" mean `feat`; "correct", "guard", "stop", "trim" mean `fix`. If verb and type disagree, re-derive the type from the diff; don't reword the verb.

**Scope.** The one top-level directory under `skills/`, `src/`, or `packages/*`. Omit when ambiguous or history shows no scopes.

**Emoji.** If `shape:` shows `emoji after colon`, put that type's emoji right after the colon (`fix(x): 🐛 subject`). If this type has none in history, read the `emoji` setting in the gitzy config `detect.py` found. Otherwise leave it out.

**Subject.** Imperative, repo casing, within the header max (commitlint `header-max-length` or gitzy `header.max`, else 50, or the repo's `longest` if history runs longer). Say what changed for the consumer, from the diff's one core fact. Build it to fit; never draft long and trim. If the core fact won't fit, say so and offer it slightly over, or name what gets dropped.

**Candidates.** If the diff supports two framings of the same concern, offer 2 or 3 full headers. One obvious effect gets one subject.

**Body.** Follow history: `bodies` mostly present means write one, mostly absent means none. Mixed and the subject isn't self-evident: ask once in the confirmation block. Why over what, one or two short lines.

**Breaking.** Only when a public export, signature, or relied-on behavior changed. Use the history's marker (`!`, footer, or both).

**Issues.** Only the id `detect.py` found on the branch. Never invent one.

### 4. Write, lint, confirm

One call writes the message to `<git-dir>/COMMIT_BODY.md` (never committed) and lints it:

```bash
python3 <skill-dir>/scripts/lint_commit.py - <header-max> <<'EOF'
fix(commit-changes): skip reverts in the sample

Reverts skewed the dominant shape.
EOF
```

Fix every flagged line and rerun until it exits 0. Then print one block:

```
mode: create | branch: feat/x | convention: repo history | repo config | conventional (fallback)
type: fix (corrects recent-commit filter) | scope: commit-changes
message: fix(commit-changes): 🐛 skip reverts in the sample
stage: 3 files via git add -u | hooks: commit-msg (commitlint)
```

With candidates, list them numbered instead of `message:`. If the user's message already said to commit, continue to step 5; otherwise ask: `Commit this? Say "commit", or name a different message.`

If the user corrects a convention and it sounds durable ("we never use scopes"), offer once to add it to `AGENTS.md` (team) or the user's personal agent instructions (personal). Don't write either without a yes.

### 5. Commit and verify

One chained call. Drop `git add -u` when the user already staged; use `git add <paths>` for untracked files they approved:

```bash
f="$(git rev-parse --git-dir)/COMMIT_BODY.md"
git add -u && git commit -F "$f" && git log -1 --format='%H%n%s%n%b' && rm "$f"
```

Amend: `git commit --amend -F "$f"`.

If a hook rejects or rewrites the message, show its output verbatim and stop.

## Voice

- Name the file, symbol, package, or flag. Never "updated things".
- Subject says the effect ("accept optional timeout"), not the mechanics ("changed function signature") or a list of files.
- Imperative, lowercase first word, unless history says otherwise.
- Most commits need no body.
- No em dashes, en dashes, middle dots, curly quotes, sign-offs, or emoji.
- No self-grading ("robust", "clean"). No hedges once a fact is settled.
- No assertion standing in for evidence.
- Don't credit a role you can't verify ("reviewer flagged", "per discussion").
- No chatty opener ("Great, let's...", "Sure, I'll...") or closing pleasantry ("Let me know if you need anything else!"). Start with the content; end with the thing itself or its next-action line.
