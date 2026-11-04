#!/usr/bin/env python3
"""Call any Slack Web API method as the user, via the browser session (d cookie).

Usage:
  slack.py <method> [key=value ...]

Env: SLACK_D_COOKIE, SLACK_URL (https://<workspace>.slack.com).
Optional SLACK_XOXC_TOKEN; without it, or when it has rotated, the token is
fetched from the workspace page using the cookie.
Values that look like JSON (arrays, objects) pass through as strings; Slack parses them.
Prints the JSON response. Exit 1 when Slack returns ok=false.
"""

import json
import os
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read()
    except urllib.error.HTTPError as e:
        html = e.read()  # Slack serves the signed-in page with a 403; the body still has the token
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
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            if attempt == 2:
                raise SystemExit("HTTP 429 three times, giving up") from None
            time.sleep(int(e.headers.get("Retry-After", "5")))


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


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    bad = [a for a in argv[1:] if "=" not in a]
    if bad:
        raise SystemExit(f"expected key=value, got: {' '.join(bad)}")
    params = dict(a.split("=", 1) for a in argv[1:])
    out = call(argv[0], params)
    json.dump(out, sys.stdout, indent=1)
    print()
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
