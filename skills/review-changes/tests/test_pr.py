"""Tests for scripts/pr.py.

Unit tests cover the diff-hunk parser and target parsing. End-to-end tests
run the script against a fake gh on PATH, so nothing reaches GitHub.

Run from the skill root: python3 -m unittest discover -s tests
"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "pr.py")
spec = importlib.util.spec_from_file_location("pr", SCRIPT)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)

PATCH = "@@ -80,6 +80,7 @@ fn\n ctx80\n ctx81\n-old82\n+new82\n+new83\n ctx84\n ctx85\n\\ No newline at end of file\n"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
body = sys.stdin.read() if "--input" in a else None
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({"argv": a, "body": body}) + "\n")
ep = next(x for x in a if x.startswith("repos/") or x == "graphql")
post = "POST" in a
if ep == "graphql":
    print(json.dumps({"data": {"repository": {"pullRequest": {
        "state": os.environ.get("FAKE_STATE", "OPEN"), "isDraft": False,
        "headRefOid": "1a2b3c4d5e6f", "title": "Tabs", "body": "Closes #41",
        "author": {"login": "sam"},
        "comments": {"nodes": [], "pageInfo": {"hasPreviousPage": False}},
        "reviews": {"nodes": [], "pageInfo": {"hasPreviousPage": False}},
        "reviewThreads": {"pageInfo": {"hasNextPage": False}, "nodes": [
            {"isResolved": False, "isOutdated": False, "path": "src/tabs.ts", "line": 83,
             "originalLine": 83, "comments": {"nodes": [
                 {"body": "<!-- review-changes: 1a2b3c4 -->\nsame body"}]}}]}}}}}))
elif ep.endswith("/files"):
    print(json.dumps([[{"filename": "src/tabs.ts", "patch": os.environ["FAKE_PATCH"],
                        "additions": 2, "deletions": 1}]]))
elif ep.endswith("/comments") and not post and "/pulls/" in ep:
    print(json.dumps([[{"path": "src/tabs.ts", "line": 83, "body": "same body"}]]))
elif ep.endswith("/comments") and not post:
    print(json.dumps([[]]))
else:
    print(json.dumps({"id": 991}))
'''


class CommentableLines(unittest.TestCase):
    def test_added_and_context_lines(self):
        lines = pr.commentable_lines(PATCH)
        self.assertEqual(lines, {80: 80, 81: 81, 82: None, 83: None, 84: 83, 85: 84})

    def test_two_hunks(self):
        patch = "@@ -1,2 +1,2 @@\n a\n-b\n+B\n@@ -10,1 +10,2 @@\n j\n+k\n"
        self.assertEqual(pr.commentable_lines(patch), {1: 1, 2: None, 10: 10, 11: None})

    def test_missing_patch(self):
        self.assertEqual(pr.commentable_lines(None), {})


class Targets(unittest.TestCase):
    def test_refs(self):
        self.assertEqual(pr.parse_target("!482", None, None, None), ("gitlab", None, None, 482))
        self.assertEqual(pr.parse_target("#285", "github", None, None), ("github", None, None, 285))

    def test_urls(self):
        self.assertEqual(pr.parse_target("https://github.com/acme/app/pull/12", None, None, None),
                         ("github", "acme/app", "github.com", 12))
        self.assertEqual(
            pr.parse_target("https://gl.acme.io/grp/sub/app/-/merge_requests/7/diffs", None, None, None),
            ("gitlab", "grp/sub/app", "gl.acme.io", 7))

    def test_bad_target(self):
        with self.assertRaises(pr.Fail) as e:
            pr.parse_target("abc", "github", None, None)
        self.assertEqual(e.exception.code, 2)

    def test_line_spans(self):
        self.assertEqual(pr.parse_lines("88"), (88, 88))
        self.assertEqual(pr.parse_lines("70-74"), (70, 74))
        for bad in ("74-70", "x", ""):
            with self.assertRaises(pr.Fail):
                pr.parse_lines(bad)

    def test_marker_stripped_for_dedupe(self):
        self.assertEqual(pr.norm("<!-- review-changes: abc1234 -->\nbody\n"), "body")


class EndToEndGitHub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        bindir = os.path.join(self.tmp.name, "bin")
        os.makedirs(bindir)
        gh = os.path.join(bindir, "gh")
        with open(gh, "w") as fh:
            fh.write(FAKE_GH)
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)
        self.log = os.path.join(self.tmp.name, "log")
        self.env = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"],
                    "FAKE_LOG": self.log, "FAKE_PATCH": PATCH}
        self.body = os.path.join(self.tmp.name, "body.md")
        self.write_body("Fix it")

    def tearDown(self):
        self.tmp.cleanup()

    def write_body(self, text):
        with open(self.body, "w") as fh:
            fh.write(text)

    def run_pr(self, *args, **env):
        p = subprocess.run([sys.executable, "-I", SCRIPT, *args, "--provider", "github"],
                           env={**self.env, **env}, capture_output=True, text=True, cwd=self.tmp.name)
        return p.returncode, json.loads(p.stdout) if p.stdout.strip() else None, p.stderr

    def posted(self):
        with open(self.log) as fh:
            return [json.loads(l) for l in fh if '"POST"' in l]

    def test_state(self):
        code, out, _ = self.run_pr("state", "285")
        self.assertEqual(code, 0)
        self.assertEqual((out["state"], out["head_sha"], out["body"]), ("open", "1a2b3c4d5e6f", "Closes #41"))
        self.assertEqual(out["threads"]["open"], 1)
        self.assertTrue(out["reviewed_at_head"])
        self.assertEqual(out["files"], [{"path": "src/tabs.ts", "additions": 2, "deletions": 1}])

    def test_inline_with_marker(self):
        code, out, _ = self.run_pr("post", "285", "--head", "1a2b3c4", "--path", "src/tabs.ts",
                                   "--line", "82", "--body-file", self.body, "--marker")
        self.assertEqual((code, out["posted"]), (0, "inline"))
        sent = json.loads(self.posted()[0]["body"])
        self.assertEqual((sent["line"], sent["side"], sent["commit_id"]), (82, "RIGHT", "1a2b3c4d5e6f"))
        self.assertTrue(sent["body"].startswith("<!-- review-changes: 1a2b3c4d5e6f -->"))

    def test_range_inside_one_hunk(self):
        self.run_pr("post", "285", "--path", "src/tabs.ts", "--line", "81-84", "--body-file", self.body)
        sent = json.loads(self.posted()[0]["body"])
        self.assertEqual((sent["start_line"], sent["line"]), (81, 84))

    def test_line_outside_diff_falls_back_to_general(self):
        code, out, _ = self.run_pr("post", "285", "--path", "src/tabs.ts", "--line", "52",
                                   "--body-file", self.body)
        self.assertEqual((code, out["posted"]), (0, "general"))
        self.assertIn("outside the diff", out["reason"])
        self.assertIn("/issues/285/comments", " ".join(self.posted()[0]["argv"]))

    def test_duplicate_is_skipped(self):
        self.write_body("same body")
        code, out, _ = self.run_pr("post", "285", "--path", "src/tabs.ts", "--line", "83",
                                   "--body-file", self.body)
        self.assertEqual((code, out["posted"]), (0, "skipped"))
        self.assertEqual(self.posted(), [])

    def test_head_moved_exits_3(self):
        code, _, err = self.run_pr("post", "285", "--head", "deadbeef", "--body-file", self.body)
        self.assertEqual(code, 3)
        self.assertIn("re-review", err)

    def test_merged_exits_4(self):
        code, _, err = self.run_pr("post", "285", "--body-file", self.body, FAKE_STATE="MERGED")
        self.assertEqual(code, 4)
        self.assertEqual(self.posted(), [])
        self.assertIn("--allow-closed", err)

    def test_merged_with_allow_closed_posts_inline(self):
        code, out, _ = self.run_pr("post", "285", "--allow-closed",
                                   "--path", "src/tabs.ts", "--line", "82",
                                   "--body-file", self.body, FAKE_STATE="MERGED")
        self.assertEqual((code, out["posted"]), (0, "inline"))

    def test_merged_with_allow_closed_still_checks_head(self):
        code, _, _ = self.run_pr("post", "285", "--allow-closed",
                                 "--head", "deadbeef",
                                 "--body-file", self.body, FAKE_STATE="MERGED")
        self.assertEqual(code, 3)
        self.assertEqual(self.posted(), [])

    def test_dry_run_posts_nothing(self):
        code, out, _ = self.run_pr("post", "285", "--path", "src/tabs.ts", "--line", "82",
                                   "--body-file", self.body, "--dry-run")
        self.assertEqual((code, out["posted"]), (0, "dry-run:inline"))
        self.assertEqual(self.posted(), [])


if __name__ == "__main__":
    unittest.main()
