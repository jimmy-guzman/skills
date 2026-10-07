# GitHub (`gh`)

Host commands for `create-pr`. Read Gotchas before running anything.

**Version floors.** `gh pr edit --attach` needs gh 2.99.0+ on GitHub.com or Enterprise Cloud. Older gh and Enterprise Server fall back to the placeholder path below. Check with `gh --version` and `gh pr edit --help | grep attach`.

## Contents

- Gotchas
- Lookups
- Templates
- Issues
- Existing PR diff
- Create
- Update
- Verify

## Gotchas

- **Always `--json`, with `--jq` to filter.** Text layout changes between gh versions. The JSON shape is stable and `--jq` is built in.
- **Always `--body-file`.** Never `--body "$(cat ...)"`. Shell quoting breaks on backticks and diff snippets.
- **Always pass `--title` and `--body-file` to `gh pr create`.** With a TTY, gh opens an interactive prompt. Without one (hooks, pipes, CI), it fails fast with "must provide `--title` and `--body`".
- **Screenshots.** Ask the user for image paths. Reference each in the body as `![before](./before.png)` and pass `--attach ./before.png`; gh uploads the file and rewrites the matching reference, or appends the attachment if no reference matches. Works on `gh pr create` and `gh pr edit` since gh 2.99.0, on GitHub.com and Enterprise Cloud only. Older gh or Enterprise Server (check `gh pr edit --help` for `--attach`): leave the placeholders and tell the user to drag the images into the description in the browser. Never commit images to the branch just to link them.
- **`gh pr edit` never changes draft state.** Only `gh pr ready` (and `--undo`) does. Don't run either unless the user asked.
- **`--draft` rejected.** Some private repos don't support draft PRs. Ask before creating it as ready.
- **Some sessions block GitHub GraphQL.** Hosted agent sessions (Claude Code in the cloud, for one) answer `gh pr view`, `gh pr list`, `gh pr diff`, `gh pr create`, `gh pr edit`, and `gh repo view` with HTTP 403 "GitHub GraphQL is not available". _Lookups_ already use REST. For the rest, use `gh api`:
  - Create: `gh api -X POST "repos/{owner}/{repo}/pulls" -f title="<title>" -f head=<branch> -f base=<base> -F draft=true -F body=@"$body" --jq .number`. Then labels with `gh api -X POST "repos/{owner}/{repo}/issues/<n>/labels" -f 'labels[]=<a>'` and the assignee with `gh api -X POST "repos/{owner}/{repo}/issues/<n>/assignees" -f 'assignees[]=<login>'`.
  - Update: the PATCH fallback below, after the bot-span append from _Update_.
  - Diff and commits: `gh api -H 'Accept: application/vnd.github.diff' "repos/{owner}/{repo}/pulls/<n>"` and `gh api "repos/{owner}/{repo}/pulls/<n>/commits" --jq '.[] | "\(.sha[:7]) \(.commit.message)"'`.
  - Verify: `gh api "repos/{owner}/{repo}/pulls/<n>" --jq '{number, title, draft, base: .base.ref, url: .html_url}'`.
  - `--attach` has no REST form. Leave the image placeholders and say so.
- **`gh pr edit` fails with a Projects (classic) GraphQL error** on older gh. Fall back to:

  ```bash
  body="$(git rev-parse --git-dir)/PR_BODY.md"
  gh api -X PATCH "repos/{owner}/{repo}/pulls/<number>" -F body=@"$body"
  ```

## Lookups

These use REST (`gh api`), so they also work where GraphQL is blocked (see Gotchas). Run independent ones as parallel calls in one turn. An error is a failed lookup: report it, never read it as "none found". `{owner}/{repo}` fills in from the local repo; for another repo, write `<owner>/<repo>`.

PR for the current branch (an empty result means none exists):

```bash
gh api "repos/{owner}/{repo}/pulls?head={owner}:{branch}&state=open" \
  --jq '.[] | {number, draft, title, body, base: .base.ref, labels: [.labels[].name], url: .html_url}'
```

PR by number. For a URL, take the owner, repo, and number from it:

