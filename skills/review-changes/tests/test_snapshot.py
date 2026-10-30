import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SNAPSHOT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "snapshot.py"
GIT_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


def make_repo(root):
    def git(*a):
        return subprocess.run(["git", *GIT_ID, *a], cwd=root, capture_output=True, check=True).stdout.decode()

    git("init", "-q")
    (pathlib.Path(root) / "a.txt").write_text("one\n")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return git


ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def run(cwd, *args):
    r = subprocess.run([sys.executable, str(SNAPSHOT), *args], cwd=cwd, capture_output=True, text=True, env=ENV)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return r.stdout.strip()


class SnapshotTest(unittest.TestCase):
    def test_snapshot_holds_untracked_and_leaves_index_alone(self):
        with tempfile.TemporaryDirectory() as repo:
            git = make_repo(repo)
            r = pathlib.Path(repo)
            (r / "a.txt").write_text("two\n")
            (r / "new.txt").write_text("fresh\n")
            (r / "sub").mkdir()
            sha = run(str(r / "sub"))
            self.assertEqual(git("show", f"{sha}:new.txt"), "fresh\n")
            self.assertEqual(git("show", f"{sha}:a.txt"), "two\n")
            self.assertEqual(git("diff", "--cached", "--name-only"), "")
            self.assertIn("?? new.txt", git("status", "--porcelain"))

    def test_snapshot_skips_nested_worktrees_ignored_or_not(self):
        for ignored in (False, True):
            with self.subTest(ignored=ignored), tempfile.TemporaryDirectory() as repo:
                git = make_repo(repo)
                r = pathlib.Path(repo)
                if ignored:
                    (r / ".gitignore").write_text(".wt/\n")
                git("worktree", "add", "-q", "-b", "agent", str(r / ".wt" / "x"))
                (r / ".wt" / "x" / "f.txt").write_text("stray\n")
                (r / "plain" / "x").mkdir(parents=True)
                (r / "plain" / "x" / "f.txt").write_text("kept\n")
                paths = git("ls-tree", "-r", "--name-only", run(repo))
                self.assertNotIn(".wt/", paths)
                self.assertIn("plain/x/f.txt", paths)

    def test_guard_without_edits_reports_nothing(self):
        with tempfile.TemporaryDirectory() as repo:
            make_repo(repo)
            (pathlib.Path(repo) / "a.txt").write_text("dirty\n")
            before = run(repo)
            self.assertEqual(json.loads(run(repo, "--guard", before)), {"changed": False})

    def test_guard_reverts_edits_and_saves_them(self):
        with tempfile.TemporaryDirectory() as repo:
            make_repo(repo)
            r = pathlib.Path(repo)
            before = run(repo)
            (r / "a.txt").write_text("stray\n")
            (r / "added.txt").write_text("stray\n")
            out = json.loads(run(repo, "--guard", before))
            self.assertTrue(out["changed"])
            self.assertEqual(sorted(out["files"]), ["a.txt", "added.txt"])
            self.assertEqual((r / "a.txt").read_text(), "one\n")
            self.assertFalse((r / "added.txt").exists())
            self.assertIn("+stray", pathlib.Path(out["patch"]).read_text())

    def test_cleanup_removes_worktree_and_branch_and_reports_edits(self):
        with tempfile.TemporaryDirectory() as repo:
            git = make_repo(repo)
            wt = pathlib.Path(repo) / ".claude" / "worktrees" / "agent-x"
            git("worktree", "add", "-q", "-b", "worktree-agent-x", str(wt))
            (wt / "a.txt").write_text("stray\n")
            git("branch", "worktree-agent-y")
            out = json.loads(run(repo, "--cleanup", str(wt), "worktree-agent-y"))
            self.assertEqual(out[0]["dirty"], [" M a.txt"])
            self.assertEqual(out[0]["removed"], [f"worktree {wt}", "branch worktree-agent-x"])
            self.assertEqual(out[1]["removed"], ["branch worktree-agent-y"])
            self.assertFalse(wt.exists())
            self.assertEqual(git("branch", "--list", "worktree-agent-*"), "")

    def test_cleanup_runs_from_a_sibling_worktree_and_spares_its_own(self):
        with tempfile.TemporaryDirectory() as repo:
            git = make_repo(repo)
            r = pathlib.Path(repo)
            session = r / ".claude" / "worktrees" / "session"
            reviewer = r / ".claude" / "worktrees" / "agent-x"
            git("worktree", "add", "-q", "-b", "session", str(session))
            git("worktree", "add", "-q", "-b", "worktree-agent-x", str(reviewer))
            out = json.loads(run(str(session), "--cleanup", str(reviewer), str(session)))
            self.assertIsNone(out[0]["error"])
            self.assertFalse(reviewer.exists())
            self.assertIn("refusing", out[1]["error"])
            self.assertTrue(session.exists())


if __name__ == "__main__":
    unittest.main()
