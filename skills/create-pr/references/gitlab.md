# GitLab (`glab`)

Host commands for `create-pr`. Read Gotchas before running anything.

## Gotchas

- **Pipe to `jq`.** Don't rely on a `--jq` flag; support varies by glab command and version.
- **JSON, not text.** Text layout changes between glab versions. The JSON shape is stable.
- **Always `--description-file`.** Never `--description "$(cat ...)"`. Shell quoting breaks on backticks and diff snippets.
- **Always `--yes`.** The skill already confirmed with the user. glab's own prompt hangs the call.
- **Never `--draft` on update.** It flips a ready MR back to draft.
- **Uploading screenshots.** Ask the user for image paths. Uploads are project-scoped, so they work before the MR exists. Upload first and use the returned `markdown` field in the body:

  ```bash
  curl -sf -H "PRIVATE-TOKEN: ${GITLAB_TOKEN:-$(glab config get token --host <host>)}" \
    -F "file=@before.png" \
    "https://<host>/api/v4/projects/<id>/uploads" | jq -r .markdown
  ```

  Prefer this over `--attach`, which is experimental or absent depending on the glab version. No images yet: leave the placeholders and say so.

## Lookups

MR for the current branch (no output: none exists):

```bash
glab mr view -F json 2>/dev/null \
  | jq '{iid, draft, title, description, target_branch, labels, web_url}'
```

MR by number or URL. Take the iid from `!482` or the URL's trailing number; for a URL in another project add `-R <group>/<project>`:

```bash
glab mr view <iid> -F json \
  | jq '{iid, draft, title, description, target_branch, source_branch, labels, web_url}'
```

Default branch:

```bash
glab repo view -F json | jq -r '.default_branch'
```

Your open MR branches (stacked-branch check):

```bash
glab mr list --author=@me -F json | jq -r '.[].source_branch'
```

Recent merged titles, bots excluded (also drop access-token users named `*_bot_*`):

```bash
glab mr list --merged --per-page=20 -F json \
  | jq -r '.[] | select(.author.username | test("bot|renovate|dependabot") | not) | .title' \
  | head -10
```

Ticket link base:

```bash
glab mr list --merged --per-page=20 -F json \
  | jq -r '.[].description // empty' \
  | grep -oE 'https?://[^ )>]+/[A-Z][A-Z0-9]+-[0-9]+' \
  | sed -E 's|[A-Z][A-Z0-9]+-[0-9]+$||' \
  | sort | uniq -c | sort -rn | head -1
```

Your recent metadata:

```bash
glab mr list --author=@me --merged --per-page=10 -F json \
  | jq '[.[] | {labels, assignees: [.assignees[]?.username], reviewers: [.reviewers[]?.username]}]'
```

Issue details: `glab issue view <n>`.

## Templates

First hit wins:

1. `.gitlab/merge_request_templates/Default.md` (any case). GitLab applies this one in the UI, so the team expects it.
2. Project-level default template, if the API exposes it:

   ```bash
   glab api projects/:id | jq -r '.merge_requests_template // empty'
   ```

3. Exactly one file in `.gitlab/merge_request_templates/`: use it. Several and none is the default: ask which.

## Issues

`#123` links automatically. Close keywords: `Closes`, `Fixes`, `Resolves`.

## Existing MR diff

```bash
glab mr diff <iid>
glab api "projects/:id/merge_requests/<iid>/commits" \
  | jq -r '.[] | "\(.short_id) \(.title)\n\(.message)"'
```

## Create

```bash
glab mr create --yes \
  --draft \
  --source-branch <branch> \
  --target-branch <target> \
  --title "<title>" \
  --description-file "$body" \
  --assignee @me \
  --label "<a>,<b>"
```

Drop `--draft` when draft is false. Drop `--assignee` and `--label` when detection found nothing.

Fork workflow: push to the fork, then create with `-R <upstream>` and `--head <fork>`.

## Update

```bash
glab mr update <iid> --yes --description-file "$body"
```

Add `--title` or `--label` only if the user approved changing them.

## Verify

```bash
glab mr view <iid> -F json | jq '{iid, title, draft, target_branch, web_url}'
```
