import pathlib
import subprocess
import sys
import tempfile
import unittest

PACK = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "pack.py"
GIT_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


def make_repo(root):
    r = pathlib.Path(root)

    def git(*a):
        return subprocess.run(["git", *GIT_ID, *a], cwd=root, capture_output=True, check=True).stdout

    git("init", "-q")
    git("commit", "-q", "--allow-empty", "-m", "root")
    (r / "pkg" / "src").mkdir(parents=True)
    (r / "pkg" / "src" / "tabs.py").write_text("def close_tab(i):\n    return i\n")
    (r / "app.py").write_text("from tabs import close_tab\nclose_tab(1)\n")
    (r / "tests").mkdir()
    (r / "tests" / "test_tabs.py").write_text("import tabs\n")
    (r / "pkg" / "src" / "my notes.py").write_bytes(b"caf\xe9 = 1\n")
    (r / "b").mkdir()
    (r / "b" / "foo.py").write_text("x = 1\n")
    (r / "foo.py").write_text("root = 0\n")
    (r / 'q"\u65e5.py').write_text("z = 3\n")
    (r / "caf\u00e9.py").write_text("y = 2\n")
    (r / "pages").mkdir()
    (r / "pages" / "[id].tsx").write_text("export default 1\n")
    (r / "tests" / "test_other.py").write_text("nothing here\n")
    git("add", "-A")
    git("commit", "-q", "-m", "add")
    return git


def run_pack(cwd, diff, *args):
    """diff is bytes, as a real pipe delivers it."""
    r = subprocess.run([sys.executable, str(PACK), *args], cwd=cwd, input=diff, capture_output=True)
    r.stderr = r.stderr.decode(errors="replace")
    return r


