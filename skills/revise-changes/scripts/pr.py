#!/usr/bin/env python3
"""Read PR/MR threads and reply to or resolve them on GitHub or GitLab.

Wraps gh and glab so the skill gets the same JSON from both providers.
Run it with the repo as the working directory. Stdlib only.

Forked from review-changes/scripts/pr.py: keeps `state` for head/base/
closed-merged checks, drops `post` (revise-changes never starts a new
thread), adds `threads`, `reply`, and `resolve`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlparse

USAGE = """\
Usage:
  pr.py state   <pr> [--provider P] [--repo R] [--host H]
  pr.py threads <pr> [--include-resolved] [--provider P] [--repo R] [--host H]
  pr.py reply   <pr> --thread ID --body-file F [--resolve] [--allow-closed]
                [--dry-run] [--provider P] [--repo R] [--host H]
  pr.py reply   <pr> --batch FILE [--allow-closed] [--dry-run]
  pr.py resolve <pr> --thread ID [--provider P] [--repo R] [--host H]

<pr> is a number (285), a ref (#285, !482), or a PR/MR URL.

state prints one JSON object:
  provider, ref, state (open|closed|merged), draft, head_sha, base_ref, title,
  author, body (the PR description)

threads prints one JSON object:
  threads [{id, node_id, resolvable, resolved, outdated, path, line,
            notes: [{author, body, created_at}]}]
  Resolved threads are left out unless --include-resolved is passed.
  outdated is GitHub's own flag; on GitLab it's true when the thread's
  diff position was taken at a head other than the MR's current one.
  node_id is the GitHub review-thread node id (PRRT_...), needed by resolve;
  null on GitLab, where id itself is the discussion id resolve needs.

reply prints one JSON object:
  replied (true|false|dry-run), resolved (true|false), id

reply always replies on the thread's first comment. A body identical to a
note the current user already left on the thread is not posted again
(replied: "skipped"). Pass --resolve to also resolve the thread after a
successful reply; without it, the thread stays open. --resolve never
happens on its own.

--batch replies to many threads in one call, so no shell loop is needed.
FILE is a JSON list of {"thread": ID, "body_file": F, "resolve": bool}
objects ("resolve" defaults to false), replied in order. Every entry and
thread is checked before the first reply. Writes are sent one at a time,
a second apart, per GitHub's rate-limit guidance. Prints one JSON object per entry,
one per line, in the single-reply shape plus "index" and "thread".

resolve prints one JSON object:
  resolved (true), id

Exit codes:
  0 ok
  2 bad arguments
  4 PR is closed or merged and --allow-closed wasn't passed (reply only)
  5 gh/glab call failed (auth, network, not found, thread not found);
    stderr says which
  6 thread can't take this action: GitHub reply with no comment to reply to,
    or GitLab resolve on a thread that isn't resolvable (a plain discussion
    still takes a reply, just not a resolve)

Examples:
  pr.py threads 285
  pr.py threads !482 --include-resolved
  pr.py reply 285 --thread PRRT_abc123 --body-file /tmp/r.md
  pr.py reply !482 --thread 9988 --body-file /tmp/r.md --resolve
  pr.py reply 285 --batch /tmp/replies.json
  pr.py resolve 285 --thread PRRT_abc123
