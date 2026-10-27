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
import time
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
elif "graphql" in a and os.environ.get("FAKE_NO_GRAPHQL"):
    sys.stderr.write("HTTP 403: GitHub GraphQL is not available\n")
    sys.exit(1)
elif "graphql" in a and any(x.startswith("query=") and "addPullRequestReviewThreadReply" in x for x in a):
    print(json.dumps({"data": {"addPullRequestReviewThreadReply": {"comment": {"databaseId": 992}}}}))
elif "graphql" in a and any(x.startswith("query=") and "resolveReviewThread" in x for x in a):
    print(json.dumps({"data": {"resolveReviewThread": {"thread": {"isResolved": True}}}}))
elif "graphql" in a:
    print(json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [
            {"id": "PRRT_1", "isResolved": False,
             "comments": {"nodes": [{"databaseId": 501}]}},
            {"id": "PRRT_2", "isResolved": True,
             "comments": {"nodes": [{"databaseId": 502}]}},
            {"id": "PRRT_gone", "isResolved": True,
             "comments": {"nodes": [{"databaseId": 507}]}},
        ]}}}}}))
elif any(x.endswith("/pulls/285/comments") for x in a):
    print(json.dumps([[
        {"id": 501, "path": "src/tabs.ts", "line": 83, "body": "swallowed error here",
         "user": {"login": "coderabbit"}, "created_at": "2026-01-01T00:00:00Z"},
        {"id": 502, "path": "src/other.ts", "line": 10, "body": "already resolved",
         "user": {"login": "sam"}, "created_at": "2026-01-01T00:00:00Z"},
        {"id": 503, "in_reply_to_id": 501, "path": "src/tabs.ts", "line": 83,
         "body": "Rethrown now, see the test.", "user": {"login": "me"},
         "created_at": "2026-01-02T00:00:00Z"},
    ] + ([
        {"id": 504, "in_reply_to_id": 499, "path": "src/gone.ts", "line": 4,
         "body": "reply to a deleted comment", "user": {"login": "sam"},
         "created_at": "2026-01-03T00:00:00Z"},
        {"id": 507, "in_reply_to_id": 499, "path": "src/gone.ts", "line": 4,
         "body": "second reply", "user": {"login": "me"},
         "created_at": "2026-01-04T00:00:00Z"},
        {"id": 505, "subject_type": "file", "path": "src/file.ts", "line": None,
         "body": "file-level note", "user": {"login": "sam"}, "created_at": "2026-01-03T00:00:00Z"},
        {"id": 506, "subject_type": "line", "path": "src/moved.ts", "line": None, "original_line": 9,
         "body": "the diff moved past me", "user": {"login": "sam"},
         "created_at": "2026-01-03T00:00:00Z"},
    ] if os.environ.get("FAKE_EXTRA") else [])]))
