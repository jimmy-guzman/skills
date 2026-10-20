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


def write(text, suffix):
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as fh:
        fh.write(text)
        return fh.name


def run(text, files=None):
    """Returns (exit code, output lines). Warnings keep the "warning: " prefix."""
    paths = [write(text, ".md")]
    args = [sys.executable, "-I", SCRIPT, paths[0]]
    if files is not None:
        paths.append(write("\n".join(files) + "\n", ".txt"))
        args += ["--files", paths[1]]
    try:
        p = subprocess.run(args, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout.splitlines()
    finally:
        for path in paths:
            os.unlink(path)


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as fh:
        return fh.read()


def words(n):
    return " ".join(["word"] * n)


def shaped(why="Nothing closed the last tab.", approach=None, review=None, ticket=None):
    parts = []
    if ticket:
        parts.append(ticket)
    parts.append(f"### Why\n\n{why}")
    if approach is not None:
        parts.append(f"### Approach\n\n{approach}")
    if review is not None:
        parts.append(f"### Review\n\n{review}")
    return "\n\n".join(parts) + "\n"


def bullets(n, indent=""):
    return "".join(f"{indent}- item\n" for _ in range(n))


class Characters(unittest.TestCase):
    def test_flagged_with_line_numbers(self):
        code, out = run("ok\nuse — here\nand “quotes”\nit’s\nmid · dot\n2–3\n")
        self.assertEqual(code, 1)
        joined = "\n".join(out)
        self.assertIn(":2: em dash", joined)
        self.assertIn(":3: curly quote", joined)
        self.assertIn(":4: curly apostrophe", joined)
        self.assertIn(":5: middle dot", joined)
        self.assertIn(":6: en dash", joined)


class Bullets(unittest.TestCase):
    def test_three_version_arrows(self):
        code, out = run("- `eslint`: 8 -> 9 -> 10 -> 10.12\n")
        self.assertEqual(code, 0)
        self.assertIn("warning: 3+ version arrows", out[0])
        code, out = run("- Toolchain:\n  - `eslint`: 8 -> 9 -> 10 -> 10.12\n")
        self.assertEqual(code, 0)
        self.assertIn("warning: 3+ version arrows", out[0])

    def test_prose_commas_pass(self):
        self.assertEqual(run("- `a.ts`: guards empty, null, and missing input\n"), (0, []))

    def test_shared_change_names_a_group(self):
        self.assertEqual(run("- Docs: `a.md`, `b.md`, `c.md`\n"), (0, []))

    def test_file_with_several_changes_nests(self):
        body = (
            "- `image-resize.ts`:\n"
            "  - drag a handle on the right edge to resize; only `width` is saved\n"
            "  - pointer capture stops `DragSelectionView` from also selecting the node\n"
        )
        self.assertEqual(run(body), (0, []))

    def test_word_limit_at_any_indent(self):
        for prefix in ("- ", "- Group:\n  - "):
            self.assertEqual(run(prefix + words(25) + "\n"), (0, []))
            code, out = run(prefix + words(26) + "\n")
            self.assertEqual(code, 0)
            self.assertIn("warning: bullet over 25 words", out[0])

    def test_code_span_is_one_word(self):
        self.assertEqual(run("- " + words(24) + " `<img src alt width>`\n"), (0, []))

    def test_unmatched_backtick_splits_on_whitespace(self):
        self.assertEqual(run("- " + words(24) + " `<img\n"), (0, []))
        code, out = run("- " + words(24) + " `<img src\n")
        self.assertEqual(code, 0)
        self.assertIn("warning: bullet over 25 words", out[0])

    def test_semicolons(self):
        self.assertEqual(run("- a; b\n"), (0, []))
        code, out = run("  - a; b; c\n")
        self.assertEqual(code, 0)
        self.assertIn("warning: more than one semicolon", out[0])

    def test_fenced_blocks_skipped(self):
        body = "- Shape:\n\n  ```diff\n  - " + words(30) + "; a; b\n  ```\n"
        self.assertEqual(run(body), (0, []))

    def test_counts_only_capped_in_default_shape(self):
        self.assertEqual(run("## Changes\n\n" + bullets(12)), (0, []))
        code, out = run(shaped(approach="Grouped.") + bullets(7))
        self.assertEqual(code, 0)
        self.assertIn("warning: 7 top-level bullets", out[0])
        self.assertEqual(run(shaped(approach="Grouped.") + bullets(2) + bullets(8, "  ")), (0, []))
        code, out = run(shaped(approach="Grouped.") + bullets(2) + bullets(9, "  "))
        self.assertEqual(code, 0)
        self.assertIn("warning: 11 bullets", out[0])


class Phrases(unittest.TestCase):
    def test_assertions_without_evidence(self):
        for phrase in ("All tests pass.", "Tested locally.", "It is fully backward compatible.", "Works as expected."):
            code, out = run(f"- `a.ts`: {phrase}\n")
            self.assertEqual(code, 1, phrase)
            self.assertIn("assertion without evidence", out[0])

    def test_self_grading_words(self):
        code, out = run("- `a.ts`: a robust, comprehensive guard that properly handles input\n")
        self.assertEqual(code, 1)
        joined = "\n".join(out)
        for word in ("robust", "comprehensive", "properly"):
            self.assertIn(f'self-grading word "{word}"', joined)

    def test_plain_claims_pass(self):
        self.assertEqual(run("- `a.ts`: the guard rejects empty input; `guard.test.ts` fails on main\n"), (0, []))


class DefaultShape(unittest.TestCase):
    def test_good_fixture_is_clean(self):
        self.assertEqual(run(fixture("good.md"), fixture("good.files").splitlines()), (0, []))

    def test_dense_fixture_is_flagged(self):
        body = fixture("dense.md")
        self.assertNotIn("auto-generated comment", body)
        code, out = run(body, fixture("good.files").splitlines())
        self.assertEqual(code, 1)
        joined = "\n".join(out)
        for message in (
            "Why opens with the change",
            "warning: Why runs 119 words",
            "warning: 20 bullets",
            "warning: bullet over 25 words",
            "warning: more than one semicolon",
            'assertion without evidence "All tests pass"',
            'self-grading word "robust"',
            "`CHANGELOG.md` is not in the diff",
            "run-in label **Testing.**",
            "### Review has nothing under it",
        ):
            self.assertIn(message, joined)

    def test_minimal_body_is_why_alone(self):
        self.assertEqual(run(shaped()), (0, []))
        self.assertEqual(run(shaped(ticket="Closes #1.")), (0, []))

    def test_ticket_forms_may_precede_why(self):
        for ticket in ("#12", "fixes PROJ-9", "Relates to [PROJ-9](https://x.atlassian.net/browse/PROJ-9)."):
            self.assertEqual(run(shaped(ticket=ticket)), (0, []))

    def test_why_must_come_first(self):
        code, out = run("Some preamble.\n\n" + shaped())
        self.assertEqual(code, 1)
        self.assertIn("### Why must come first", out[0])
        code, out = run("### Approach\n\nFirst.\n\n### Why\n\nSecond.\n")
        self.assertEqual(code, 1)
        self.assertIn("### Why must come first", "\n".join(out))

    def test_why_required_when_shaped(self):
        code, out = run("### Approach\n\nAlone.\n")
        self.assertEqual(code, 1)
        self.assertIn("no ### Why section", out[0])

    def test_why_openers(self):
        for opener in ("This PR adds", "This change moves", "Adds a", "Introduces the", "Updates the"):
            code, out = run(shaped(why=f"{opener} thing."))
            self.assertEqual(code, 1, opener)
            self.assertIn(":3: Why opens with the change", out[0])
        self.assertEqual(run(shaped(why="The thing was missing, so adds failed.")), (0, []))

    def test_run_in_labels_are_errors(self):
        code, out = run("**Why.** Nothing closed the last tab.\n")
        self.assertEqual(code, 1)
        self.assertIn("run-in label **Why.**: use a ### heading", out[0])

    def test_label_limits(self):
        self.assertEqual(run(shaped(why=words(80), approach=words(100))), (0, []))
        self.assertEqual(run(shaped(why=words(80), review=words(60))), (0, []))
        code, out = run(shaped(why=words(81)))
        self.assertEqual(code, 0)
        self.assertIn(":1: warning: Why runs 81 words", out[0])
        code, out = run(shaped(approach=words(101)))
        self.assertEqual(code, 0)
        self.assertIn(":5: warning: Approach runs 101 prose words", out[0])
        code, out = run(shaped(review=words(61)))
        self.assertEqual(code, 0)
        self.assertIn(":5: warning: Review runs 61 words", out[0])

    def test_approach_bullets_not_counted_as_prose(self):
        self.assertEqual(run(shaped(approach=words(100)) + bullets(2)), (0, []))

    def test_warnings_pass_errors_fail(self):
        code, out = run(shaped(why=words(81), approach="A robust fix."))
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 2)
        self.assertEqual(sum(":1: warning:" in line for line in out), 1)

    def test_ticket_line_not_counted(self):
        self.assertEqual(run(shaped(why=words(80), approach=words(100), ticket="Closes #1.")), (0, []))

    def test_empty_section(self):
        code, out = run(shaped() + "\n### Review\n")
        self.assertEqual(code, 1)
        self.assertIn("### Review has nothing under it", out[0])
        self.assertEqual(run(shaped(approach="| a | b |\n| - | - |\n| 1 | 2 |")), (0, []))
        self.assertEqual(run(shaped(approach="```text\ntree\n```")), (0, []))

    def test_duplicate_section(self):
        code, out = run(shaped() + "\n### Why\n\nAgain.\n")
        self.assertEqual(code, 1)
        self.assertIn("### Why appears twice", out[0])

    def test_review_closes_the_body(self):
        body = shaped(review="Start in `a.ts`.") + "\n### Before\n\nold\n"
        code, out = run(body)
        self.assertEqual(code, 1)
        self.assertIn("text after ### Review", out[0])
        body = shaped(review="Start in `a.ts`.\nThen `b.ts`.")
        self.assertEqual(run(body), (0, []))

    def test_evidence_between_approach_and_review_passes(self):
        body = shaped(approach="The cap is gone.") + "\n### Before\n\nold\n\n### After\n\nnew\n\n### Review\n\nLook at `a.ts`.\n"
        self.assertEqual(run(body), (0, []))

    def test_template_bodies_skip_shape_checks(self):
        body = "## Summary\n\nThis PR adds a thing.\n\n## Testing\n\n- ran it\n"
        self.assertEqual(run(body), (0, []))


