"""Tests for scripts/slack.py.

Run from the skill folder: python3 -m unittest discover -s tests
"""

import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import typing
import unittest
import urllib.parse

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "slack.py"


def run(*args, url=None, token="xoxc-test", stdin=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SLACK_")}
    env["SLACK_D_COOKIE"] = "xoxd-test"
    env["SLACK_URL"] = url or "http://127.0.0.1:9"
    if token:
        env["SLACK_XOXC_TOKEN"] = token
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args],
                          env=env, input=stdin, capture_output=True, text=True, timeout=30, check=False)


class Always429(http.server.BaseHTTPRequestHandler):
    hits: typing.ClassVar[list[float]] = []

    def do_POST(self):
        type(self).hits.append(time.monotonic())
        self.send_response(429)
        self.send_header("Retry-After", "1")
        self.end_headers()

    def log_message(self, *a):
        pass


class FakeSlack(http.server.BaseHTTPRequestHandler):
    """Workspace page holds xoxc-fresh when the cookie is good; the API accepts only that token."""

    page = '<script>{"api_token":"xoxc-fresh","x":1}</script>'
    seen: typing.ClassVar[list[str]] = []
    forms: typing.ClassVar[list[dict]] = []

    def do_GET(self):
        body = self.page if self.headers.get("Cookie") == "d=xoxd-test" else "<html>sign in</html>"
        self._send(body, "text/html", status=403)  # real Slack answers the workspace page with 403

    def do_POST(self):
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        type(self).seen.append(token)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        type(self).forms.append(dict(urllib.parse.parse_qsl(body)))
        ok = token == "xoxc-fresh"
        self._send(json.dumps({"ok": ok} if ok else {"ok": False, "error": "invalid_auth"}),
                   "application/json")

    def _send(self, body, ctype, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


def serve(handler):
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


class SlackTest(unittest.TestCase):
    def setUp(self):
        FakeSlack.seen.clear()
        FakeSlack.forms.clear()
        FakeSlack.page = '<script>{"api_token":"xoxc-fresh","x":1}</script>'

    def _run_fake(self, token, *args, stdin=None):
        srv, url = serve(FakeSlack)
        try:
            return run(*(args or ("auth.test",)), url=url, token=token, stdin=stdin)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_at_dash_reads_value_from_stdin(self):
        r = self._run_fake("xoxc-fresh", "chat.postMessage", "channel=C1", "text=@-",
                           stdin="a 'q' \"q\"\n• <https://x|y>\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(FakeSlack.forms, [{"channel": "C1", "text": "a 'q' \"q\"\n• <https://x|y>"}])

    def test_two_stdin_keys_is_a_usage_error(self):
        r = run("chat.postMessage", "text=@-", "blocks=@-")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("only one key can read stdin", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_fetches_token_from_cookie_when_unset(self):
        r = self._run_fake(token=None)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(FakeSlack.seen, ["xoxc-fresh"])

    def test_refetches_when_set_token_is_stale(self):
        r = self._run_fake(token="xoxc-stale")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(FakeSlack.seen, ["xoxc-stale", "xoxc-fresh"])

    def test_expired_cookie_says_so(self):
        FakeSlack.page = "<html>sign in</html>"
        r = self._run_fake(token=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("d cookie expired", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_arg_without_equals_is_a_usage_error(self):
        r = run("conversations.replies", "C0123ABCD")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("expected key=value, got: C0123ABCD", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_gives_up_after_third_429_without_sleeping(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), Always429)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = run("auth.test", url=f"http://127.0.0.1:{srv.server_port}")
            done = time.monotonic()
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(Always429.hits), 3)
        self.assertIn("429", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        # Retry-After is 1s, so a sleep after the last 429 would show as >= 1s here.
        self.assertLess(done - Always429.hits[-1], 0.9)


if __name__ == "__main__":
    unittest.main()
