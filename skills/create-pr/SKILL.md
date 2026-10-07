---
name: create-pr
description: >
  Draft, open, or update a pull request (GitHub) or merge request (GitLab)
  that follows the repo's own conventions (base branch, title shape, template,
  ticket links, labels, issue closing) and writes the description in a terse,
  reviewer-first voice. Use whenever the user wants to create, open, draft,
  update, or describe a PR or MR: "create a PR", "open a merge request",
  "push and MR", "draft a PR", "update the PR description", "write a
  description for !482" or for a PR URL, "/create-pr", or a pushed feature
  branch and "what next". Use it even if they never name the host or the CLI.
  Handles new PRs, the PR on the current branch, and an already-open PR given
  by number or URL. Not for commit messages or reviewing a PR.
compatibility: Requires git, plus gh (GitHub) or glab and jq (GitLab), authenticated
---

# create-pr

"PR" below means MR on GitLab, and "base" means target branch. Use the host's own terms when talking to the user and in the text you write.

## Principle

Detect every value. Sources, highest precedence first:

1. Agent docs and user memory: `AGENTS.md` and `CLAUDE.md` at the repo root, then the user's personal `CLAUDE.md`, then the user's auto-memory (`MEMORY.md` in context, and the files it indexes under `.../memory/` -- `feedback_*` entries especially, which carry durable "always/never" rules). Repo docs win on conflict; they describe the team. Memory entries win over the harness attribution reminder; they describe the user.
2. The repo itself: PR templates, recent PRs, branch and commit history.
3. Fallbacks listed in each step.

When a source has a convention, follow it. When none does, use the fallback and say so in the confirmation step.

A harness attribution footer (a "Generated with ..." line the session asks for on PR bodies) ranks below all three. Leave it out when any source says to omit: agent docs, template limits, or a memory `feedback_*` entry about Claude, `Co-Authored-By`, or attribution trailers. If every source is silent, add it as the last line. Check memory explicitly: a visible `MEMORY.md` index line like `- [No Co-Authored-By trailers](feedback_no_co_author.md)` is a direct instruction, not a hint.

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

- **describe**: the user named a PR by number or URL. Fetch it with _Lookups: PR by number or URL_. Skip the branch checks; nothing local is touched. If the PR lives in another repo (the URL or `gh pr view` output names a different owner/repo), record that repo and pass `--repo <owner>/<repo>` on gh or `-R <group>/<project>` on glab to every lookup in §1. Templates must come from the host API, not the local filesystem.
- **update**: the current branch already has a PR (_Lookups: PR for the current branch_).
- **create**: otherwise.

Describe and update keep the PR's current title, description, base, labels, and draft state for §4 and §6.

**Branch checks** (create and update only).

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
- The working tree is dirty. List files; ask whether to commit, stash, or stop.
- The branch is not on the remote (`ls-remote` prints nothing). Show the branch and remote; ask before `git push -u <remote> <branch>`. Never auto-push.
- The remote branch's commit differs from `HEAD`. Ask before pushing. The PR shows the remote, not your local branch.

### 1. Detect conventions

Fetch first so every ref the parallel runs read actually exists locally:

```bash
git fetch <remote> <base>
```

The stacked-branch check below also reads candidate head refs; fetch those (`git fetch <remote> <candidate>`) before the ancestor check. Shallow and single-branch clones have neither otherwise.

Then run in parallel. Record each value and its source for §5. Commands are under _Lookups_ in the reference file.

**Agent docs.** Read the repo's `AGENTS.md` and `CLAUDE.md` if present, plus the user's personal `CLAUDE.md` if it's in context. Take only pull request, merge request, branching, and commit guidance: base branch, title format, required sections, labels, ticket linking, draft state. Anything they state outranks what the repo implies. Ignore guidance unrelated to PRs.

When sampling recent PRs anywhere below, exclude bot authors and reverts. Review bots (CodeRabbit and similar) also write into human PRs: before reading a description, drop everything from `<!-- This is an auto-generated comment` to its `<!-- end of auto-generated comment` marker. If nothing human is left, that PR doesn't count; sample further back.

**Base branch.** First hit wins:

