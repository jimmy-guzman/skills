# GitHub (`gh`)

Host commands for `create-pr`. Read Gotchas before running anything.

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
- **Always pass `--title` and `--body-file` to `gh pr create`.** Without both, gh opens an interactive prompt and hangs the call.
- **Screenshots.** Ask the user for image paths. On create, reference each in the body as `![before](./before.png)` and pass `--attach ./before.png`; gh uploads the file and rewrites the reference. `gh pr edit` has no `--attach`, and older gh lacks it on create too (check `gh pr create --help`): then leave the placeholders and tell the user to drag the images into the description in the browser. Never commit images to the branch just to link them.
- **`gh pr edit` never changes draft state.** Only `gh pr ready` (and `--undo`) does. Don't run either unless the user asked.
- **`--draft` rejected.** Some private repos don't support draft PRs. Ask before creating it as ready.
- **`gh pr edit` fails with a Projects (classic) GraphQL error** on older gh. Fall back to:

  ```bash
  gh api -X PATCH "repos/{owner}/{repo}/pulls/<number>" -F body=@"$body"
  ```

## Lookups

PR for the current branch (no output: none exists):

```bash
gh pr view --json number,isDraft,title,body,baseRefName,labels,url 2>/dev/null
```

PR by number or URL (gh accepts either, including URLs in other repos):

```bash
gh pr view <number-or-url> --json number,isDraft,title,body,baseRefName,headRefName,labels,url
```

Default branch:

```bash
gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'
```

Your open PR branches (stacked-branch check):

```bash
gh pr list --author @me --json headRefName --jq '.[].headRefName'
```

Recent merged titles, bots excluded:

```bash
gh pr list --state merged --limit 20 --json title,author \
  --jq '[.[] | select(.author.is_bot | not) | .title] | .[:10][]'
```

Ticket link base:

```bash
gh pr list --state merged --limit 20 --json body --jq '.[].body' \
  | grep -oE 'https?://[^ )>]+/[A-Z][A-Z0-9]+-[0-9]+' \
  | sed -E 's|[A-Z][A-Z0-9]+-[0-9]+$||' \
  | sort | uniq -c | sort -rn | head -1
```

Your recent metadata:

```bash
gh pr list --author @me --state merged --limit 10 \
  --json labels,assignees,latestReviews \
  --jq '[.[] | {labels: [.labels[].name], assignees: [.assignees[].login], reviewers: [.latestReviews[].author.login]}]'
```

Issue details: `gh issue view <n> --json title,body`.

## Templates

First hit wins:

1. `pull_request_template.md` (any case) in `.github/`, the repo root, or `docs/`. GitHub applies this one in the UI, so the team expects it.
2. Exactly one file in `.github/PULL_REQUEST_TEMPLATE/`: use it. Several: ask which.

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
gh pr edit <number-or-url> --body-file "$body"
```

Add `--title` or `--add-label` only if the user approved changing them.

## Verify

```bash
gh pr view <number-or-url> --json number,title,isDraft,baseRefName,url
```