elif any(x.endswith("/pulls/285") for x in a):
    print(json.dumps({"state": "open" if state == "OPEN" else "closed",
                      "merged_at": "2026-01-01T00:00:00Z" if state == "MERGED" else None,
                      "draft": False, "head": {"sha": "1a2b3c4d5e6f"}, "base": {"ref": "main"},
                      "title": "Tabs", "body": "Closes #41", "user": {"login": "sam"}}))
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
        self.env = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"], "REVIEW_PR_WRITE_PAUSE": "0",
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
        self.assertEqual((t["id"], t["node_id"]), ("501", "PRRT_1"))
        self.assertEqual([n["author"] for n in t["notes"]], ["coderabbit", "me"])
        self.assertNotIn("first_comment_id", t)

    def test_threads_include_resolved(self):
        _, out, _ = self.run_pr("threads", "285", "--include-resolved")
        self.assertEqual(len(out["threads"]), 2)

    def test_reply_posts_to_first_comment(self):
        code, out, _ = self.run_pr("reply", "285", "--thread", "PRRT_1", "--body-file", self.body)
        self.assertEqual((code, out["replied"], out["resolved"]), (0, True, False))
        self.assertIn("repos/{owner}/{repo}/pulls/285/comments/501/replies", self.posted()[0]["argv"])

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

    def test_threads_without_graphql(self):
        # Some sessions answer every GraphQL call with 403. threads must still list
        # every thread, with resolution unknown rather than guessed.
        code, out, err = self.run_pr("threads", "285", FAKE_NO_GRAPHQL="1")
        self.assertEqual(code, 0, err)
        self.assertEqual([(t["id"], t["resolved"], t["node_id"]) for t in out["threads"]],
                         [("501", None, None), ("502", None, None)])

    def test_reply_without_graphql_by_comment_id(self):
        code, out, err = self.run_pr("reply", "285", "--thread", "501", "--body-file", self.body,
                                     FAKE_NO_GRAPHQL="1")
        self.assertEqual((code, out["replied"]), (0, True), err)

    def test_resolve_without_graphql_fails_clearly(self):
        code, _, err = self.run_pr("resolve", "285", "--thread", "501", FAKE_NO_GRAPHQL="1")
        self.assertEqual(code, 5)
        self.assertIn("GraphQL", err)

    def test_batch_resolve_without_graphql_replies_nothing(self):
        code, _, err = self.run_batch([("501", "Fixed.", True), ("502", "Also.", False)],
                                      FAKE_NO_GRAPHQL="1")
        self.assertEqual(code, 5)
        self.assertIn("nothing replied", err)
        self.assertEqual(self.posted(), [])

    def test_threads_rest_edge_cases(self):
        # Replies to a deleted first comment stay one thread under the oldest reply,
        # and match GraphQL's thread whichever reply it names; a file-level comment
        # has no line but isn't outdated; a line comment that lost its line is.
        code, out, err = self.run_pr("threads", "285", "--include-resolved", FAKE_EXTRA="1")
        self.assertEqual(code, 0, err)
        by_id = {t["id"]: t for t in out["threads"]}
        self.assertNotIn("507", by_id)
        self.assertEqual([n["body"] for n in by_id["504"]["notes"]],
                         ["reply to a deleted comment", "second reply"])
        self.assertEqual((by_id["504"]["node_id"], by_id["504"]["resolved"]), ("PRRT_gone", True))
        self.assertEqual({i: by_id[i]["outdated"] for i in ("501", "505", "506")},
                         {"501": False, "505": False, "506": True})
        self.assertEqual(by_id["506"]["line"], 9)

    def test_reply_on_deleted_root_goes_through_graphql(self):
        # GitHub's REST reply endpoint takes only a top-level comment, and 504 is a
        # reply whose first comment was deleted.
        code, out, err = self.run_pr("reply", "285", "--thread", "504", "--body-file", self.body,
                                     FAKE_EXTRA="1")
        self.assertEqual((code, out["replied"], out["id"]), (0, True, 992), err)
        log = self.log_lines()
        self.assertFalse(any(x.endswith("/replies") for l in log for x in l["argv"]))
        sent = next(l["argv"] for l in log if "addPullRequestReviewThreadReply" in str(l["argv"]))
        self.assertIn("id=PRRT_gone", sent)
        self.assertIn("body=Guarded the index now, see the test.", sent)

    def test_reply_on_deleted_root_without_graphql_replies_nothing(self):
        code, _, err = self.run_batch([("501", "ok", False), ("504", "x", False)],
                                      FAKE_EXTRA="1", FAKE_NO_GRAPHQL="1")
        self.assertEqual(code, 5)
        self.assertIn("reply to thread 504", err)
        self.assertEqual(self.posted(), [])

    def test_merged_state(self):
        _, out, _ = self.run_pr("state", "285", FAKE_STATE="MERGED")
        self.assertEqual(out["state"], "merged")

    def test_resolve_standalone(self):
        code, out, _ = self.run_pr("resolve", "285", "--thread", "PRRT_1")
        self.assertEqual((code, out["resolved"]), (0, True))


    def run_batch(self, entries, *args, **env):
        path = os.path.join(self.tmp.name, "batch.json")
        rows = []
        for i, (thread, text, resolve) in enumerate(entries):
            f = os.path.join(self.tmp.name, f"r{i}.md")
            with open(f, "w") as fh:
                fh.write(text)
            rows.append({"thread": thread, "body_file": f, "resolve": resolve})
        with open(path, "w") as fh:
            json.dump(rows, fh)
        p = subprocess.run([sys.executable, "-I", SCRIPT, "reply", "285", "--batch", path, *args,
                            "--provider", "github"],
                           env={**self.env, **env}, capture_output=True, text=True,
                           cwd=self.tmp.name, check=False)
        return p.returncode, [json.loads(l) for l in p.stdout.splitlines() if l.strip()], p.stderr

    def test_batch_replies_in_order_and_dedupes(self):
        code, out, err = self.run_batch([
            ("PRRT_1", "Rethrown now, see the test.", False),
            ("PRRT_1", "Second note.", True),
            ("PRRT_1", "Second note.", False),
        ])
        self.assertEqual(code, 0, err)
        self.assertEqual([(o["index"], o["thread"], o["replied"]) for o in out],
                         [(0, "PRRT_1", "skipped"), (1, "PRRT_1", True), (2, "PRRT_1", "skipped")])
        self.assertEqual([o["resolved"] for o in out], [False, True, False])
        self.assertEqual(len(self.posted()), 1)

    def test_batch_unknown_thread_replies_nothing(self):
        code, _, err = self.run_batch([("PRRT_1", "ok", False), ("PRRT_404", "x", False)])
        self.assertEqual(code, 5)
        self.assertIn("PRRT_404", err)
        self.assertEqual(self.posted(), [])

    def test_batch_with_single_flags_is_refused(self):
        code, _, err = self.run_batch([("PRRT_1", "ok", False)], "--thread", "PRRT_1")
        self.assertEqual(code, 2)
        self.assertIn("--batch replaces", err)

    def test_batch_pauses_between_writes_only(self):
        self.env["REVIEW_PR_WRITE_PAUSE"] = "0.3"
        start = time.monotonic()
        code, out, err = self.run_batch([
            ("PRRT_1", "First.", False),
            ("PRRT_1", "Second.", False),
        ])
        self.assertEqual(code, 0, err)
        self.assertEqual([o["replied"] for o in out], [True, True])
        self.assertGreaterEqual(time.monotonic() - start, 0.3)

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
        self.env = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"], "REVIEW_PR_WRITE_PAUSE": "0",
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