```bash
gh api "repos/<owner>/<repo>/pulls/<n>" \
  --jq '{number, draft, title, body, base: .base.ref, head: .head.ref, labels: [.labels[].name], url: .html_url}'
```

Default branch:

```bash
gh api "repos/{owner}/{repo}" --jq .default_branch
```

Your login, for the two lookups that filter on it: `gh api user --jq .login`.

Your open PR branches (stacked-branch check):

```bash
gh api "repos/{owner}/{repo}/pulls?state=open&per_page=100" \
  --jq '.[] | select(.user.login == "<login>") | .head.ref'
```

Recent merged titles, bots excluded:

```bash
gh api "repos/{owner}/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=50" \
  --jq '[.[] | select(.merged_at != null and .user.type != "Bot") | .title][:10][]'
```

Ticket link base:

```bash
gh api "repos/{owner}/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=50" \
  --jq '.[] | select(.merged_at != null and .user.type != "Bot") | .body // empty' \
  | grep -oE 'https?://[^ )>]+/[A-Z][A-Z0-9]+-[0-9]+' \
  | sed -E 's|[A-Z][A-Z0-9]+-[0-9]+$||' \
  | sort | uniq -c | sort -rn | head -1
```

Your recent metadata. `requested_reviewers` empties once reviewers review, so it is often blank:

```bash
gh api "repos/{owner}/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=50" \
  --jq '[.[] | select(.merged_at != null and .user.login == "<login>")][:10]
    | map({labels: [.labels[].name], assignees: [.assignees[].login], reviewers: [.requested_reviewers[].login]})'
```

Issue details: `gh api "repos/{owner}/{repo}/issues/<n>" --jq '{title, body}'`.

## Templates

First hit wins:

1. `pull_request_template.md` (any case) in `.github/`, the repo root, or `docs/`. GitHub applies this one in the UI, so the team expects it.
2. Exactly one file in `.github/PULL_REQUEST_TEMPLATE/`: use it. Several: ask which.

**Another repo** (describe mode). Read the same locations from the host, in the same order. The API is case-sensitive, so try `pull_request_template.md` and `PULL_REQUEST_TEMPLATE.md` in each place:

```bash
gh api -H 'Accept: application/vnd.github.raw' "repos/<owner>/<repo>/contents/.github/pull_request_template.md" 2>/dev/null
gh api "repos/<owner>/<repo>/contents/.github/PULL_REQUEST_TEMPLATE" --jq '.[].name' 2>/dev/null
```

A 404 means that path doesn't exist; move to the next.

## Issues

`#123` links automatically. Close keywords: `Closes`, `Fixes`, `Resolves`.

On squash-merge repos the PR title becomes the commit subject, so the title shape matters.

## Existing PR diff

```bash
gh pr diff <number-or-url>
gh pr view <number-or-url> --json commits \
  --jq '.commits[] | "\(.oid[:7]) \(.messageHeadline)\n\(.messageBody)"'
```

## Create

```bash
body="$(git rev-parse --git-dir)/PR_BODY.md"
gh pr create \
  --draft \
  --head <branch> \
  --base <base> \
  --title "<title>" \
  --body-file "$body" \
  --assignee @me \
  --label "<a>,<b>"
```

Drop `--draft` when draft is false. Drop `--assignee` and `--label` when detection found nothing. Add `--attach <file>` once per screenshot.

Fork workflow: push to the fork, then create with `--repo <upstream>` and `--head <fork-owner>:<branch>`.

## Update

```bash
body="$(git rev-parse --git-dir)/PR_BODY.md"
echo >> "$body"
gh pr view <number-or-url> --json body --jq .body \
  | awk '/^<!-- This is an auto-generated comment/,/^<!-- end of auto-generated comment/' >> "$body"
gh pr edit <number-or-url> --body-file "$body"
```

The fetch and awk carry every bot span from the live body; skip neither, even for a one-line touch-up. Add `--title` or `--add-label` only if the user approved changing them. Pass `--attach <file>` once per screenshot the same way as on create (gh 2.99.0+, see Gotchas).

## Verify

```bash
gh pr view <number-or-url> --json number,title,isDraft,baseRefName,url
```
