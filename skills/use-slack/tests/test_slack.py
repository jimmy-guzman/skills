"""Tests for scripts/slack.py.

Run from the skill folder: python3 -m unittest discover -s tests
"""

import http.server
import json
import os
import pathlib
import subprocess
import sys
import tempfile
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


class Always500(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(500)
        self.end_headers()

    def log_message(self, *a):
        pass


class HangUp(http.server.BaseHTTPRequestHandler):
    """Accepts the request and closes without a response."""

    def handle(self):
        self.rfile.readline()

    def log_message(self, *a):
        pass


class ShortBody(http.server.BaseHTTPRequestHandler):
    """Promises 1000 bytes, sends 7, closes: 403 for the workspace page, 200 for the API."""

    def do_GET(self):
        self._short(403)

    def do_POST(self):
        self._short(200)

    def _short(self, status):
        self.send_response(status)
        self.send_header("Content-Length", "1000")
        self.end_headers()
        self.wfile.write(b"partial")
        self.close_connection = True

    def log_message(self, *a):
        pass


class NotJson(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<html>oops</html>")

    def log_message(self, *a):
        pass


class FakeSlack(http.server.BaseHTTPRequestHandler):
    """Workspace page holds xoxc-fresh when the cookie is good; the API accepts only that token."""

    page = '<script>{"api_token":"xoxc-fresh","x":1}</script>'
    seen: typing.ClassVar[list[str]] = []
    forms: typing.ClassVar[list[dict]] = []
    uploads: typing.ClassVar[list[bytes]] = []
    upload_status = 200
    url_error = None

    def do_GET(self):
        body = self.page if self.headers.get("Cookie") == "d=xoxd-test" else "<html>sign in</html>"
        self._send(body, "text/html", status=403)  # real Slack answers the workspace page with 403

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/upload/x":
            type(self).uploads.append(raw)
            if type(self).upload_status == "garbage":  # malformed status line: BadStatusLine
                self.wfile.write(b"garbage\r\n\r\n")
            elif type(self).upload_status is not None:  # None: hang up without answering
                self._send("OK - 1", "text/plain", status=type(self).upload_status)
            return
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        type(self).seen.append(token)
        type(self).forms.append(dict(urllib.parse.parse_qsl(raw.decode())))
        ok = token == "xoxc-fresh"
        out = {"ok": ok} if ok else {"ok": False, "error": "invalid_auth"}
        if ok and self.path == "/api/files.getUploadURLExternal":
            if type(self).url_error:
                out = {"ok": False, "error": type(self).url_error}
            else:
                out |= {"upload_url": f"http://{self.headers['Host']}/upload/x", "file_id": "F1"}
        self._send(json.dumps(out), "application/json")

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
        FakeSlack.uploads.clear()
        FakeSlack.upload_status = 200
        FakeSlack.url_error = None
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

    def test_upload_sends_bytes_and_completes(self):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d, "notes.txt")
            f.write_bytes(b"hello\x00bytes")
            r = self._run_fake("xoxc-fresh", "upload", str(f), "channel=D1", "thread_ts=1.2",
                               "initial_comment=@-", stdin="see attached\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(FakeSlack.uploads, [b"hello\x00bytes"])
        self.assertEqual(FakeSlack.forms[0], {"filename": "notes.txt", "length": "11"})
        self.assertEqual(FakeSlack.forms[1], {
            "channel_id": "D1", "thread_ts": "1.2", "initial_comment": "see attached",
            "files": json.dumps([{"id": "F1", "title": "notes.txt"}]),
        })

    def test_upload_missing_file_is_one_line(self):
        r = run("upload", "/no/such/file", "channel=C1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no such file", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def _upload(self, *args):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d, "notes.txt")
            f.write_bytes(b"hi")
            return self._run_fake("xoxc-fresh", "upload", str(f), *args)

    def test_upload_without_channel_is_one_line(self):
        r = self._upload()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("upload needs channel", r.stderr)
        self.assertEqual(FakeSlack.forms, [])

    def test_upload_stops_when_url_request_fails(self):
        FakeSlack.url_error = "file_too_large"
        r = self._upload("channel=C1")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("file_too_large", r.stdout)
        self.assertEqual(FakeSlack.uploads, [])
        self.assertEqual(len(FakeSlack.forms), 1)

    def test_upload_post_failure_is_one_line(self):
        FakeSlack.upload_status = 500
        r = self._upload("channel=C1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("upload failed: HTTP 500", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len(FakeSlack.forms), 1)  # never reached completeUploadExternal

    def test_upload_dropped_connection_is_one_line(self):
        FakeSlack.upload_status = None
        r = self._upload("channel=C1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("upload failed", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len(FakeSlack.forms), 1)

    def test_upload_bad_status_line_is_one_line(self):
        FakeSlack.upload_status = "garbage"
        r = self._upload("channel=C1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("upload failed", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def _one_line(self, handler, needle, token="xoxc-test"):
        srv, url = serve(handler)
        try:
            r = run("auth.test", url=url, token=token)
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(needle, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_http_error_is_one_line(self):
        self._one_line(Always500, "HTTP 500 from auth.test")

    def test_non_json_is_one_line(self):
        self._one_line(NotJson, "non-JSON response from auth.test")

    def test_dropped_connection_is_one_line(self):
        self._one_line(HangUp, "cannot reach")  # RemoteDisconnected is an OSError, not a URLError
        self._one_line(HangUp, "cannot reach", token=None)  # via fetch_token

    def test_cut_off_body_is_one_line(self):
        self._one_line(ShortBody, "cannot reach")  # IncompleteRead is not an OSError
        self._one_line(ShortBody, "cannot reach", token=None)  # 403 page body read in fetch_token

    def test_unreachable_host_is_one_line(self):
        for token in ("xoxc-test", None):  # None goes via fetch_token
            r = run("auth.test", token=token)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("cannot reach", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

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
