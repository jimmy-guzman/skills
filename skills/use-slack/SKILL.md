---
name: use-slack
description: >
  Reads and searches Slack as the user through their browser session (the d
  cookie), no Slack app or bot needed. Use when the user shares a
  Slack link, asks what was said in a channel or thread, wants messages
  searched, a thread summarized, a user or channel looked up, or a message
  posted or replied to. Not for building Slack apps or bots.
compatibility: Requires python3 and SLACK_D_COOKIE, SLACK_URL (optionally SLACK_XOXC_TOKEN) in the environment.
---

# use-slack

`scripts/slack.py <method> [key=value ...]` calls any [Slack Web API](https://api.slack.com/methods) method as the user and prints the JSON. Stdlib only.

```sh
python3 scripts/slack.py auth.test
python3 scripts/slack.py search.messages query="deploy failed in:#general after:2026-10-01" count=20
python3 scripts/slack.py conversations.replies channel=C0123ABCD ts=1730730000.123456
```

## Auth

Env vars, usually exported from `~/.zshrc`:

- `SLACK_D_COOKIE`: value of the `d` cookie (`xoxd-...`), from DevTools > Application > Cookies on `https://app.slack.com`.
- `SLACK_URL`: `https://<workspace>.slack.com`.
- `SLACK_XOXC_TOKEN`: optional. The script fetches a fresh `xoxc-...` token from the workspace page with the cookie when this is unset or rejected.

If a var is missing in the agent's shell, run with `zsh -ic 'python3 scripts/slack.py ...'` so `~/.zshrc` loads. On "the d cookie expired", ask the user to copy a fresh `d` cookie. Never print the cookie or token.

## Common calls

| Need | Method and params |
| --- | --- |
| Search messages | `search.messages query=... count=20 sort=timestamp` (Slack search syntax: `in:#chan`, `from:@user`, `after:YYYY-MM-DD`) |
| Thread | `conversations.replies channel=C... ts=<parent ts>` |
| Channel history | `conversations.history channel=C... limit=50 oldest=<unix ts>` |
| Find a channel id | `search.messages query="in:#name" count=1`, or `conversations.list types=public_channel,private_channel limit=1000` (paginate with `cursor`) |
| Who is U... | `users.info user=U...` |
| Post / reply | `chat.postMessage channel=C... text=... thread_ts=<parent ts>` (`text=@-` reads stdin) |
| Edit a message | `chat.update channel=C... ts=<msg ts> parse=none text=@-` (without `parse=none`, Slack escapes `<url\|label>` links on edit) |

For multi-line text, links, or quotes, pass `text=@-` and feed a quoted heredoc outside the `zsh -ic '...'` string so nothing needs escaping:

```sh
zsh -ic 'python3 scripts/slack.py chat.postMessage channel=C0123ABCD thread_ts=1730730000.123456 text=@-' <<'EOF'
All addressed:
• <https://github.com/o/r/pull/1|PR #1>
_posted via use-slack_
EOF
```

Message links look like `https://<ws>.slack.com/archives/C0123ABCD/p1730730000123456`: channel is `C0123ABCD`, ts is the digits with a dot before the last six (`1730730000.123456`). A `?thread_ts=` query param is the thread parent.

Resolve `<@U...>` mentions with `users.info` before quoting messages back, and paginate with `response_metadata.next_cursor` only when the first page isn't enough.

## Writes

Every write acts as the user, visible to others. Before any method that changes state (anything other than `auth.test`, `search.*`, `*.list`, `*.info`, `*.history`, `*.replies`), show the exact call and target and wait for an explicit yes in the current message.

When a post has links, ask in the same step whether to show link previews; if not, add `unfurl_links=false unfurl_media=false` to `chat.postMessage`. Decide before posting: an edit with `chat.update` drops existing previews and can't add them back.