"""

# GitHub asks for at least a second between content-creating requests to stay under
# its secondary rate limit; GitLab gets the same pacing. REVIEW_PR_WRITE_PAUSE overrides
# it (tests set 0).
WRITE_PAUSE = float(os.environ.get("REVIEW_PR_WRITE_PAUSE", "1"))


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def run(cmd, stdin=None, env=None):
    try:
        p = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True,
            env={**os.environ, **(env or {})}, check=False,
        )
    except FileNotFoundError:
        raise Fail(5, f"{cmd[0]} is not installed")
    if p.returncode != 0:
        detail = (p.stderr or p.stdout).strip().splitlines()
        raise Fail(5, f"{' '.join(cmd[:3])} failed: {' '.join(detail[-3:])}")
    return p.stdout


# Target resolution -------------------------------------------------------


def parse_target(raw, provider, repo, host):
    raw = raw.strip()
    m = re.match(r"^[#!]?(\d+)$", raw)
    if m:
        number = int(m.group(1))
        if not provider:
            provider = "gitlab" if raw.startswith("!") else detect_provider()
        return provider, repo, host, number

    u = urlparse(raw)
    if not u.scheme or not u.netloc:
        raise Fail(2, f"can't read PR reference {raw!r}; pass a number, #n, !n, or a URL")
    path = u.path.strip("/")
    m = re.match(r"^(.+?)/-/merge_requests/(\d+)", path)
    if m:
        return provider or "gitlab", repo or m.group(1), host or u.netloc, int(m.group(2))
    m = re.match(r"^([^/]+/[^/]+)/pull/(\d+)", path)
    if m:
        return provider or "github", repo or m.group(1), host or u.netloc, int(m.group(2))
    raise Fail(2, f"{raw!r} is not a GitHub pull or GitLab merge request URL")


def detect_provider():
    try:
        remotes = run(["git", "remote", "-v"])
    except Fail:
        raise Fail(2, "not in a git repo; pass --provider or a PR URL")
    if "github" in remotes:
        return "github"
    if "gitlab" in remotes:
        return "gitlab"
    raise Fail(2, "can't tell GitHub from GitLab from the remotes; pass --provider")


# GitHub -----------------------------------------------------------------

GH_STATE_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      state isDraft headRefOid baseRefName title body author { login }
    }
  }
}
"""

