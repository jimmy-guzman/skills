"""Tests for scripts/lint_commit.py.

Run from the skill folder: python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "lint_commit.py")


def run(text):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        p = subprocess.run([sys.executable, "-I", SCRIPT, path], capture_output=True, text=True, check=False)
        return p.returncode, p.stdout.splitlines()
    finally:
        os.unlink(path)


class LintCommit(unittest.TestCase):
    def test_clean_subject_passes(self):
        code, lines = run("fix(commit): skip reverts in the sample\n")
        self.assertEqual(code, 0)
        self.assertEqual(lines, [])

    def test_past_tense_verb_flagged(self):
        code, lines = run("fix(commit): added a new check\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("not imperative" in line for line in lines))

    def test_gerund_verb_flagged(self):
        code, lines = run("fix(commit): adding a new check\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("not imperative" in line for line in lines))

    def test_over_length_subject_flagged(self):
        subject = "fix(commit): " + "a very long subject line that goes way past the limit"
        code, lines = run(subject + "\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("keep it to" in line for line in lines))

    def test_custom_header_max_respected(self):
        subject = "fix(commit): a somewhat longish subject line right here"
        code, _lines = run(subject + "\n")
        self.assertEqual(code, 1)

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(subject + "\n")
            path = fh.name
        try:
            p = subprocess.run(
                [sys.executable, "-I", SCRIPT, path, "100"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p.returncode, 0)
        finally:
            os.unlink(path)

    def test_trailing_period_flagged(self):
        code, lines = run("fix(commit): skip reverts in the sample.\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("period" in line for line in lines))

    def test_em_dash_in_body_flagged(self):
        code, lines = run("fix(commit): skip reverts\n\nThis matters — a lot.\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("em dash" in line for line in lines))

    def test_curly_quotes_flagged(self):
        code, lines = run("fix(commit): skip the “reverts” case\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("curly quote" in line for line in lines))

    def test_clean_multiline_body_passes(self):
        code, lines = run(
            "fix(commit): skip reverts in the sample\n"
            "\n"
            "Reverts were counted toward the dominant shape, skewing detection.\n"
        )
        self.assertEqual(code, 0)
        self.assertEqual(lines, [])

    def test_empty_file_is_clean(self):
        code, lines = run("")
        self.assertEqual(code, 0)
        self.assertEqual(lines, [])

    def test_missing_file_errors(self):
        p = subprocess.run(
            [sys.executable, "-I", SCRIPT, "/no/such/file.md"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p.returncode, 2)

    def test_bad_args_print_usage(self):
        p = subprocess.run([sys.executable, "-I", SCRIPT], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