1. The existing PR's base (describe and update).
2. Agent docs.
3. Stacked branch. For each head branch of the user's open PRs, fetch it (`git fetch <remote> <candidate>`), then check `git merge-base --is-ancestor <remote>/<candidate> HEAD`. If one is an ancestor and closer than the default branch (smaller `git rev-list --count <remote>/<candidate>..HEAD`), propose it and ask.
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
4. Ask once. Offer to record the answer as one line in the repo's `AGENTS.md` (team-wide) or the personal `CLAUDE.md` (every repo at this org). Don't write either without a yes.

`#123` needs no base. The host links it.

**Issue closing.** Agent docs, then how recent descriptions reference tickets: `Closes #123`, `Fixes #123`, `Relates to #123`, or a bare reference. Match the dominant form. Fallback: bare reference, no auto-close.

**Metadata.** Agent docs, then the user's own recent PRs:

- Assignee: the user, if most were self-assigned.
- Labels: those on most of those PRs that fit this change.
- Reviewers: never add automatically. List frequent ones as a suggestion. Approval rules and CODEOWNERS are the host's job.

**Draft.** Agent docs, else true. Describe and update keep the current state.

### 2. Gather context

**Create and update.** The base fetch ran in §1. In parallel:

- `git diff --stat <remote>/<base>...HEAD` to size the change.
- `git diff <remote>/<base>...HEAD` excluding lockfiles, generated code, snapshots, and vendored files. For large diffs, read per file guided by the stat.
- `git log <remote>/<base>..HEAD --format='%h %s%n%b'`. Commit bodies carry intent.

Diff against the fetched remote base, never the local one. A stale local base shows changes that aren't yours.

**Describe.** Use _Existing PR diff_ in the reference file for the diff and commits. It reads from the host, so it works for branches that aren't checked out and for forks.

**All modes.** Ticket details: a tracker tool for Jira or Linear ids, the host's issue view for `#n`.

### 3. Decide the evidence

Evidence is a before and an after.

- UI change (the diff touches `.vue`, `.tsx`, `.jsx`, `.svelte`, `.css`, `.scss`, chart or plot code, or the ticket is visual): screenshots. Draft the table with `<!-- before -->` and `<!-- after -->` placeholders; how real images get in is host-specific (see Gotchas in the reference file). Never fabricate a screenshot.
- Anything else: the test that failed before and passes now, or the output that changed.

Never state a before you didn't observe. A test that is new in this diff and was never run against the base is "new test", not "failed before".

### 4. Draft title and body

**Title.** Fill the shape from §1. Don't type a `Draft:` prefix; the draft flag handles it. Describe and update keep the current title unless asked.

**Body with a template.** Keep its headings, order, and checklists. Fill each section using Voice. Handle unused sections and template comments the way recent merged PRs do. Don't tick a checkbox you can't verify from the diff or the conversation.

**Body without a template.** Use the default shape under Voice.

**Ticket reference.** Put it where the template puts it. Otherwise it opens `## Why`.

- Jira or Linear: `[TICKET-ID](<link base>TICKET-ID)`, prefixed with the close keyword from §1 if any.
- Host issue: `#123`, prefixed with the close keyword if any.

**Describe and update.** Redraft from the full diff, then merge with the current description. Keep everything you did not write: uploaded images, ticked checkboxes, sections you didn't write, notes for reviewers. Drop bot spans (the auto-generated markers from §1) from the merge; §6 re-adds them from the live body at write time, so a bot that wrote after §0 still survives. An empty current description needs no merge.

### 5. Confirm inline

Write the drafted body to a temp file first, then lint it. Fix every flagged line before showing the user.

```bash
body=$(mktemp)
trap 'rm -f "$body"' EXIT
# Write the drafted body to $body here.

grep -nF -- '—' "$body" && echo "em dash: replace with period, comma, or hyphen"
grep -nF -- '–' "$body" && echo "en dash: replace with period, comma, or hyphen"
grep -nF -- '·' "$body" && echo "middle dot: replace with period, comma, or hyphen"
grep -nF -- '“' "$body" && echo "curly quote: replace with straight quote"
grep -nF -- '”' "$body" && echo "curly quote: replace with straight quote"
grep -nF -- '‘' "$body" && echo "curly apostrophe: replace with straight apostrophe"
grep -nF -- '’' "$body" && echo "curly apostrophe: replace with straight apostrophe"
grep -nE '^-[^-].*-> .*-> .*-> ' "$body" \
  && echo "3+ version arrows on one bullet: split into a sub-list"
grep -nE '^-[^-].+,.+,' "$body" \
  && echo "3+ comma-separated items on one bullet: split into a sub-list, or redraft if prose"
```