GH_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated isCollapsed path line originalLine
          comments(first: 100) {
            pageInfo { hasNextPage endCursor }
            nodes { databaseId body author { login } createdAt }
          }
        }
      }
    }
  }
}
"""

GH_THREAD_COMMENTS_QUERY = """
query($id: ID!, $after: String) {
  node(id: $id) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { databaseId body author { login } createdAt }
      }
    }
  }
}
"""


class GitHub:
    def __init__(self, repo, host, number):
        self.number = number
        self.env = {}
        if repo:
            self.env["GH_REPO"] = f"{host}/{repo}" if host else repo
        self.host = ["--hostname", host] if host else []

    def api(self, *args, body=None):
        cmd = ["gh", "api", *self.host, *args]
        if body is not None:
            cmd += ["--input", "-"]
        out = run(cmd, stdin=json.dumps(body) if body is not None else None, env=self.env)
        return json.loads(out) if out.strip() else None

    def graphql(self, query, pr_scoped=True, **variables):
        args = ["graphql"]
        if pr_scoped:
            args += ["-F", "owner={owner}", "-F", "name={repo}", "-F", f"number={self.number}"]
        args += ["-f", f"query={query}"]
        for k, v in variables.items():
            args += ["-f" if isinstance(v, str) else "-F", f"{k}={v}"]
        return self.api(*args)

    def me(self):
        return self.api("user")["login"]

    def comments(self, thread):
        page = thread["comments"]
        notes = list(page["nodes"])
        while page["pageInfo"]["hasNextPage"]:
            data = self.graphql(GH_THREAD_COMMENTS_QUERY, pr_scoped=False,
                                id=thread["id"], after=page["pageInfo"]["endCursor"])
            page = data["data"]["node"]["comments"]
            notes += page["nodes"]
        return notes

    def state(self):
        data = self.graphql(GH_STATE_QUERY)
        pr = data["data"]["repository"]["pullRequest"]
        return {
            "state": {"OPEN": "open", "CLOSED": "closed", "MERGED": "merged"}[pr["state"]],
            "draft": pr["isDraft"],
            "head_sha": pr["headRefOid"],
            "base_ref": pr["baseRefName"],
            "title": pr["title"],
            "body": pr["body"] or "",
            "author": (pr["author"] or {}).get("login"),
            "ref": f"#{self.number}",
        }

    def threads(self):
        out, after = [], None
        while True:
            data = self.graphql(GH_THREADS_QUERY, after=after or "")
            page = data["data"]["repository"]["pullRequest"]["reviewThreads"]
            for t in page["nodes"]:
                notes = self.comments(t)
                out.append({
                    "id": t["id"],
                    "node_id": t["id"],
                    "first_comment_id": notes[0]["databaseId"] if notes else None,
                    "resolvable": True,
                    "resolved": t["isResolved"],
                    "outdated": t["isOutdated"],
                    "path": t["path"],
                    "line": t["line"] or t["originalLine"],
                    "notes": [
                        {"author": (n["author"] or {}).get("login"),
                         "body": n["body"], "created_at": n["createdAt"]}
                        for n in notes
                    ],
                })
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
        return out

    def reply(self, thread, body):
        cid = thread.get("first_comment_id")
        if not cid:
            raise Fail(6, f"thread {thread['id']} has no comment to reply to")
        res = self.api("-X", "POST",
                       f"repos/{{owner}}/{{repo}}/pulls/{self.number}/comments/{cid}/replies",
                       body={"body": body})
        return res["id"]

    def resolve(self, thread):
        node_id = thread.get("node_id") or thread["id"]
        self.api("graphql", "-f",
                 f'query=mutation {{ resolveReviewThread(input: {{threadId: "{node_id}"}}) '
                 '{ thread { isResolved } } }')
        return node_id


# GitLab -------------------------------------------------------------------


class GitLab:
    def __init__(self, repo, host, number):
        self.number = number
        self.project = quote(repo, safe="") if repo else ":fullpath"
        self.host = ["--hostname", host] if host else []
        self.mr = f"projects/{self.project}/merge_requests/{number}"

    def api(self, *args, body=None):
        cmd = ["glab", "api", *self.host, *args]
        if body is not None:
            cmd += ["-H", "Content-Type: application/json", "--input", "-"]
        out = run(cmd, stdin=json.dumps(body) if body is not None else None)
        return json.loads(out) if out.strip() else None

    def pages(self, endpoint):
        out = run(["glab", "api", *self.host, endpoint, "--paginate", "--output", "ndjson"])
        return [json.loads(line) for line in out.splitlines() if line.strip()]

    def me(self):
        return self.api("user")["username"]

    def state(self):
        mr = self.api(self.mr)
        state = {"opened": "open", "locked": "open"}.get(mr["state"], mr["state"])
        return {
            "state": state,
            "draft": bool(mr.get("draft", mr.get("work_in_progress"))),
            "head_sha": mr["sha"],
            "base_ref": mr["target_branch"],
            "title": mr["title"],
            "body": mr.get("description") or "",
            "author": (mr.get("author") or {}).get("username"),
            "ref": f"!{self.number}",
        }

    def threads(self):
        out = []
        head = self.state()["head_sha"]
        for d in self.pages(f"{self.mr}/discussions"):
            notes = d.get("notes") or []
            first = notes[0] if notes else {}
            pos = first.get("position") or {}
            out.append({
                "id": d["id"],
                "node_id": None,
                "first_comment_id": None,
                "resolvable": bool(first.get("resolvable")),
                "resolved": bool(first.get("resolved")),
                "outdated": bool(pos.get("head_sha")) and pos["head_sha"] != head,
                "path": pos.get("new_path") or pos.get("old_path"),
                "line": pos.get("new_line") or pos.get("old_line"),
                "notes": [
                    {"author": (n.get("author") or {}).get("username"),
                     "body": n.get("body", ""), "created_at": n.get("created_at")}
                    for n in notes
                ],
            })
        return out

    def reply(self, thread, body):
        res = self.api("-X", "POST", f"{self.mr}/discussions/{thread['id']}/notes",
                       body={"body": body})
        return res["id"]

    def resolve(self, thread):
        if not thread.get("resolvable"):
            raise Fail(6, f"thread {thread['id']} is not resolvable")
        self.api("-X", "PUT", f"{self.mr}/discussions/{thread['id']}", body={"resolved": "true"})
        return thread["id"]


# Commands ---------------------------------------------------------------


def client(args):
    provider, repo, host, number = parse_target(args.pr, args.provider, args.repo, args.host)
    if provider not in ("github", "gitlab"):
        raise Fail(2, f"--provider must be github or gitlab, got {provider!r}")
    return (GitHub if provider == "github" else GitLab)(repo, host, number), provider


def cmd_state(args):
    c, provider = client(args)
    s = c.state()
    print(json.dumps({
        "provider": provider,
        "ref": s["ref"],
        "state": s["state"],
        "draft": s["draft"],
        "head_sha": s["head_sha"],
        "base_ref": s["base_ref"],
        "title": s["title"],
        "author": s["author"],
        "body": s["body"],
    }, indent=1))


def cmd_threads(args):
    c, _ = client(args)
    threads = c.threads()
    if not args.include_resolved:
        threads = [t for t in threads if not t["resolved"]]
    for t in threads:
        t.pop("first_comment_id", None)
    print(json.dumps({"threads": threads}, indent=1))


def find_thread(threads, thread_id):
    for t in threads:
        if t["id"] == thread_id or t.get("node_id") == thread_id:
            return t
    raise Fail(5, f"no thread {thread_id!r} found")


def read_reply_body(path):
    try:
        with open(path, encoding="utf-8") as fh:
            body = fh.read().strip()
    except OSError as e:
        raise Fail(2, f"can't read --body-file: {e}")
    if not body:
        raise Fail(2, f"--body-file {path} is empty")
    return body


def read_batch(path):
    try:
        with open(path, encoding="utf-8") as fh:
            entries = json.load(fh)
    except (OSError, ValueError) as e:
        raise Fail(2, f"can't read --batch: {e}")
    if not isinstance(entries, list) or not entries:
        raise Fail(2, "--batch must be a non-empty JSON list")
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not e.get("thread") or not e.get("body_file"):
            raise Fail(2, f"--batch entry {i} needs thread and body_file")
    return [(str(e["thread"]), e["body_file"], e.get("resolve") is True) for e in entries]


def cmd_reply(args):
    if args.batch:
        if args.thread or args.body_file or args.resolve:
            raise Fail(2, "--batch replaces --thread, --body-file, and --resolve")
        entries = read_batch(args.batch)
    else:
        entries = [(args.thread, args.body_file, args.resolve)]
    bodies = [read_reply_body(f) for _, f, _ in entries]

    c, _ = client(args)
    ctx = c.state()
    if ctx["state"] in ("closed", "merged") and not args.allow_closed:
        raise Fail(4, f"{ctx['ref']} is {ctx['state']}; nothing replied. "
                      "Pass --allow-closed only if the user asked to "
                      "reply on it anyway")
    all_threads = c.threads()
    threads = [find_thread(all_threads, t) for t, _, _ in entries]
    me = None if args.dry_run else c.me()
    wrote = False

    for i, ((tid, _, resolve), body, thread) in enumerate(zip(entries, bodies, threads)):
        if args.dry_run:
            out = {"replied": "dry-run", "resolved": False, "id": None, "body": body}
        else:
            if wrote:
                time.sleep(WRITE_PAUSE)
            out = reply_one(c, me, thread, body, resolve)
            wrote = out["replied"] is True or out["resolved"]
        if args.batch:
            print(json.dumps({"index": i, "thread": tid, **out}))
        else:
            print(json.dumps(out, indent=1 if args.dry_run else None))


def reply_one(c, me, thread, body, resolve):
    already_replied = any(n["author"] == me and n["body"].strip() == body
                          for n in thread["notes"])
    nid = None
    if already_replied:
        replied = "skipped"
    else:
        nid = c.reply(thread, body)
        replied = True
        thread["notes"].append({"author": me, "body": body})

    resolved = False
    if resolve and not thread["resolved"]:
        c.resolve(thread)
        thread["resolved"] = resolved = True
    return {"replied": replied, "resolved": resolved, "id": nid}


def cmd_resolve(args):
    c, _ = client(args)
    thread = find_thread(c.threads(), args.thread)
    nid = c.resolve(thread)
    print(json.dumps({"resolved": True, "id": nid}))


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    p = argparse.ArgumentParser(prog="pr.py", add_help=False)
    p.add_argument("command", choices=["state", "threads", "reply", "resolve"])
    p.add_argument("pr")
    p.add_argument("--provider", choices=["github", "gitlab"])
    p.add_argument("--repo", help="owner/name or group/sub/project")
    p.add_argument("--host", help="GitHub Enterprise or self-hosted GitLab host")
    p.add_argument("--thread")
    p.add_argument("--body-file")
    p.add_argument("--include-resolved", action="store_true")
    p.add_argument("--resolve", action="store_true")
    p.add_argument("--allow-closed", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--batch")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        if args.command == "state":
            cmd_state(args)
        elif args.command == "threads":
            cmd_threads(args)
        elif args.command == "reply":
            if not args.batch and not args.thread:
                raise Fail(2, "reply needs --thread")
            if not args.batch and not args.body_file:
                raise Fail(2, "reply needs --body-file")
            cmd_reply(args)
        else:
            if not args.thread:
                raise Fail(2, "resolve needs --thread")
            cmd_resolve(args)
    except Fail as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
