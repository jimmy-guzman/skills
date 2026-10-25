---
name: submit-changes
description: >
  Drafts, opens, or updates a pull request (GitHub) or merge request (GitLab)
  that follows the repo's own conventions (base branch, title shape, template,
  ticket links, labels, issue closing) and writes the description in a terse,
  reviewer-first voice. Use whenever the user wants to create, open, draft,
  update, or describe a PR or MR: "create a PR", "open a merge request",
  "push and MR", "draft a PR", "update the PR description", "add a
  description to this PR", "this PR has no description, add one", "give
  this PR a description", "write a description for !482" or for a PR URL,
  a request for submit-changes by name, or a pushed feature branch and "what
  next". Use it even if they never name the host or the CLI, or never name
  the PR by number: the current branch's own open PR counts.
  Handles new PRs, the PR on the current branch, and an already-open PR given
  by number or URL. Not for commit messages or reviewing a PR.
compatibility: Requires git and python3, plus gh (GitHub) or glab and jq (GitLab), authenticated
---

# submit-changes

"PR" below means MR on GitLab, and "base" means target branch. Use the host's own terms when talking to the user and in the text you write.

## Principle

Detect every value. Sources, highest precedence first:

1. Instructions: the repo's agent docs (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/`, `CONTRIBUTING.md`), then the user's own instructions and saved preferences, in whatever form the agent has them. Repo docs win on conflict; they describe the team.
2. The repo itself: PR templates, recent PRs, branch and commit history.
3. Fallbacks listed in each step.

When a source has a convention, follow it. When none does, use the fallback and say so in the confirmation step.

**Attribution line.** If the agent is set up to add an attribution line to PR bodies (a "Generated with ..." footer), it ranks below all three sources above. Detected the same way as the rest of §1 (see **Attribution convention** below).

## In any agent

- To ask the user something, use the agent's question tool if it has one. Otherwise ask in plain text with numbered choices, and wait for the answer.
- Scratch files (body, file list) go in a temp dir, never under `.git`: in a linked worktree `git rev-parse --git-dir` points into the main checkout, and some hosts refuse writes there (Claude Code inside a worktree does). Run `mktemp -d` once as its own command and reuse the printed path as a literal, written `<tmp>` below. Never rebuild it with `$(...)`.

## Process

### 0. Preflight

**Host.** Don't assume the remote is `origin`; use the branch's upstream remote.

```bash
git remote get-url <remote>
```

- `github.com` in the URL: GitHub.
- `gitlab` in the URL: GitLab.
- Unclear (self-hosted): whichever of `gh repo view` or `glab repo view` succeeds. Neither: stop. This probe is the only host command allowed before the reference file is read.

Then read exactly one file, before running any other host command:

- GitHub: [references/github.md](references/github.md)
- GitLab: [references/gitlab.md](references/gitlab.md)

It holds every host command named below and the gotchas for that CLI.

**Mode.**

- **describe**: the user named a PR by number or URL. Fetch it with _Lookups: PR by number or URL_. Skip the branch checks; nothing local is touched. If the PR lives in another repo (the URL or `gh pr view` output names a different owner/repo), record that repo and use it in every lookup in §1: `<owner>/<repo>` in place of `{owner}/{repo}` on GitHub, or `-R <group>/<project>` on glab. Templates must come from the host (_Templates_ in the reference file covers another repo), not the local filesystem.
- **update**: the current branch already has a PR (_Lookups: PR for the current branch_).
- **create**: otherwise.

Describe and update keep the PR's current title, description, base, labels, and draft state for §4 and §6, so in §1 they skip Base branch, Title shape, Metadata, and Draft.

**Branch checks** (create and update only). Run them as one command.

```bash
git status --porcelain
git branch --show-current
git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null   # names the remote, nothing more
git ls-remote <remote> refs/heads/<branch>                         # empty: never pushed
git rev-parse HEAD
```

Ask the remote whether the branch exists; don't infer it from `@{u}`. A branch cut from the base (`git switch -c x origin/main`, `git worktree add -b x origin/main`) tracks `origin/main`, so `@{u}` reports an upstream and "1 ahead" for a branch that was never pushed.

Stop and ask if:

