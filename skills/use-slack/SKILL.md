---
name: use-slack
description: >
  Reads and searches Slack as the user through their browser session (xoxc
  token plus d cookie), no Slack app or bot needed. Use when the user shares a
  Slack link, asks what was said in a channel or thread, wants messages
  searched, a thread summarized, a user or channel looked up, or a message
  posted or replied to. Not for building Slack apps or bots.
compatibility: Requires python3 and SLACK_XOXC_TOKEN, SLACK_D_COOKIE (optionally SLACK_URL) in the environment.
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

- `SLACK_XOXC_TOKEN`: `xoxc-...` token from the logged-in web client.
- `SLACK_D_COOKIE`: value of the `d` cookie (`xoxd-...`) for the workspace domain.
- `SLACK_URL`: `https://<workspace>.slack.com`. Optional; falls back to `https://slack.com`.

If a var is missing in the agent's shell, run with `zsh -ic 'python3 scripts/slack.py ...'` so `~/.zshrc` loads. On `invalid_auth` or `not_authed`, the session expired: ask the user to copy a fresh token (DevTools console on the web client: `JSON.parse(localStorage.localConfig_v2).teams[<team_id>].token`) and `d` cookie (Application > Cookies). Never print either value.

## Common calls

| Need | Method and params |
| --- | --- |
| Search messages | `search.messages query=... count=20 sort=timestamp` (Slack search syntax: `in:#chan`, `from:@user`, `after:YYYY-MM-DD`) |
| Thread | `conversations.replies channel=C... ts=<parent ts>` |
| Channel history | `conversations.history channel=C... limit=50 oldest=<unix ts>` |
| Find a channel id | `search.messages query="in:#name" count=1`, or `conversations.list types=public_channel,private_channel limit=1000` (paginate with `cursor`) |
| Who is U... | `users.info user=U...` |
| Post / reply | `chat.postMessage channel=C... text=... thread_ts=<parent ts>` |

Message links look like `https://<ws>.slack.com/archives/C0123ABCD/p1730730000123456`: channel is `C0123ABCD`, ts is the digits with a dot before the last six (`1730730000.123456`). A `?thread_ts=` query param is the thread parent.

Resolve `<@U...>` mentions with `users.info` before quoting messages back, and paginate with `response_metadata.next_cursor` only when the first page isn't enough.

## Writes

Every write acts as the user, visible to others. Before any method that changes state (anything other than `auth.test`, `search.*`, `*.list`, `*.info`, `*.history`, `*.replies`), show the exact call and target and wait for an explicit yes in the current message.
