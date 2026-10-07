"""Tests for scripts/lint_body.py.

Run from the skill folder: python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "lint_body.py")


def run(text):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        p = subprocess.run([sys.executable, "-I", SCRIPT, path], capture_output=True, text=True, check=False)
        return p.returncode, p.stdout.splitlines()
    finally:
        os.unlink(path)


class LintBody(unittest.TestCase):
    def test_clean_body(self):
        body = "## What\n\n- `tabs.ts`: keep the last tab active\n\n## Why\n\nClosing the last tab left none active.\n"
        self.assertEqual(run(body), (0, []))

    def test_characters_flagged_with_line_numbers(self):
        code, out = run("ok\nuse — here\nand “quotes”\nit’s\nmid · dot\n2–3\n")
        self.assertEqual(code, 1)
        joined = "\n".join(out)
        self.assertIn(":2: em dash", joined)
        self.assertIn(":3: curly quote", joined)
        self.assertIn(":4: curly apostrophe", joined)
        self.assertIn(":5: middle dot", joined)
        self.assertIn(":6: en dash", joined)

    def test_three_version_arrows(self):
        code, out = run("- `eslint`: 8 -> 9 -> 10 -> 10.12\n")
        self.assertEqual(code, 1)
        self.assertIn("version arrows", out[0])

    def test_three_backticked_items(self):
        code, out = run("- Bumped `eslint`, `vue`, and `@eslint/js`\n")
        self.assertEqual(code, 1)
        self.assertIn("3+ named items", out[0])

    def test_prose_commas_pass(self):
        self.assertEqual(run("- `a.ts`: guards empty, null, and missing input\n"), (0, []))

    def test_sub_bullets_are_not_checked_for_lists(self):
        self.assertEqual(run("- Toolchain:\n  - `a`, `b`, `c`\n"), (0, []))

    def test_two_items_stay_inline(self):
        self.assertEqual(run("- `a.ts`, `b.ts`: share the guard\n"), (0, []))

    def test_bad_usage(self):
        p = subprocess.run([sys.executable, "-I", SCRIPT], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)
        p = subprocess.run([sys.executable, "-I", SCRIPT, "/no/such/file.md"], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