- The current branch is the default branch.
- The working tree is dirty. List files and stop. Committing is commit-changes' job: name it, and never draft a commit message here or put a commit and a push in one question.
- The remote branch's commit differs from `HEAD` and the remote is ahead or the two diverged. Fetch it (`git fetch <remote> <branch>`) and check `git merge-base --is-ancestor <remote>/<branch> HEAD`. Failure means the remote has commits you don't: stop and say so. Never force over commits you did not just rebase yourself in §2.

Not a stop, but record it for §5 and §6: the branch is not on the remote (`ls-remote` prints nothing), or `HEAD` is ahead of it (the ancestor check passes). The PR shows the remote, not your local branch, so a push is needed. It is listed as an action in §5 and runs in §6, after the user says go. Never push before then.

### 1. Detect conventions

Fetch the base first so every ref the parallel runs read actually exists locally:

```bash
git fetch <remote> <base>
```

Then run the lookups as parallel calls in one turn. Record each value and its source for §5. Commands are under _Lookups_ in the reference file. An error is a failed lookup: report it, never read it as "none found".

**Agent docs.** Read the instruction sources from Principle. Take only pull request, merge request, branching, and commit guidance: base branch, title format, required sections, labels, ticket linking, draft state. Anything they state outranks what the repo implies. Ignore guidance unrelated to PRs.

When sampling recent PRs anywhere below, exclude bot authors and reverts. Review bots (CodeRabbit and similar) also write into human PRs: before reading a description, drop everything from `<!-- This is an auto-generated comment` to its `<!-- end of auto-generated comment` marker. If nothing human is left, that PR doesn't count; sample further back.

**Base branch.** First hit wins:

1. The existing PR's base (describe and update).
2. Agent docs.
3. Stacked branch. The candidates are the head branches of your open PRs, from the lookup. Fetch them all in one call (`git fetch <remote> <candidate>...`); shallow and single-branch clones have none of these refs otherwise. For each candidate, check `git merge-base --is-ancestor <remote>/<candidate> HEAD`, all in one loop. If one is an ancestor and closer than the default branch (smaller `git rev-list --count <remote>/<candidate>..HEAD`), propose it and ask.
4. Default branch.

**Title shape.** Agent docs, then the dominant shape (not the words) of recent merged titles. Match it exactly: ticket prefix and its punctuation, `type(scope):` if used, casing, and whether identifiers are backticked. Fallbacks: the branch's first commit subject (`git log <remote>/<base>..HEAD --format=%s | tail -1`), then plain English.

**Description template.** First hit wins:

1. A template named in agent docs.
2. The host's template files (_Templates_ in the reference file).
3. Required sections listed in agent docs.
4. None: the default shape under Voice.

**Ticket id.** Extract from the branch name, then commit subjects, then the existing PR title. Patterns:

- `[A-Z][A-Z0-9]+-\d+`: Jira or Linear style.
- `#\d+`: an issue on the host.

Discard look-alikes such as `UTF-8`, `ISO-8601`, `ES-2015`. Accept a prefix only if it appears in agent docs, recent PR titles or descriptions, or the user confirms.

No match means no ticket. Only ask if agent docs require one or nearly every recent PR carries one. Never invent an id.

**Ticket link base** (Jira or Linear style ids). First hit wins:

1. Agent docs.
2. Recent PR descriptions (_Lookups: ticket link base_).
3. A connected tracker tool. Jira: list the accessible Atlassian sites, take the site URL, append `/browse/`. Linear: use the workspace URL plus `/issue/`.
4. Ask once. Offer to add it to `AGENTS.md` (team) or the user's personal agent instructions (personal). Don't write either without a yes.

`#123` needs no base. The host links it.

**Issue closing.** Agent docs, then how recent descriptions reference tickets: `Closes #123`, `Fixes #123`, `Relates to #123`, or a bare reference. Match the dominant form. Fallback: bare reference, no auto-close.

**Attribution convention.** First hit wins:

1. Agent docs, or a user instruction/preference about attribution, co-author trailers, or AI credit.
2. The template, if it has a footer section or forbids one.
3. Recent merged PR bodies (same sample already pulled for Title shape/Issue closing): footer present or absent, dominant pattern wins.
4. Sample inconclusive (too few merged PRs, or genuinely mixed): fallback, append it.

**Metadata.** Agent docs, then the user's own recent PRs:

- Assignee: the user, if most were self-assigned.
- Labels: those on most of those PRs that fit this change.
- Reviewers: never add automatically. List frequent ones as a suggestion. Approval rules and CODEOWNERS are the host's job.

