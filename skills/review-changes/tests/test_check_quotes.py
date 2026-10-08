"""Tests for scripts/check_quotes.py.

Run from the skill root: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "check_quotes.py")

COMMITTED = """\
a
b
  const active = next[index] ?? null;  // keep last
d
label = "it’s"
x  =   y
"""

WORKING = "new top\n" + COMMITTED


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class CheckQuotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = cls.tmp.name
        git(cls.repo, "init", "-q")
        git(cls.repo, "config", "user.email", "t@t")
        git(cls.repo, "config", "user.name", "t")
        os.makedirs(os.path.join(cls.repo, "src"))
        with open(os.path.join(cls.repo, "src", "tabs.ts"), "w") as fh:
            fh.write(COMMITTED)
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "one")
        cls.sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cls.repo,
                                 capture_output=True, text=True).stdout.strip()
        with open(os.path.join(cls.repo, "src", "tabs.ts"), "w") as fh:
            fh.write(WORKING)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_check(self, findings, rev=None):
        args = [sys.executable, "-I", SCRIPT] + (["--rev", rev] if rev else []) + ["-"]
        p = subprocess.run(args, cwd=self.repo, input=json.dumps(findings),
                           capture_output=True, text=True)
        out = json.loads(p.stdout) if p.stdout.strip() else None
        return p.returncode, out

    def one(self, line, quote, rev="HEAD", path="src/tabs.ts"):
        code, out = self.run_check([{"id": 1, "path": path, "line": line, "quote": quote}],
                                   self.sha if rev == "HEAD" else rev)
        return code, out[0]

    def test_ok_at_rev(self):
        code, r = self.one("3", "const active = next[index] ?? null;")
        self.assertEqual((code, r["status"]), (0, "ok"))

    def test_quote_without_trailing_comment_is_ok(self):
        self.assertEqual(self.one("3", "next[index] ?? null")[1]["status"], "ok")

    def test_range_contains_quote(self):
        self.assertEqual(self.one("2-4", "next[index]")[1]["status"], "ok")

    def test_whitespace_runs_collapse(self):
        self.assertEqual(self.one("6", "x = y")[1]["status"], "ok")
        self.assertEqual(self.one("3", "const   active =  next[index]")[1]["status"], "ok")

    def test_curly_quotes_match_straight(self):
        self.assertEqual(self.one("5", 'label = "it\'s"')[1]["status"], "ok")
        self.assertEqual(self.one("5", "label = “it’s”")[1]["status"], "ok")

    def test_case_still_matters(self):
        self.assertEqual(self.one("3", "CONST active")[1]["status"], "missing")

    def test_moved_reports_new_line(self):
        code, r = self.one("1", "next[index]")
        self.assertEqual((code, r["status"], r["found_at"]), (1, "moved", [3]))

    def test_working_tree_without_rev(self):
        code, r = self.one("3", "next[index]", rev=None)
        self.assertEqual((r["status"], r["found_at"]), ("moved", [4]))
        self.assertEqual(self.one("4", "next[index]", rev=None)[1]["status"], "ok")

    def test_missing_returns_nearby_lines(self):
        code, r = self.one("3", "return made_up();")
        self.assertEqual((code, r["status"]), (1, "missing"))
        self.assertEqual(sorted(r["near"], key=int), ["1", "2", "3", "4", "5", "6"])
        self.assertIn("next[index]", r["near"]["3"])

    def test_missing_or_empty_quote_is_per_finding(self):
        code, out = self.run_check([
            {"id": 1, "path": "src/tabs.ts", "line": "3", "quote": "next[index]"},
            {"id": 2, "path": "src/tabs.ts", "line": "1-3"},
            {"id": 3, "path": "src/tabs.ts", "line": "2", "quote": "   "},
        ], self.sha)
        self.assertEqual(code, 1)
        self.assertEqual([r["status"] for r in out], ["ok", "no-quote", "no-quote"])

    def test_no_file(self):
        self.assertEqual(self.one("1", "x", path="src/nope.ts")[1]["status"], "no-file")

    def test_mixed_batch_exit_code(self):
        code, out = self.run_check([
            {"id": 1, "path": "src/tabs.ts", "line": "3", "quote": "next[index]"},
            {"id": 2, "path": "src/tabs.ts", "line": "1", "quote": "next[index]"},
        ], self.sha)
        self.assertEqual(code, 1)
        self.assertEqual([r["status"] for r in out], ["ok", "moved"])

    def test_extra_fields_are_ignored(self):
        code, out = self.run_check([{"id": "B1", "path": "src/tabs.ts", "line": "3", "quote": "next[index]",
                                     "severity": "Major", "fix": "x", "removed": False}], self.sha)
        self.assertEqual((code, out), (0, [{"id": "B1", "status": "ok"}]))

    def test_bad_input_exits_2(self):
        p = subprocess.run([sys.executable, "-I", SCRIPT, "-"], cwd=self.repo,
                           input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        code, _ = self.run_check([{"id": 1, "path": "src/tabs.ts", "line": "4-2", "quote": "x"}])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
