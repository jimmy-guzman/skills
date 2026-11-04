"""Tests for scripts/slack.py.

Run from the skill folder: python3 -m unittest discover -s tests
"""

import http.server
import os
import pathlib
import subprocess
import sys
import threading
import time
import typing
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "slack.py"


def run(*args, url=None):
    env = {**os.environ, "SLACK_XOXC_TOKEN": "xoxc-test", "SLACK_D_COOKIE": "xoxd-test"}
    if url:
        env["SLACK_URL"] = url
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args],
                          env=env, capture_output=True, text=True, timeout=30, check=False)


class Always429(http.server.BaseHTTPRequestHandler):
    hits: typing.ClassVar[list[float]] = []

    def do_POST(self):
        type(self).hits.append(time.monotonic())
        self.send_response(429)
        self.send_header("Retry-After", "1")
        self.end_headers()

    def log_message(self, *a):
        pass


class SlackTest(unittest.TestCase):
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