**Draft.** Agent docs, else true. Describe and update keep the current state.

### 2. Gather context

**Branch freshness** (create and update only; describe has no local branch).

```bash
git merge-base --is-ancestor <remote>/<base> HEAD
```

Success means the base is already merged into `HEAD`: skip ahead, nothing to do. Failure means the base has commits `HEAD` lacks, and the PR would open out of date:

```bash
git rev-list --count HEAD..<remote>/<base>
```

Show the count and ask, with the question tool, in this order: "Rebase onto `<remote>/<base>` (Recommended)", "Merge `<remote>/<base>` in", "Leave it behind". Rebase is the default: "yes", "sync", or "go" means rebase. Never update without asking, and never leave it behind without the user choosing that.

- Rebase: `git rebase <remote>/<base>`. `HEAD` now differs from the remote branch, so §6 pushes with `--force-with-lease`.
- Merge: `git merge <remote>/<base>`. §6 pushes normally.
- Leave it behind: proceed.

On conflicts from either, stop and hand control back; never auto-resolve. Record the outcome for the §5 summary, one line whichever it was: "Rebased onto `origin/main` (was 3 behind)", "Merged `origin/main` (was 3 behind)", or "3 behind `origin/main`, left as is (your call)".

**Create and update.** The base fetch ran in §1. One command:

```bash
git diff --stat <remote>/<base>...HEAD
git log <remote>/<base>..HEAD --format='%h %s%n%b'
git diff <remote>/<base>...HEAD -- . ':(exclude,glob)**/*.lock' ':(exclude,glob)**/*-lock.*' ':(exclude,glob)**/go.sum'
```

Skip generated code, snapshots, and vendored files when reading. When the stat runs past about 1,500 lines, drop the last line and read the diff per file group instead.

Diff against the fetched remote base, never the local one. A stale local base shows changes that aren't yours.

**Describe.** Use _Existing PR diff_ in the reference file for the diff and commits. It reads from the host, so it works for branches that aren't checked out and for forks. The last line saves the file list for the §5 lint.

**Where the why comes from.** The diff never says why, and a why inferred from it cannot be checked. Sources, first hit wins:

1. The conversation or plan this change was made in, when this agent did the work. It holds what was tried and dropped.
2. Commit bodies. Subjects say what; bodies carry intent.
3. The ticket: a tracker tool for Jira or Linear ids, the host's issue view for `#n`. Often the slowest step; skip it when 1 or 2 answers.
4. The user, asked in §5. Never the diff.

### 3. Decide the evidence

Evidence is a before and an after.

- UI change (the diff touches `.vue`, `.tsx`, `.jsx`, `.svelte`, `.css`, `.scss`, chart or plot code, or the ticket is visual): screenshots. Draft `### Before` and `### After` headings with a `<!-- before -->` / `<!-- after -->` placeholder under each; how real images get in is host-specific (see Gotchas in the reference file). A table, one row per pair, only for a real series of screens or states. Never fabricate a screenshot.
- Anything else: the test that failed before and passes now, or the output that changed.

Never state a before you didn't observe. A test that is new in this diff and was never run against the base is "new test", not "failed before".

### 4. Draft title and body

**Title.** Fill the shape from §1. Don't type a `Draft:` prefix; the draft flag handles it. Describe and update keep the current title unless asked.

**Body with a template.** Keep its headings, order, and checklists; _With a template_ under Voice says how to fill them. Don't tick a checkbox you can't verify from the diff or the conversation.

**Body without a template.** Use the default shape under Voice.

**Ticket reference.** Put it where the template puts it. Otherwise it is the first line of the body, alone.

- Jira or Linear: `[TICKET-ID](<link base>TICKET-ID)`, prefixed with the close keyword from §1 if any.
- Host issue: `#123`, prefixed with the close keyword if any.

**Describe and update.** Redraft from the full diff, then merge with the current description. Keep everything you did not write: uploaded images, ticked checkboxes, other sections, notes for reviewers. Drop bot spans (the auto-generated markers from §1) from the merge; §6 re-adds them from the live body at write time, so a bot that wrote after §0 survives. An empty current description needs no merge.

### 5. Confirm inline

Write the drafted body to `<tmp>/PR_BODY.md`, then lint it. Fix every error and rerun until it exits 0, before showing the user. A `warning:` line flags length or shape: reread the span, cut what the diff already says, keep what the reviewer needs. Keeping one is fine; say so in the chat summary.

