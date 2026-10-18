"""Tests for scripts/detect.py.

Run from the skill folder: python3 -m unittest discover -s tests
"""

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "detect.py"


class Repo:
    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.git("init", "-q", "-b", "main")

    def git(self, *args, author="Dev <d@d>"):
        name, email = author[:-1].split(" <")
        env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
               "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
        subprocess.run(["git", *args], cwd=self.root, env=env, capture_output=True, check=True)

    def commit(self, message, author="Dev <d@d>"):
        self.git("commit", "-q", "--allow-empty", "-m", message, author=author)

    def write(self, path, text="x\n"):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def detect(self):
        p = subprocess.run([sys.executable, "-I", SCRIPT], cwd=self.root, capture_output=True, text=True, check=True)
        return p.stdout


def field(out, name):
    return next(line for line in out.splitlines() if line.startswith(f"{name}:"))


class Detect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_protected_branch_and_empty_repo(self):
        self.repo.commit("init")
        out = self.repo.detect()
        self.assertEqual(field(out, "branch"), "branch: main (protected)")
        self.assertIn("changes: nothing to commit", out)

    def test_feature_branch_ticket_skips_lookalikes(self):
        self.repo.commit("init")
        self.repo.git("checkout", "-q", "-b", "feat/UTF-8-ABC-42-thing")
        out = self.repo.detect()
        self.assertEqual(field(out, "branch"), "branch: feat/UTF-8-ABC-42-thing")
        self.assertTrue(field(out, "ticket").startswith("ticket: ABC-42 (branch)"))

    def test_gitzy_config_and_devdep(self):
        self.repo.write(".gitzyrc.json", "{}")
        self.repo.write("package.json", '{"devDependencies": {"gitzy": "^6"}}')
        self.assertEqual(field(self.repo.detect(), "gitzy"), "gitzy: .gitzyrc.json, package.json deps")

    def test_no_gitzy(self):
        self.assertEqual(field(Repo(self.tmp.name).detect(), "gitzy"), "gitzy: none")

    def test_emoji_map_and_bots_dropped(self):
        self.repo.commit("feat(ui): ✨ add dark mode")
        self.repo.commit("fix: 🐛 guard empty input")
        self.repo.commit("chore(deps): bump x", author="renovate[bot] <r@r>")
        out = self.repo.detect()
        shape = field(out, "shape")
        self.assertIn("feat ✨", shape)
        self.assertIn("fix 🐛", shape)
        self.assertNotIn("bump x", out)

    def test_custom_commit_msg_hook(self):
        self.repo.write(".husky/commit-msg", "#!/bin/sh\n./scripts/check-msg \"$1\"\n")
        self.assertIn("commit-msg: custom (./scripts/check-msg", field(self.repo.detect(), "hooks"))

    def test_untracked_secret_flagged(self):
        self.repo.write(".env.local")
        self.repo.write("ok.txt")
        out = self.repo.detect()
        self.assertIn("untracked: 2", out)
        self.assertIn(".env.local  [secret?]", out)
        self.assertIn("  ok.txt\n", out)


if __name__ == "__main__":
    unittest.main()
