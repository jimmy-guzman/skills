#!/usr/bin/env python3
"""Call any Slack Web API method as the user, via the browser session (d cookie).

Usage:
  slack.py <method> [key=value ...]
  slack.py upload <path> channel=<C or D id> [thread_ts=...] [title=...] [initial_comment=@-]

Env: SLACK_D_COOKIE, SLACK_URL (https://<workspace>.slack.com).
Optional SLACK_XOXC_TOKEN; without it, or when it has rotated, the token is
fetched from the workspace page using the cookie.
key=@- reads that value from stdin (one key at most), for multi-line text.
Values that look like JSON (arrays, objects) pass through as strings; Slack parses them.
upload runs files.getUploadURLExternal, POSTs the bytes, then files.completeUploadExternal
(files.upload is retired). Extra key=value pairs go to the completion call.
Prints the JSON response. Exit 1 when Slack returns ok=false.
"""

import http.client
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"
TOKEN_RE = re.compile(r'"api_token":"(xoxc-[^"]+)"')


def fetch_token(base, cookie):
    req = urllib.request.Request(f"{base}/", headers={"Cookie": f"d={cookie}", "User-Agent": UA})
    try:
        try:
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            resp = e  # Slack serves the signed-in page with a 403; the body still has the token
        with resp:
            html = resp.read()
    # OSError: URLError plus timeouts and resets urlopen doesn't wrap; HTTPException: a cut-off body
    except (OSError, http.client.HTTPException) as e:
        raise SystemExit(f"cannot reach {base}: {getattr(e, 'reason', e)}") from None
    m = TOKEN_RE.search(html.decode("utf-8", "replace"))
    if not m:
        raise SystemExit("no token on the workspace page: the d cookie expired, copy a fresh one")
    return m.group(1)


def post(base, method, params, token, cookie):
    req = urllib.request.Request(
        f"{base}/api/{method}",
        data=urllib.parse.urlencode(params).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Cookie": f"d={cookie}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
            break
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise SystemExit(f"HTTP {e.code} from {method}") from None
            if attempt == 2:
                raise SystemExit("HTTP 429 three times, giving up") from None
            time.sleep(int(e.headers.get("Retry-After", "5")))
        except (OSError, http.client.HTTPException) as e:
            raise SystemExit(f"cannot reach {base}: {getattr(e, 'reason', e)}") from None
    try:
        return json.loads(body)
    except ValueError:
        raise SystemExit(f"non-JSON response from {method}: {body[:200]!r}") from None


def call(method, params):
    missing = [v for v in ("SLACK_D_COOKIE", "SLACK_URL") if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)} (try: zsh -ic '...')")
    base = os.environ["SLACK_URL"].rstrip("/")
    cookie = os.environ["SLACK_D_COOKIE"]
    token = os.environ.get("SLACK_XOXC_TOKEN")
    if token:
        out = post(base, method, params, token, cookie)
        if out.get("error") not in ("invalid_auth", "not_authed"):
            return out
    return post(base, method, params, fetch_token(base, cookie), cookie)


def upload(path, params):
    p = pathlib.Path(path)
    if not p.is_file():
        raise SystemExit(f"no such file: {path}")
    if "channel" not in params:
        raise SystemExit("upload needs channel=<C or D id>")
    data = p.read_bytes()
    got = call("files.getUploadURLExternal", {"filename": p.name, "length": len(data)})
    if not got.get("ok"):
        return got
    req = urllib.request.Request(got["upload_url"], data=data,
                                 headers={"Cookie": f"d={os.environ['SLACK_D_COOKIE']}"})
    try:
        urllib.request.urlopen(req, timeout=120).close()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"upload failed: HTTP {e.code}") from None
    except (OSError, http.client.HTTPException) as e:
        raise SystemExit(f"upload failed: {getattr(e, 'reason', e)}") from None
    title = params.pop("title", p.name)
    params["channel_id"] = params.pop("channel")
    params["files"] = json.dumps([{"id": got["file_id"], "title": title}])
    return call("files.completeUploadExternal", params)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    method, args = argv[0], argv[1:]
    if method == "upload":
        if not args:
            raise SystemExit("usage: slack.py upload <path> channel=<id> [key=value ...]")
        path, args = args[0], args[1:]
    bad = [a for a in args if "=" not in a]
    if bad:
        raise SystemExit(f"expected key=value, got: {' '.join(bad)}")
    params = dict(a.split("=", 1) for a in args)
    stdin_keys = [k for k, v in params.items() if v == "@-"]
    if len(stdin_keys) > 1:
        raise SystemExit("only one key can read stdin (@-)")
    if stdin_keys:
        params[stdin_keys[0]] = sys.stdin.read().removesuffix("\n")
    out = upload(path, params) if method == "upload" else call(method, params)
    json.dump(out, sys.stdout, indent=1)
    print()
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