```bash
python3 <skill-dir>/scripts/lint_body.py <tmp>/PR_BODY.md --base <remote>/<base>   # create, update
python3 <skill-dir>/scripts/lint_body.py <tmp>/PR_BODY.md --files <tmp>/PR_FILES.txt   # describe
```

`--base` lists the changed files itself. Describe takes them from the host instead, saved in §2.

Before printing, apply the attribution rule from Principle.

If §2 found no why, or nothing was said for Review, ask with the draft, in the same message: "What prompted this?" and "Anything the reviewer should focus on, challenge, or know wasn't exercised?" The user corrects a body, not a form. A "just open it" skips the Review question, never the Why one: a body with no why doesn't ship, so lint again once the answer is in.

Before the title and body, print a short list of the conventions you found. One fact per line, in plain words. Give a source only where the user might disagree. Put all the empty fields on one "Not set" line. Put the actions last:

```markdown
- Opening a merge request on GitLab into `develop` (from AGENTS.md)
- Title: `PROJ-123: desc`, like 7 of the last 10 MRs
- Body: the `Default.md` template
- Ticket: PROJ-123, closed with `Closes`
- Labels: `frontend`, like 8 of your last 10
- Assignee: you
- Draft: yes
- Not set: attribution footer (recent MRs have none)
- Rebased onto `origin/develop` (was 3 behind)
- Will force-with-lease push `feat-x` to origin first
```

The sync line from §2 is always present when the branch was behind. The push line is required whenever §0 or §2 left `HEAD` off the remote: a plain push for a new branch, new commits, or a merge; a force-with-lease push after a rebase. Without it the PR shows the old remote.

For describe and update, also show what changed against the current description.

`Go ahead with this? Say "go", or name an edit.` No pushes, uploads, or host writes until then. A request that already said to go ahead ("just open it", "ship it") is the approval: print the summary and continue to §6.

If the user corrects a detected convention, apply it to this PR. If it sounds durable ("we always target develop"), offer once to add it to `AGENTS.md` (team) or the user's personal agent instructions (personal). Don't write either without a yes.

### 6. Create or update

**Push first** (create and update). Re-check here, not from the §0 result: §0 or §2 may have moved `HEAD` since.

```bash
git rev-parse HEAD
git ls-remote <remote> refs/heads/<branch>
```

- Same sha: nothing to push.
- Empty: `git push -u <remote> <branch>`.
- Different, `git merge-base --is-ancestor <remote>/<branch> HEAD` passes: `git push <remote> <branch>`.
- Different because §2 rebased: `git push --force-with-lease <remote> <branch>`. This is the only force push this skill makes. A refused lease means someone else pushed meanwhile: stop and say so.
- Anything else: stop and say so.

The body is already on disk from §5. Run _Create_ (create mode) or _Update_ (describe and update) from the reference file. Change the title, labels, or draft state of an existing PR only if the user approved it.

**Every body write is a full replacement.** Bots append to the body after §0 reads it (CodeRabbit lands within minutes). Right before the write, re-fetch the live body and append every bot span to the draft; the _Update_ snippet in the reference file does both. This holds for any later edit of the body, inside this skill or a one-line touch-up after it.

### 7. Verify

Run _Verify_ from the reference file. Confirm draft state and base match what §5 showed. Then, for create and update, confirm the PR's head sha equals `git rev-parse HEAD` and that the branch is current with the base:

```bash
git fetch <remote> <base>
git merge-base --is-ancestor <remote>/<base> HEAD
```

Failure means the PR is out of date. Report it; the one accepted case is "left as is" chosen in §2, and the report says so. Delete `<tmp>`. Report the PR URL.

## Voice

Applies to the body. The title follows the shape from §1 exactly, emoji and all.

**Default shape** (no template). Three `###` headings, Why, Approach, Review, in that order, always headings and never bold run-in labels. A heading exists only when it has something under it. Inside a section use whatever tells the story: a list for same-shaped items, a table for a series of pairs, a fenced block for a command or its output, a file tree or Mermaid diagram for structure, `### Before` / `### After` for evidence. Prose is the default; a block earns its place by being clearer than the sentence it replaces.

