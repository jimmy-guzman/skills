"""Tests for scripts/lint_body.py.

Run from the skill folder: python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "lint_body.py")


def run(text):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        p = subprocess.run([sys.executable, "-I", SCRIPT, path], capture_output=True, text=True, check=False)
        return p.returncode, p.stdout.splitlines()
    finally:
        os.unlink(path)


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as fh:
        return fh.read()


def words(n):
    return " ".join(["word"] * n)


def what(n):
    return "## What\n\n" + "- item\n" * n


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
        code, out = run("- Toolchain:\n  - `eslint`: 8 -> 9 -> 10 -> 10.12\n")
        self.assertEqual(code, 1)
        self.assertIn("version arrows", out[0])

    def test_prose_commas_pass(self):
        self.assertEqual(run("- `a.ts`: guards empty, null, and missing input\n"), (0, []))

    def test_shared_change_names_a_group(self):
        self.assertEqual(run("- Docs: `a.md`, `b.md`, `c.md`\n"), (0, []))

    def test_two_items_stay_inline(self):
        self.assertEqual(run("- `a.ts`, `b.ts`: share the guard\n"), (0, []))

    def test_file_with_several_changes_nests(self):
        body = (
            "- `image-resize.ts`:\n"
            "  - drag a handle on the right edge to resize; only `width` is saved\n"
            "  - pointer capture stops `DragSelectionView` from also selecting the node\n"
        )
        self.assertEqual(run(body), (0, []))

    def test_good_fixture_is_clean(self):
        self.assertEqual(run(fixture("good.md")), (0, []))

    def test_dense_fixture_is_flagged(self):
        body = fixture("dense.md")
        self.assertNotIn("auto-generated comment", body)
        code, out = run(body)
        self.assertEqual(code, 1)
        joined = "\n".join(out)
        self.assertIn("bullet over 25 words", joined)
        self.assertIn("more than one semicolon", joined)
        self.assertIn("19 bullets under ## What", joined)
        self.assertIn("## Why runs", joined)

    def test_word_limit_at_any_indent(self):
        for prefix in ("- ", "- Group:\n  - "):
            self.assertEqual(run(prefix + words(25) + "\n"), (0, []))
            code, out = run(prefix + words(26) + "\n")
            self.assertEqual(code, 1)
            self.assertIn("bullet over 25 words", out[0])

    def test_code_span_is_one_word(self):
        self.assertEqual(run("- " + words(24) + " `<img src alt width>`\n"), (0, []))

    def test_unmatched_backtick_splits_on_whitespace(self):
        self.assertEqual(run("- " + words(24) + " `<img\n"), (0, []))
        code, out = run("- " + words(24) + " `<img src\n")
        self.assertEqual(code, 1)
        self.assertIn("bullet over 25 words", out[0])

    def test_semicolons(self):
        self.assertEqual(run("- a; b\n"), (0, []))
        code, out = run("  - a; b; c\n")
        self.assertEqual(code, 1)
        self.assertIn("more than one semicolon", out[0])

    def test_top_level_bullets_under_what(self):
        self.assertEqual(run(what(6)), (0, []))
        self.assertEqual(run(what(6) + "  - sub\n  - sub\n"), (0, []))
        code, out = run(what(7))
        self.assertEqual(code, 1)
        self.assertEqual(out, [out[0]])
        self.assertIn(":1: 7 top-level bullets under ## What", out[0])

    def test_total_bullets_under_what(self):
        self.assertEqual(run(what(2) + "  - sub\n" * 8), (0, []))
        code, out = run(what(2) + "  - sub\n" * 9)
        self.assertEqual(code, 1)
        self.assertIn(":1: 11 bullets under ## What", out[0])

    def test_why_paragraphs(self):
        self.assertEqual(run("## Why\n\nCloses #1.\n\nOne.\n\nTwo.\n"), (0, []))
        code, out = run("## Why\n\nOne.\n\nTwo.\n\nThree.\n")
        self.assertEqual(code, 1)
        self.assertIn(":1: 3 paragraphs under ## Why", out[0])

    def test_ticket_reference_forms(self):
        for ticket in ("#12", "fixes PROJ-9", "Relates to [PROJ-9](https://x.atlassian.net/browse/PROJ-9)."):
            self.assertEqual(run(f"## Why\n\n{ticket}\n\nOne.\n\nTwo.\n"), (0, []))

    def test_why_words(self):
        self.assertEqual(run("## Why\n\nCloses #1.\n\n" + words(80) + "\n"), (0, []))
        code, out = run("## Why\n\n" + words(81) + "\n")
        self.assertEqual(code, 1)
        self.assertIn(":1: ## Why runs 81 words", out[0])

    def test_fenced_blocks_skipped(self):
        body = "- Shape:\n\n  ```diff\n  - " + words(30) + "; a; b\n  ```\n"
        self.assertEqual(run(body), (0, []))

    def test_bad_usage(self):
        p = subprocess.run([sys.executable, "-I", SCRIPT], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)
        p = subprocess.run([sys.executable, "-I", SCRIPT, "/no/such/file.md"], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
