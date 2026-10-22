#!/usr/bin/env python3
"""Read PR state and post, fix, and resolve review comments on GitHub or GitLab.

Wraps gh and glab so the skill gets the same JSON from both providers.
Run it with the repo as the working directory. Stdlib only.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from urllib.parse import quote, urlparse

USAGE = """\
Usage:
  pr.py state <pr> [--provider P] [--repo R] [--host H]
  pr.py post  <pr> --body-file F [--path P --line N[-M]] [--head SHA]
              [--allow-closed] [--dry-run]
              [--provider P] [--repo R] [--host H]
  pr.py edit    <pr> --comment ID --body-file F [--general] [--allow-closed] [--dry-run]
  pr.py delete  <pr> --comment ID [--general] [--allow-closed] [--dry-run]
  pr.py reply   <pr> --comment ID --body-file F [--allow-closed] [--dry-run]
  pr.py resolve <pr> --comment ID [--dry-run]

<pr> is a number (285), a ref (#285, !482), or a PR/MR URL.
Without --path, post writes one general comment. Every post starts with
<!-- review-changes: <head_sha> -->, which state reads into reviewed_shas.

state prints one JSON object:
  provider, ref, state (open|closed|merged), draft, head_sha, base_ref, title,
  author, body (the PR description), threads {open, resolved, anchors[]}, reviewed_shas[],
  reviewed_at_head, files [{path, additions, deletions}], truncated

post prints one JSON object:
  posted (inline|general|skipped), reason, id

edit, delete, reply, and resolve take the id that post returned. Pass
--general when that id came from a general comment; reply and resolve
work on inline comments only. Each prints one JSON object:
  <command> (true|dry-run), id

post, edit, delete, and reply refuse a closed or merged PR by default and
exit 4. Pass --allow-closed only when the user explicitly asked to write
on that PR.

Exit codes:
  0 ok (including a skipped duplicate)
  2 bad arguments
  3 head moved: the PR head is not --head; re-review before posting
  4 PR is closed or merged and --allow-closed wasn't passed; nothing posted
  5 gh/glab call failed (auth, network, not found); stderr says which
  6 resolve found no review thread for --comment

Examples:
  pr.py state 285
  pr.py state https://gitlab.example.com/grp/app/-/merge_requests/482
  pr.py post 285 --head 1a2b3c4 --path src/tabs.ts --line 88 \\
      --body-file /tmp/f1.md
  pr.py post !482 --body-file /tmp/general.md --dry-run
  pr.py reply 285 --comment 991 --body-file /tmp/downgrade.md
  pr.py resolve 285 --comment 991
"""

MARKER = "<!-- review-changes: {} -->"
MARKER_RE = re.compile(r"<!-- review-changes: ([0-9a-f]{7,40}) -->")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def run(cmd, stdin=None, env=None):
    try:
        p = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True,
            env={**os.environ, **(env or {})},
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


# Diff parsing ------------------------------------------------------------


def commentable_lines(patch):
    """Map each new-side line inside a hunk to its old-side line.

    Added lines map to None. Context lines map to their old line number,
    which GitLab needs to anchor a comment on an unchanged line.
    """
    lines, old, new = {}, None, None
    for text in (patch or "").splitlines():
        h = HUNK_RE.match(text)
        if h:
            old, new = int(h.group(1)), int(h.group(2))
            continue
        if new is None or text.startswith("\\"):
            continue
        if text.startswith("+"):
            lines[new] = None
            new += 1
        elif text.startswith("-"):
            old += 1
        else:
            lines[new] = old
            old += 1
            new += 1
    return lines


def norm(body):
    return MARKER_RE.sub("", body or "").strip()


def patch_counts(patch):
    """Count added/removed lines in a unified diff hunk body."""
    added = removed = 0
    for text in (patch or "").splitlines():
        if text.startswith(("+++", "---")):
            continue
        if text.startswith("+"):
            added += 1
        elif text.startswith("-"):
            removed += 1
    return added, removed


# GitHub -----------------------------------------------------------------

GH_STATE_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      state isDraft headRefOid baseRefName title body author { login }
      comments(last: 100) { nodes { body } pageInfo { hasPreviousPage } }
      reviews(last: 100) { nodes { body } pageInfo { hasPreviousPage } }
      reviewThreads(first: 100) {
        pageInfo { hasNextPage }
        nodes {
          isResolved isOutdated path line originalLine
          comments(first: 1) { nodes { body } }
        }
      }
    }
  }
}
"""

GH_THREAD_IDS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { id comments(first: 1) { nodes { databaseId } } }
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

    def pages(self, endpoint):
        pages = self.api(endpoint, "--paginate", "--slurp")
        return [item for page in pages for item in page]

    def state(self):
        data = self.api(
            "graphql", "-F", "owner={owner}", "-F", "name={repo}",
            "-F", f"number={self.number}", "-f", f"query={GH_STATE_QUERY}",
        )
        pr = data["data"]["repository"]["pullRequest"]
        threads = pr["reviewThreads"]["nodes"]
        bodies = [n["body"] for n in pr["comments"]["nodes"] + pr["reviews"]["nodes"]]
        anchors = []
        for t in threads:
            first = (t["comments"]["nodes"] or [{"body": ""}])[0]["body"]
            bodies.append(first)
            anchors.append({
                "path": t["path"],
                "line": t["line"] or t["originalLine"],
                "resolved": t["isResolved"],
                "outdated": t["isOutdated"],
                "first_line": first_line(first),
            })
        return {
            "state": {"OPEN": "open", "CLOSED": "closed", "MERGED": "merged"}[pr["state"]],
            "draft": pr["isDraft"],
            "head_sha": pr["headRefOid"],
            "base_ref": pr["baseRefName"],
            "title": pr["title"],
            "body": pr["body"] or "",
            "author": (pr["author"] or {}).get("login"),
            "anchors": anchors,
            "bodies": bodies,
            "files": self.file_counts(),
            "truncated": pr["reviewThreads"]["pageInfo"]["hasNextPage"]
            or pr["comments"]["pageInfo"]["hasPreviousPage"]
            or pr["reviews"]["pageInfo"]["hasPreviousPage"],
            "ref": f"#{self.number}",
        }

    def pr_files(self):
        return self.pages(f"repos/{{owner}}/{{repo}}/pulls/{self.number}/files")

    def files(self):
        out = {}
        for f in self.pr_files():
            out[f["filename"]] = {"lines": commentable_lines(f.get("patch")),
                                  "old_path": f.get("previous_filename", f["filename"])}
        return out

    def file_counts(self):
        return [{"path": f["filename"], "additions": f.get("additions", 0),
                 "deletions": f.get("deletions", 0)} for f in self.pr_files()]

    def existing(self):
        seen = set()
        for c in self.pages(f"repos/{{owner}}/{{repo}}/pulls/{self.number}/comments"):
            seen.add((c["path"], c.get("line") or c.get("original_line"), norm(c["body"])))
        for c in self.pages(f"repos/{{owner}}/{{repo}}/issues/{self.number}/comments"):
            seen.add((None, None, norm(c["body"])))
        return seen

    def post_inline(self, ctx, path, start, end, body, _old):
        payload = {"body": body, "commit_id": ctx["head_sha"], "path": path,
                   "line": end, "side": "RIGHT"}
        if start != end:
            payload.update(start_line=start, start_side="RIGHT")
        return self.api("-X", "POST", f"repos/{{owner}}/{{repo}}/pulls/{self.number}/comments",
                        body=payload)["id"]

    def post_general(self, ctx, body):
        return self.api("-X", "POST", f"repos/{{owner}}/{{repo}}/issues/{self.number}/comments",
                        body={"body": body})["id"]

    def comment_url(self, cid, general):
        return f"repos/{{owner}}/{{repo}}/{'issues' if general else 'pulls'}/comments/{cid}"

    def edit(self, cid, body, general):
        self.api("-X", "PATCH", self.comment_url(cid, general), body={"body": body})
        return cid

    def delete(self, cid, general):
        self.api("-X", "DELETE", self.comment_url(cid, general))
        return cid

    def reply(self, cid, body):
        return self.api("-X", "POST", f"repos/{{owner}}/{{repo}}/pulls/comments/{cid}/replies",
                        body={"body": body})["id"]

    def resolve(self, cid):
        after = []
        while True:
            data = self.api("graphql", "-F", "owner={owner}", "-F", "name={repo}",
                            "-F", f"number={self.number}", *after,
                            "-f", f"query={GH_THREAD_IDS_QUERY}")
            page = data["data"]["repository"]["pullRequest"]["reviewThreads"]
            for t in page["nodes"]:
                first = t["comments"]["nodes"]
                if first and str(first[0]["databaseId"]) == str(cid):
                    self.api("graphql", "-f",
                             f'query=mutation {{ resolveReviewThread(input: {{threadId: "{t["id"]}"}}) '
                             '{ thread { isResolved } } }')
                    return t["id"]
            if not page["pageInfo"]["hasNextPage"]:
                raise Fail(6, f"no review thread starts with comment {cid}")
            after = ["-f", f"after={page['pageInfo']['endCursor']}"]


# GitLab -----------------------------------------------------------------


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

    def mr_object(self):
        return self.api(self.mr)

    def state(self):
        mr = self.mr_object()
        discussions = self.pages(f"{self.mr}/discussions")
        anchors, bodies = [], []
        for d in discussions:
            notes = d.get("notes") or []
            bodies += [n.get("body", "") for n in notes]
            first = notes[0] if notes else {}
            if not first.get("resolvable"):
                continue
            pos = first.get("position") or {}
            anchors.append({
                "path": pos.get("new_path") or pos.get("old_path"),
                "line": pos.get("new_line") or pos.get("old_line"),
                "resolved": bool(first.get("resolved")),
                "outdated": False,
                "first_line": first_line(first.get("body", "")),
            })
        state = {"opened": "open", "locked": "open"}.get(mr["state"], mr["state"])
        return {
            "state": state,
            "draft": bool(mr.get("draft", mr.get("work_in_progress"))),
            "head_sha": mr["sha"],
            "base_ref": mr["target_branch"],
            "title": mr["title"],
            "body": mr.get("description") or "",
            "author": (mr.get("author") or {}).get("username"),
            "anchors": anchors,
            "bodies": bodies,
            "files": self.file_counts(),
            "truncated": False,
            "ref": f"!{self.number}",
            "diff_refs": mr.get("diff_refs"),
        }

    def mr_diffs(self):
        try:
            return self.pages(f"{self.mr}/diffs")
        except Fail:
            return (self.api(f"{self.mr}/changes") or {}).get("changes", [])

    def files(self):
        return {d["new_path"]: {"lines": commentable_lines(d.get("diff")),
                                "old_path": d.get("old_path", d["new_path"])}
                for d in self.mr_diffs()}

    def file_counts(self):
        out = []
        for d in self.mr_diffs():
            added, removed = patch_counts(d.get("diff"))
            out.append({"path": d["new_path"], "additions": added, "deletions": removed})
        return out

    def existing(self):
        seen = set()
        for d in self.pages(f"{self.mr}/discussions"):
            for n in d.get("notes") or []:
                pos = n.get("position") or {}
                seen.add((pos.get("new_path"), pos.get("new_line"), norm(n.get("body"))))
        return seen

    def post_inline(self, ctx, path, _start, end, body, old):
        refs = ctx.get("diff_refs") or {}
        position = {
            "position_type": "text",
            "base_sha": refs.get("base_sha"),
            "start_sha": refs.get("start_sha"),
            "head_sha": refs.get("head_sha"),
            "old_path": old["old_path"],
            "new_path": path,
            "new_line": end,
        }
        if old["old_line"] is not None:
            position["old_line"] = old["old_line"]
        res = self.api("-X", "POST", f"{self.mr}/discussions",
                       body={"body": body, "position": position})
        return res["id"]

    def post_general(self, ctx, body):
        return self.api("-X", "POST", f"{self.mr}/notes", body={"body": body})["id"]

    # An inline id is a discussion id; a general id is a note id.
    def note_id(self, cid, general):
        return cid if general else self.api(f"{self.mr}/discussions/{cid}")["notes"][0]["id"]

    def edit(self, cid, body, general):
        nid = self.note_id(cid, general)
        self.api("-X", "PUT", f"{self.mr}/notes/{nid}", body={"body": body})
        return nid

    def delete(self, cid, general):
        nid = self.note_id(cid, general)
        self.api("-X", "DELETE", f"{self.mr}/notes/{nid}")
        return nid

    def reply(self, cid, body):
        return self.api("-X", "POST", f"{self.mr}/discussions/{cid}/notes",
                        body={"body": body})["id"]

    def resolve(self, cid):
        self.api("-X", "PUT", f"{self.mr}/discussions/{cid}", body={"resolved": True})
        return cid


def first_line(body):
    text = norm(body)
    line = text.splitlines()[0] if text else ""
    return line[:120]


# Commands ---------------------------------------------------------------


def client(args):
    provider, repo, host, number = parse_target(args.pr, args.provider, args.repo, args.host)
    if provider not in ("github", "gitlab"):
        raise Fail(2, f"--provider must be github or gitlab, got {provider!r}")
    return (GitHub if provider == "github" else GitLab)(repo, host, number), provider


def cmd_state(args):
    c, provider = client(args)
    s = c.state()
    reviewed = sorted({m for b in s["bodies"] for m in MARKER_RE.findall(b or "")})
    head = s["head_sha"]
    print(json.dumps({
        "provider": provider,
        "ref": s["ref"],
        "state": s["state"],
        "draft": s["draft"],
        "head_sha": head,
        "base_ref": s["base_ref"],
        "title": s["title"],
        "author": s["author"],
        "body": s["body"],
        "threads": {
            "open": sum(1 for a in s["anchors"] if not a["resolved"]),
            "resolved": sum(1 for a in s["anchors"] if a["resolved"]),
            "anchors": s["anchors"],
        },
        "reviewed_shas": reviewed,
        "reviewed_at_head": any(head.startswith(r) or r.startswith(head) for r in reviewed),
        "files": s["files"],
        "truncated": s["truncated"],
    }, indent=1))


def parse_lines(raw):
    m = re.match(r"^(\d+)(?:-(\d+))?$", raw or "")
    if not m:
        raise Fail(2, f"--line must be N or N-M, got {raw!r}")
    start = int(m.group(1))
    end = int(m.group(2) or start)
    if end < start:
        raise Fail(2, f"--line range {raw} runs backwards")
    return start, end


def read_body(args):
    if not args.body_file:
        raise Fail(2, f"{args.command} needs --body-file")
    try:
        with open(args.body_file, encoding="utf-8") as fh:
            body = fh.read().strip()
    except OSError as e:
        raise Fail(2, f"can't read --body-file: {e}")
    if not body:
        raise Fail(2, "--body-file is empty")
    return body


def open_state(c, args):
    ctx = c.state()
    if ctx["state"] in ("closed", "merged") and not args.allow_closed:
        raise Fail(4, f"{ctx['ref']} is {ctx['state']}; nothing written. "
                      f"Pass --allow-closed only if the user asked to "
                      f"{args.command} on it anyway")
    return ctx


def cmd_post(args):
    if bool(args.path) != bool(args.line):
        raise Fail(2, "--path and --line go together; leave both out for a general comment")
    body = read_body(args)

    c, _ = client(args)
    ctx = open_state(c, args)
    head = ctx["head_sha"]
    if args.head and not head.startswith(args.head):
        raise Fail(3, f"{ctx['ref']} head is {head[:12]}, not {args.head[:12]}; "
                      "re-review the new head before posting")
    body = f"{MARKER.format(head)}\n{body}"

    kind, reason, anchor = "general", None, None
    if args.path:
        start, end = parse_lines(args.line)
        f = c.files().get(args.path)
        if f is None:
            reason = f"{args.path} is not in the diff"
        elif end not in f["lines"]:
            reason = f"{args.path}:{end} is outside the diff hunks"
        else:
            if start != end and not all(n in f["lines"] for n in range(start, end + 1)):
                start = end
            kind = "inline"
            anchor = (start, end, {"old_path": f["old_path"], "old_line": f["lines"][end]})

    key = (args.path, anchor[1], norm(body)) if kind == "inline" else (None, None, norm(body))
    if key in c.existing():
        print(json.dumps({"posted": "skipped", "reason": "same comment already on the PR", "id": None}))
        return

    if args.dry_run:
        print(json.dumps({"posted": f"dry-run:{kind}", "reason": reason, "id": None,
                          "path": args.path, "line": anchor[1] if anchor else None,
                          "body": body}, indent=1))
        return

    if kind == "inline":
        start, end, old = anchor
        nid = c.post_inline(ctx, args.path, start, end, body, old)
    else:
        nid = c.post_general(ctx, body)
    print(json.dumps({"posted": kind, "reason": reason, "id": nid}))


def cmd_followup(args):
    cmd = args.command
    if not args.comment:
        raise Fail(2, f"{cmd} needs --comment")
    if args.general and cmd in ("reply", "resolve"):
        raise Fail(2, f"a general comment has no thread to {cmd}; edit it instead")
    body = read_body(args) if cmd in ("edit", "reply") else None

    c, _ = client(args)
    if cmd != "resolve":
        open_state(c, args)
    if args.dry_run:
        print(json.dumps({cmd: "dry-run", "id": args.comment, "body": body}, indent=1))
        return

    if cmd == "edit":
        nid = c.edit(args.comment, body, args.general)
    elif cmd == "delete":
        nid = c.delete(args.comment, args.general)
    elif cmd == "reply":
        nid = c.reply(args.comment, body)
    else:
        nid = c.resolve(args.comment)
    print(json.dumps({cmd: True, "id": nid}))


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    p = argparse.ArgumentParser(prog="pr.py", add_help=False)
    p.add_argument("command", choices=["state", "post", "edit", "delete", "reply", "resolve"])
    p.add_argument("pr")
    p.add_argument("--provider", choices=["github", "gitlab"])
    p.add_argument("--repo", help="owner/name or group/sub/project")
    p.add_argument("--host", help="GitHub Enterprise or self-hosted GitLab host")
    p.add_argument("--body-file")
    p.add_argument("--path")
    p.add_argument("--line")
    p.add_argument("--head")
    p.add_argument("--comment")
    p.add_argument("--general", action="store_true")
    p.add_argument("--allow-closed", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        if args.command == "state":
            cmd_state(args)
        elif args.command == "post":
            cmd_post(args)
        else:
            cmd_followup(args)
    except Fail as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