class DiffConsistency(unittest.TestCase):
    def test_named_path_must_be_in_diff(self):
        files = ["src/editor/image-resize.ts", "README.md"]
        self.assertEqual(run("- `image-resize.ts`: resize\n- `README.md`: note\n", files), (0, []))
        self.assertEqual(run("- `src/editor/image-resize.ts`: resize\n", files), (0, []))
        code, out = run("- `image-dialog.tsx`: opens it\n", files)
        self.assertEqual(code, 1)
        self.assertIn("`image-dialog.tsx` is not in the diff", out[0])

    def test_non_paths_ignored(self):
        files = ["a.ts"]
        body = "- `req.body`, `@vue/eslint-config-typescript`, `3.5.17`, `<img src>`, `pnpm test`, `D97`, `width`\n"
        self.assertEqual(run(body, files), (0, []))

    def test_without_files_paths_unchecked(self):
        self.assertEqual(run("- `nowhere.ts`: fine\n"), (0, []))

    def test_test_claim_needs_test_file(self):
        body = shaped(approach="Added a test for the empty case.")
        self.assertEqual(run(body, ["src/a.ts", "src/a.test.ts"]), (0, []))
        self.assertEqual(run(body, ["src/a.ts", "tests/test_a.py"]), (0, []))
        self.assertEqual(run(body, ["src/a.ts", "src/__tests__/a.ts"]), (0, []))
        code, out = run(body, ["src/a.ts"])
        self.assertEqual(code, 1)
        self.assertIn("claims a test change, but no test file", out[0])

    def test_existing_test_mention_passes(self):
        body = shaped(approach="The listener test covers the press.")
        self.assertEqual(run(body, ["src/a.ts"]), (0, []))


class Usage(unittest.TestCase):
    def test_bad_usage(self):
        for args in ([], ["/no/such/file.md"], [write("x\n", ".md"), "--files"], [write("x\n", ".md"), "--nope", "y"]):
            p = subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True, check=False)
            self.assertEqual(p.returncode, 2, args)

    def test_missing_files_list(self):
        p = subprocess.run(
            [sys.executable, "-I", SCRIPT, write("x\n", ".md"), "--files", "/no/such/list.txt"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
