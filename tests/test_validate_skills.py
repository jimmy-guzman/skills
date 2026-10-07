"""Tests for scripts/validate_skills.py.

Run from the repo root: `python -m unittest discover -s tests -t tests`.
Each test builds a tiny fixture skill under a temp directory, invokes the
script via `uv run` so PEP 723 inline deps install themselves, and asserts
on the stdout + exit code.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_skills.py"


def write_skill(root, name, frontmatter, body=""):
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\n{frontmatter.strip()}\n---\n{body}",
        encoding="utf-8",
    )


def run_validator(root):
    return subprocess.run(
        ["uv", "run", str(VALIDATOR), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class GoodFixture(unittest.TestCase):
    def test_passes_with_zero_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "my-skill",
                "name: my-skill\ndescription: A tiny well-formed skill for tests.",
                "# my-skill\n\nSome body text.\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("0 error(s)", r.stdout)


class BadName(unittest.TestCase):
    def test_folder_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "my-skill",
                "name: other-name\ndescription: Folder and name differ.",
                "body\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("does not match folder", r.stdout)

    def test_contains_claude(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "claude-helper",
                "name: claude-helper\ndescription: Has forbidden substring.",
                "body\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("may not contain 'claude' or 'anthropic'", r.stdout)

    def test_double_hyphen(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "bad--name",
                "name: bad--name\ndescription: Doubled hyphen.",
                "body\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("lowercase letters, digits, and single hyphens", r.stdout)


class DescriptionTooLong(unittest.TestCase):
    def test_errors_over_1024(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            desc = "x" * 1025
            write_skill(
                root,
                "big-desc",
                "name: big-desc\ndescription: {}".format(desc),
                "body\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("description length 1025 > 1024", r.stdout)


class UnknownField(unittest.TestCase):
    def test_errors_on_extra_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "extra",
                "name: extra\ndescription: Has unknown field.\nfoo: bar",
                "body\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("unknown frontmatter field: foo", r.stdout)


class BrokenLink(unittest.TestCase):
    def test_relative_link_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "linky",
                "name: linky\ndescription: Links to a file that is not there.",
                "See [the ref](references/missing.md) for details.\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("link target does not exist", r.stdout)

    def test_fenced_link_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            body = (
                "An example:\n\n"
                "```\n"
                "[not real](references/missing.md)\n"
                "```\n"
            )
            write_skill(
                root,
                "fenced",
                "name: fenced\ndescription: Fenced link should not trigger.",
                body,
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)


class EmDash(unittest.TestCase):
    def test_em_dash_in_body_warns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(
                root,
                "dashy",
                "name: dashy\ndescription: Has em-dash in body.",
                "This is a sentence — and here is more.\n",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("warning: em-dash or en-dash", r.stdout)

    def test_em_dash_in_fenced_block_silent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            body = "```\ngrep -nF -- '—' file\n```\n"
            write_skill(
                root,
                "fenced-dash",
                "name: fenced-dash\ndescription: Em-dash inside a fence is allowed.",
                body,
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertNotIn("em-dash", r.stdout)


class BodyWarnings(unittest.TestCase):
    def test_long_body_warns_but_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            body = "a line of body text to make this skill long.\n" * 600
            write_skill(
                root,
                "long",
                "name: long\ndescription: Overly long body.",
                body,
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("warning", r.stdout)
            self.assertIn("lines", r.stdout)


class MissingSkillMd(unittest.TestCase):
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "skills" / "no-md").mkdir(parents=True)
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("SKILL.md is missing", r.stdout)


class MalformedFrontmatter(unittest.TestCase):
    def test_no_frontmatter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill_dir = root / "skills" / "no-fm"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# just a title\n", encoding="utf-8")
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("frontmatter missing or malformed", r.stdout)

    def test_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill_dir = root / "skills" / "bad-yaml"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: bad-yaml\ndescription: [unclosed\n---\n",
                encoding="utf-8",
            )
            r = run_validator(root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("frontmatter YAML error", r.stdout)


class Help(unittest.TestCase):
    def test_help_exits_zero(self):
        r = subprocess.run(
            ["uv", "run", str(VALIDATOR), "--help"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("--root", r.stdout)


class BadRoot(unittest.TestCase):
    def test_missing_skills_dir(self):
        with tempfile.TemporaryDirectory() as td:
            r = run_validator(Path(td))
            self.assertEqual(r.returncode, 2)
            self.assertIn("is not a directory", r.stderr)


if __name__ == "__main__":
    unittest.main()
