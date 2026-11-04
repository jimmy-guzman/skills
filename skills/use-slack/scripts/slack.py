#!/usr/bin/env python3
"""Call any Slack Web API method as the user, via the browser session (xoxc token + d cookie).

Usage:
  slack.py <method> [key=value ...]

Env: SLACK_XOXC_TOKEN, SLACK_D_COOKIE, SLACK_URL (https://<workspace>.slack.com).
Values that look like JSON (arrays, objects) pass through as strings; Slack parses them.
Prints the JSON response. Exit 1 when Slack returns ok=false.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def call(method, params):
    missing = [v for v in ("SLACK_XOXC_TOKEN", "SLACK_D_COOKIE") if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)} (try: zsh -ic '...')")
    base = (os.environ.get("SLACK_URL") or "https://slack.com").rstrip("/")
    req = urllib.request.Request(
        f"{base}/api/{method}",
        data=urllib.parse.urlencode(params).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['SLACK_XOXC_TOKEN']}",
            "Cookie": f"d={os.environ['SLACK_D_COOKIE']}",
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