```markdown
<ticket reference, alone, if there is one>

### Why

<The problem: what was wrong, how it showed up, why now.>

### Approach

<The decisions the diff does not show.>

<Evidence, where a real before and after exists.>

### Review

<What the reviewer should do with this.>
```

Why is required and first. Approach and Review exist only when they have content; a dependency bump is often a Why alone. No other section names, nothing follows Review except the attribution footer from Principle. The first sentence of each section carries the point.

**Why** answers "what was wrong and why it mattered," never "what changed": that is Approach's job. Readable without opening the ticket; short sentences, concrete nouns, no "This PR introduces". Asked for more detail, say more about the problem (where it leads, how it showed up, why now), not about the changes.

**Approach** holds only what a reviewer cannot tell from the diff or the file list: the alternative rejected and why, a departure from the codebase's usual pattern, what is deliberately out of scope, the one behavior change inside a refactor, a default that flipped. Name the file, symbol, package, or flag ("the 320px cap is gone", not "updated the component"). How it works is in the diff; a migration that just adds a column gets no mention unless something in it is surprising. Prose by default. A list is for same-shaped items only, one or two short clauses per bullet, at most one semicolon; a sub-list only when each item has its own change (one child per package in a toolchain upgrade, one per change in a file with several). Items sharing one change get a group name on one bullet ("Docs: spec, design, README"); two items stay inline. The file inventory, one bullet per touched file, is the failure this shape exists to prevent.

```markdown
- `image-resize.ts`:
  - drag a handle on the right edge to resize; only `width` is saved
  - pointer capture stops `DragSelectionView` from also selecting the node
```

**Evidence** is a real before and after a reviewer can't get elsewhere: a number, a screenshot, a test that failed and now passes. "Tests pass" is not evidence; the PR shows CI. Most changes need none. When one does, it sits right after the sentence it supports, under `### Before` / `### After` headings; a table only for a real series of pairs. For structure or flow, the smallest visual that makes it clear: a file tree, call tree, or Mermaid diagram.

**Review** is the one paragraph written to the reviewer, and only from what the user or the session actually said; an invented doubt sends them to the wrong place. A specific feedback request is the single element of a description with the strongest measured effect on review, so write one whenever the user or session gave anything to ask. Its content: the feedback wanted ("design check on the cache key, the rest is mechanical"), where to start in a large diff, what the author is unsure of, and a behavior left unverified that a reviewer would assume was covered. Say the behavior, not the step skipped: "the retry path never ran against the real API" is actionable; "`pnpm dev` was not run" is not, and a reviewer once said so. Mechanical files (renames, formatter output) go as self-comments on the diff. Coordination talk ("Deploy order", "This merges first", "Follow-up MR") stays in the chat summary: the body is about the change, not the session.

A risk gets one clause in the Approach sentence it belongs to, only when the reviewer has something specific to check. Don't attribute to a role you can't verify ("reviewer flagged", "per discussion") unless a named reviewer said it in the thread. Same for a referenced PR, ticket, or incident: fetch it and confirm before saying what it did or broke; unverified, state only what's known ("spooked the team", not "broke builds").

Every file the body names must be in the diff, and a claimed test must have a test file behind it; describing work the diff does not contain is what most reliably gets a PR rejected.

Length scales with the change. Description length does not predict whether a PR merges; what it says does. The lint warns past Why 80 words (ticket line aside), Approach prose 100, Review 60, 6 top-level bullets or 10 in all, 25 words a bullet. A warning asks whether the diff already says it, not for a cut: a substantial problem gets a substantial Why. The diff holds the how.

No em dashes, en dashes, middle dots, curly quotes, sign-offs, or emoji; the attribution footer from Principle is the one exception, added after the lint. No summary of the summary. No self-grading ("robust", "comprehensive", "properly"). No hedges once a fact is settled. No assertion standing in for evidence ("tests pass", "tested locally", "fully backward compatible"). The §5 lint enforces this section. In the chat turn around the draft, no chatty opener ("Great, let's...") or closing pleasantry ("Let me know if you need anything else!"); start with the content and end with the thing itself or its next-action line.

**With a template**, its headings and order win. Fill each section in this voice: Why's rules where it asks for motivation, Approach's where it asks for the changes. Handle unused sections the way recent merged PRs do; when they don't settle it, delete a section with nothing to say rather than writing "N/A". Never leave the template's HTML comments in. An AI disclosure field gets the tool and the extent, truthfully.