For the attribution footer, re-read source 1 in Principle. A visible `MEMORY.md` index line about Claude, `Co-Authored-By`, or attribution trailers means omit the footer regardless of what the harness reminder says.

Print a one-block conventions summary, then the title and body. Example:

```
host: GitLab | mode: create | base: develop (AGENTS.md)
title: `TICKET: desc` (7/10 recent MRs) | template: Default.md
ticket: PROJ-123 via recent MR descriptions | closing: Closes (6/10)
labels: frontend (8/10 of yours) | assignee: @me | draft: yes
```

For describe and update, also show what changed against the current description.

Wait for approval or edits. No file writes, uploads, or host write calls until then.

If the user corrects a detected convention, apply it to this PR. If it sounds durable ("we always target develop"), offer once to add it to agent docs: the repo's `AGENTS.md` for team conventions, the personal `CLAUDE.md` for personal defaults.

### 6. Create or update

The body is already on disk from §5. Run _Create_ (create mode) or _Update_ (describe and update) from the reference file. Change the title, labels, or draft state of an existing PR only if the user approved it.

**Every body write is a full replacement.** Bots append to the body after §0 reads it (CodeRabbit lands within minutes of the open). Right before the write, re-fetch the live body and append every bot span to the draft; the _Update_ snippet in the reference file does both. This holds for any later edit of the body too, inside this skill or a one-line touch-up after it.

### 7. Verify

Run _Verify_ from the reference file. Confirm draft state and base match what §5 showed. Report the PR URL.

## Voice

Governs prose everywhere in the PR, template or not.

**Default shape** (when the repo has no template):

```markdown
## What

- `<file group or symbol>`: <specific change, one line>
- `<file group or symbol>`: <what changed and what to look at>.

  | Before | After |
  |---|---|
  | <screenshot, failing test, or old output> | <screenshot, passing test, or new output> |

## Why

<ticket reference>

<One or two short paragraphs. Lead with the problem, not the solution.>
```

Those two sections only. Nothing else gets a heading.

**Rules:**

- **Specificity over category.** Each change names the file, symbol, package, or flag. Never "updated the component" or "refactored the module".
- **Why is for the reviewer, not the ticket.** Plain prose a reviewer can read without clicking through. Short sentences. Concrete nouns. No "This PR introduces", no "In order to".
- **The body is about the change, not the session.** It carries the change and its risk. What you ran, didn't run, or skipped ("`pnpm dev` was not run on this branch"), and coordination talk ("Deploy order", "This merges first", "Follow-up MR"), is nothing a reviewer can act on; it goes in the chat summary.
- **Don't attribute to a role you can't verify.** No "reviewer flagged", "after feedback", "per discussion" unless a named reviewer actually said it in the thread. If the change came from reconsidering, say so directly, or just state the change.
- **Evidence lives with the claim.** Benchmarks, before/after numbers, and screenshots sit on the bullet they support, never in a trailing section. Evidence is a before and an after; "tests pass" alone is not evidence.
- **Show shape when shape is the point.** When the change is about structure or flow (files moving, a call order changing), a bullet can carry the smallest visual that makes it clear: a file tree, call tree, or Mermaid diagram, or a diff of one. Otherwise plain bullets.

  ```diff
   submitForm
     createSession
  +    expandSkillMention
       launchAgent
  ```

- **Length scales with the change, then stops.** A one-column migration gets four lines. A ten-file change gets one bullet per group of files that change together, not one per file or symbol. One line per bullet. `## Why` stays at two short paragraphs. The diff holds the rest.
- **Three or more named items get a sub-list.** When a bullet enumerates three or more distinct packages, files, rules, or flags, split them: a short parent bullet with a label, one child bullet per item with its own change. Two items can stay inline. Hard rule, not a judgment call; the §5 lint catches it.

  ```markdown
  - Toolchain upgrade:
    - `eslint`: 8.57 -> 10.12 (via 9.39.5)
    - `@vue/eslint-config-typescript`: 13 -> 14.9
    - `eslint-plugin-vue`: 9.33 -> 10.11
    - `@eslint/js` added at 10
    - `vue`: 3.5.17 -> 3.5.43
  ```

- **No filler.** No em dashes, no sign-offs, no emoji, no summary of the summary. The §5 lint catches em dashes, en dashes, middle dots, and curly quotes before the confirmation print.
