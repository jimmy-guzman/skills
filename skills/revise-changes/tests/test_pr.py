"""Tests for scripts/pr.py.

Unit tests cover target parsing. End-to-end tests run the script against a
fake gh/glab on PATH, so nothing reaches GitHub or GitLab.

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

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
body = sys.stdin.read() if "--input" in a else None
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({"argv": a, "body": body}) + "\n")
state = os.environ.get("FAKE_STATE", "OPEN")
if a == ["api", "user"]:
    print(json.dumps({"login": "me"}))
elif "graphql" in a and any(x.startswith("query=") and "reviewThreads(first: 50" in x for x in a):
    print(json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [
            {"id": "PRRT_1", "isResolved": False, "isOutdated": False, "isCollapsed": False,
             "path": "src/tabs.ts", "line": 83, "originalLine": 83,
             "comments": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [
                 {"databaseId": 501, "body": "swallowed error here", "author": {"login": "coderabbit"},
                  "createdAt": "2026-01-01T00:00:00Z"},
                 {"databaseId": 503, "body": "Rethrown now, see the test.", "author": {"login": "me"},
                  "createdAt": "2026-01-02T00:00:00Z"}]}},
            {"id": "PRRT_2", "isResolved": True, "isOutdated": False, "isCollapsed": False,
             "path": "src/other.ts", "line": 10, "originalLine": 10,
             "comments": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [
                 {"databaseId": 502, "body": "already resolved", "author": {"login": "sam"},
                  "createdAt": "2026-01-01T00:00:00Z"}]}},
        ]}}}}}))
elif "graphql" in a and any(x.startswith("query=") and "resolveReviewThread" in x for x in a):
    print(json.dumps({"data": {"resolveReviewThread": {"thread": {"isResolved": True}}}}))
elif "graphql" in a:
    print(json.dumps({"data": {"repository": {"pullRequest": {
        "state": state, "isDraft": False, "headRefOid": "1a2b3c4d5e6f", "baseRefName": "main",
        "title": "Tabs", "body": "Closes #41", "author": {"login": "sam"}}}}}))
elif any(x.endswith("/replies") for x in a):
    print(json.dumps({"id": 991}))
else:
    print(json.dumps({"id": 991}))
'''

FAKE_GLAB = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
body = sys.stdin.read() if "--input" in a else None
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({"argv": a, "body": body}) + "\n")
if a == ["api", "user"]:
    print(json.dumps({"username": "me"}))
    sys.exit(0)
endpoint = next(x for x in a if x.startswith("projects/"))
if endpoint.endswith("/discussions") and "--paginate" in a:
    print(json.dumps({"id": "disc1", "notes": [
        {"body": "swallowed error here", "author": {"username": "sam"},
         "created_at": "2026-01-01T00:00:00Z", "resolvable": True, "resolved": False,
         "position": {"new_path": "src/tabs.ts", "new_line": 83, "head_sha": "1a2b3c4d5e6f"}}]}))
    print(json.dumps({"id": "disc3", "notes": [
        {"body": "left on an older head", "author": {"username": "sam"},
         "created_at": "2026-01-01T00:00:00Z", "resolvable": True, "resolved": False,
         "position": {"new_path": "src/old.ts", "new_line": 5, "head_sha": "0000000000"}}]}))
    print(json.dumps({"id": "disc2", "notes": [
        {"body": "general note, not a diff thread", "author": {"username": "sam"},
         "created_at": "2026-01-01T00:00:00Z", "resolvable": False, "resolved": False,
         "position": None}]}))
elif endpoint.endswith("merge_requests/482"):
    print(json.dumps({"state": "opened", "sha": "1a2b3c4d5e6f", "target_branch": "main",
                      "title": "Tabs", "description": "Closes #41", "author": {"username": "sam"}}))
else:
    print(json.dumps({"id": "note1"}))
'''


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
                    "FAKE_LOG": self.log}
        self.body = os.path.join(self.tmp.name, "body.md")
        self.write_body("Guarded the index now, see the test.")

    def tearDown(self):
        self.tmp.cleanup()

    def write_body(self, text):
        with open(self.body, "w") as fh:
            fh.write(text)

    def run_pr(self, *args, **env):
        p = subprocess.run([sys.executable, "-I", SCRIPT, *args, "--provider", "github"],
                           env={**self.env, **env}, capture_output=True, text=True,
                           cwd=self.tmp.name, check=False)
        return p.returncode, json.loads(p.stdout) if p.stdout.strip() else None, p.stderr

    def posted(self):
        with open(self.log) as fh:
            return [json.loads(l) for l in fh if '"POST"' in l]

    def log_lines(self):
        with open(self.log) as fh:
            return [json.loads(l) for l in fh]

    def test_state(self):
        code, out, _ = self.run_pr("state", "285")
        self.assertEqual(code, 0)
        self.assertEqual((out["state"], out["head_sha"], out["base_ref"], out["body"]),
                         ("open", "1a2b3c4d5e6f", "main", "Closes #41"))

    def test_threads_excludes_resolved_by_default(self):
        code, out, _ = self.run_pr("threads", "285")
        self.assertEqual(code, 0)
        self.assertEqual(len(out["threads"]), 1)
        t = out["threads"][0]
        self.assertEqual(t["id"], "PRRT_1")
        self.assertEqual(t["notes"][0]["author"], "coderabbit")
        self.assertNotIn("first_comment_id", t)

    def test_threads_include_resolved(self):
        _, out, _ = self.run_pr("threads", "285", "--include-resolved")
        self.assertEqual(len(out["threads"]), 2)

    def test_reply_posts_to_first_comment(self):
        code, out, _ = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body)
        self.assertEqual((code, out["replied"], out["resolved"]), (0, True, False))
        self.assertIn("501/replies", " ".join(self.posted()[0]["argv"]))

    def test_reply_with_resolve_calls_mutation(self):
        code, out, _ = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body,
                                   "--resolve")
        self.assertEqual((code, out["replied"], out["resolved"]), (0, True, True))
        mutations = [p for p in self.log_lines() if "resolveReviewThread" in str(p)]
        self.assertTrue(mutations)

    def test_reply_dry_run_posts_nothing(self):
        code, out, _ = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body,
                                   "--dry-run")
        self.assertEqual((code, out["replied"]), (0, "dry-run"))
        self.assertEqual(self.posted(), [])

    def test_reply_skips_when_already_posted(self):
        # PRRT_1 already has a note by the current user ("me") with this body
        # (see FAKE_GH). A retry (e.g. after a failed --resolve) must not
        # double-post.
        self.write_body("Rethrown now, see the test.")
        code, out, _ = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body)
        self.assertEqual((code, out["replied"]), (0, "skipped"))
        self.assertEqual(self.posted(), [])

    def test_reply_matching_someone_elses_note_still_posts(self):
        # Dedupe is against the current user's own notes only. A body that
        # happens to match the reviewer's comment is still a new reply.
        self.write_body("swallowed error here")
        code, out, _ = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body)
        self.assertEqual((code, out["replied"]), (0, True))
        self.assertEqual(len(self.posted()), 1)

    def test_reply_resolve_retry_after_dedupe_still_resolves(self):
        # A retry that skips the duplicate reply should still attempt the
        # resolve the user asked for with --resolve.
        self.write_body("Rethrown now, see the test.")
        code, out, _ = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body,
                                   "--resolve")
        self.assertEqual((code, out["replied"], out["resolved"]), (0, "skipped", True))
        mutations = [p for p in self.log_lines() if "resolveReviewThread" in str(p)]
        self.assertTrue(mutations)

    def test_reply_unknown_thread_fails(self):
        code, _, err = self.run_pr("reply", "285", "--thread", "PRRT_404", "--body-file", self.body)
        self.assertEqual(code, 5)
        self.assertIn("no thread", err)

    def test_reply_refuses_merged_without_allow_closed(self):
        code, _, err = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body,
                                   FAKE_STATE="MERGED")
        self.assertEqual(code, 4)
        self.assertIn("--allow-closed", err)

    def test_resolve_standalone(self):
        code, out, _ = self.run_pr("resolve", "285", "--thread", "PRRT_1")
        self.assertEqual((code, out["resolved"]), (0, True))


class EndToEndGitLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        bindir = os.path.join(self.tmp.name, "bin")
        os.makedirs(bindir)
        glab = os.path.join(bindir, "glab")
        with open(glab, "w") as fh:
            fh.write(FAKE_GLAB)
        os.chmod(glab, os.stat(glab).st_mode | stat.S_IEXEC)
        self.log = os.path.join(self.tmp.name, "log")
        self.env = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"],
                    "FAKE_LOG": self.log}
        self.body = os.path.join(self.tmp.name, "body.md")
        with open(self.body, "w") as fh:
            fh.write("Rethrown now, see the test.")

    def tearDown(self):
        self.tmp.cleanup()

    def run_pr(self, *args):
        p = subprocess.run([sys.executable, "-I", SCRIPT, *args, "--provider", "gitlab"],
                           env=self.env, capture_output=True, text=True,
                           cwd=self.tmp.name, check=False)
        return p.returncode, json.loads(p.stdout) if p.stdout.strip() else None, p.stderr

    def test_threads_carries_resolvable(self):
        code, out, _ = self.run_pr("threads", "!482", "--include-resolved")
        self.assertEqual(code, 0)
        self.assertEqual({t["id"]: t["resolvable"] for t in out["threads"]},
                         {"disc1": True, "disc3": True, "disc2": False})

    def test_threads_marks_outdated_when_position_head_moved(self):
        # disc1's position was taken at the MR's current sha; disc3's at an
        # older one; disc2 has no diff position at all.
        _, out, _ = self.run_pr("threads", "!482")
        self.assertEqual({t["id"]: t["outdated"] for t in out["threads"]},
                         {"disc1": False, "disc3": True, "disc2": False})

    def test_resolve_on_non_resolvable_thread_fails(self):
        code, _, err = self.run_pr("resolve", "!482", "--thread", "disc2")
        self.assertEqual(code, 6)
        self.assertIn("not resolvable", err)

    def test_reply_on_non_resolvable_thread_still_succeeds(self):
        # A plain (non-resolvable) GitLab discussion still takes a reply note;
        # resolvable only gates resolve.
        code, out, _ = self.run_pr("reply", "!482", "--thread", "disc2", "--body-file", self.body)
        self.assertEqual((code, out["replied"]), (0, True))

    def test_reply_on_resolvable_thread_succeeds(self):
        code, out, _ = self.run_pr("reply", "!482", "--thread", "disc1", "--body-file", self.body)
        self.assertEqual((code, out["replied"]), (0, True))

    def test_resolve_on_resolvable_thread_succeeds(self):
        code, out, _ = self.run_pr("resolve", "!482", "--thread", "disc1")
        self.assertEqual((code, out["resolved"]), (0, True))


if __name__ == "__main__":
    unittest.main()