class PackTest(unittest.TestCase):
    def test_rev_pack_handles_subdir_noprefix_space_latin1_quoting_and_regex_stems(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git = make_repo(repo)
            rev = git("rev-parse", "HEAD").decode().strip()
            diff = git("-c", "diff.noprefix=true", "diff", "HEAD~1", "HEAD")
            res = run_pack(str(pathlib.Path(repo) / "pkg"), diff, "--out", out, "--rev", rev)
            self.assertEqual(res.returncode, 0, res.stderr)
            o = pathlib.Path(out)
            self.assertEqual((o / "diff.patch").read_text(), diff.decode("utf-8", "replace"))
            self.assertIn("def close_tab", (o / "files" / "pkg" / "src" / "tabs.py").read_text())
            self.assertTrue((o / "files" / "pkg" / "src" / "my notes.py").exists())
            self.assertFalse(list((o / "files").rglob("*\t")))
            callers = (o / "callers.txt").read_text()
            self.assertIn("## close_tab", callers)
            self.assertIn("\napp.py:2:", callers)
            self.assertNotIn(rev, callers)
            self.assertIn("x = 1", (o / "files" / "b" / "foo.py").read_text())
            self.assertIn("root = 0", (o / "files" / "foo.py").read_text())
            self.assertIn("y = 2", (o / "files" / "caf\u00e9.py").read_text())
            tests_txt = (o / "tests.txt").read_text()
            self.assertIn("tests/test_tabs.py", tests_txt)
            self.assertNotIn("tests/test_other.py", tests_txt)

    def test_missing_file_at_rev_is_skipped(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git = make_repo(repo)
            rev = git("rev-parse", "HEAD").decode().strip()
            diff = b"--- a/ghost.txt\n+++ b/ghost.txt\n@@ -0,0 +1 @@\n+x\n"
            res = run_pack(repo, diff, "--out", out, "--rev", rev)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse((pathlib.Path(out) / "files" / "ghost.txt").exists())

    def test_read_only_pack_sees_untracked_files(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git = make_repo(repo)
            r = pathlib.Path(repo)
            (r / "pkg" / "src" / "tabs.py").write_text("def close_tab(i, force=False):\n    return i\n")
            (r / "tests" / "test_close.py").write_text("from tabs import close_tab\n")
            diff = git("diff", "HEAD")
            res = run_pack(repo, diff, "--out", out, "--extra", "tests/test_close.py")
            self.assertEqual(res.returncode, 0, res.stderr)
            o = pathlib.Path(out)
            self.assertIn("close_tab", (o / "files" / "tests" / "test_close.py").read_text())
            self.assertIn("force=False", (o / "files" / "pkg" / "src" / "tabs.py").read_text())
            self.assertIn("tests/test_close.py:1:", (o / "callers.txt").read_text())
            self.assertIn("tests/test_close.py", (o / "tests.txt").read_text())
            self.assertFalse((o / "untracked.txt").exists())

    def test_quotepath_false_header_with_quote_and_cjk(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git = make_repo(repo)
            rev = git("rev-parse", "HEAD").decode().strip()
            diff = git("-c", "core.quotePath=false", "diff", "HEAD~1", "HEAD", "--", 'q"\u65e5.py')
            res = run_pack(repo, diff, "--out", out, "--rev", rev)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("z = 3", (pathlib.Path(out) / "files" / 'q"\u65e5.py').read_text())

    def test_content_line_starting_with_plus_plus_is_not_a_header(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git = make_repo(repo)
            r = pathlib.Path(repo)
            (r / "app.py").write_text("from tabs import close_tab\nclose_tab(1)\n++ appended\n")
            (r / "pkg" / "src" / "tabs.py").write_text("def close_tab(i, force=False):\n    return i\n")
            git("add", "-A")
            git("commit", "-q", "-m", "stray")
            rev = git("rev-parse", "HEAD").decode().strip()
            res = run_pack(repo, git("diff", "HEAD~1", "HEAD"), "--out", out, "--rev", rev)
            self.assertEqual(res.returncode, 0, res.stderr)
            o = pathlib.Path(out)
            self.assertIn("appended", (o / "files" / "app.py").read_text())
            self.assertIn("force=False", (o / "files" / "pkg" / "src" / "tabs.py").read_text())
            self.assertFalse((o / "files" / "appended").exists())

    def test_one_line_matching_several_patterns_is_listed_under_each(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git = make_repo(repo)
            (pathlib.Path(repo) / "both.py").write_text("open_tab(close_tab(1))  # shared line\n")
            (pathlib.Path(repo) / "pkg" / "src" / "tabs.py").write_text(
                "def close_tab(n):\n    return n\n\ndef open_tab(i):\n    return i\n")
            git("add", "-A")
            git("commit", "-q", "-m", "more")
            rev = git("rev-parse", "HEAD").decode().strip()
            diff = git("diff", "HEAD~1", "HEAD")
            res = run_pack(repo, diff, "--out", out, "--rev", rev)
            self.assertEqual(res.returncode, 0, res.stderr)
            callers = (pathlib.Path(out) / "callers.txt").read_text()
            for sym in ("close_tab", "open_tab"):
                chunk = callers.split(f"## {sym}\n", 1)[1].split("## ", 1)[0]
                self.assertIn("both.py:1:open_tab(close_tab(1))", chunk)
            self.assertNotIn(rev, callers)

    def test_indented_locals_are_not_symbols(self):
        sys.path.insert(0, str(PACK.parent))
        from pack import symbols
        diff = ("@@ -1 +1 @@\n+    const data = 1\n+  let result = 2\n+export const config = 3\n"
                "+const LIMIT = 4\n+  export const nested = 5\n+    def method(self):\n+function load() {}\n")
        self.assertEqual(symbols(diff), ["config", "LIMIT", "nested", "method", "load"])

    def test_diff_from_file_matches_stdin(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git = make_repo(repo)
            rev = git("rev-parse", "HEAD").decode().strip()
            patch = pathlib.Path(out) / "in.patch"
            patch.write_bytes(git("diff", "HEAD~1", "HEAD"))
            res = run_pack(repo, b"", "--diff", str(patch), "--out", str(pathlib.Path(out) / "pack"), "--rev", rev)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("def close_tab", (pathlib.Path(out) / "pack" / "files" / "pkg" / "src" / "tabs.py").read_text())

    def test_empty_diff_fails(self):
        res = run_pack(None, b"", "--out", tempfile.mkdtemp())
        self.assertEqual(res.returncode, 1)

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out, \
                tempfile.TemporaryDirectory() as outside:
            make_repo(repo)
            secret = pathlib.Path(outside) / "secret.txt"
            secret.write_text("top secret\n")
            diff = f"--- a/x\n+++ b/../../../..{secret}\n@@ -0,0 +1 @@\n+x\n".encode()
            res = run_pack(repo, diff, "--out", out, "--extra", str(secret), "--extra", f"../../../..{secret}")
            self.assertEqual(res.returncode, 0, res.stderr)
            o = pathlib.Path(out)
            # Nothing escaped out/files, and the outside file was neither read into the pack nor overwritten.
            self.assertEqual(sorted(p.name for p in (o / "files").rglob("*") if p.is_file()), [])
            self.assertFalse(secret.with_suffix(".txt.bak").exists())
            self.assertEqual(secret.read_text(), "top secret\n")


if __name__ == "__main__":
    unittest.main()
