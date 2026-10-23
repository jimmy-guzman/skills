#!/usr/bin/env python3
"""Save the working tree as a commit, or undo edits made since one.

One plain command in place of a shell pipeline, so hosts that refuse $(...),
&& chains, or pipes (a Claude Code session running inside a worktree) can run it.
Stdlib only. Runs from the repo root whatever the working directory.

Usage:
  snapshot.py                 print the SHA of a commit holding the working tree
  snapshot.py --guard BEFORE  undo every change since BEFORE, print JSON

The snapshot includes untracked files and leaves the user's index and files
alone: it stages into a copy of the index. ':/' is the root of the current
worktree, so sibling worktrees never land in it; '.claude/worktrees' is left
out because Claude Code nests subagent worktrees there.

--guard takes a fresh snapshot as AFTER. When the trees match it prints
{"changed": false}. Otherwise it saves `git diff-tree -p --binary BEFORE AFTER`
to a temp file, applies the reverse to the working tree, and prints
{"changed": true, "files": [...], "patch": "<path>"}.
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


def git(*args, env=None, input=None):
    r = subprocess.run(["git", *args], capture_output=True, env=env, input=input)
    if r.returncode != 0:
        sys.exit(f"snapshot.py: git {args[0]} failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def snapshot():
    tmp = tempfile.mkdtemp()
    try:
        idx = pathlib.Path(tmp) / "index"
        real = pathlib.Path(git("rev-parse", "--git-path", "index").decode().strip())
        if real.exists():
            shutil.copyfile(real, idx)
        env = {**os.environ, "GIT_INDEX_FILE": str(idx)}
        git("add", "-A", "--", ":/", ":!/.claude/worktrees", env=env)
        tree = git("write-tree", env=env).decode().strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    head = subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], capture_output=True, text=True)
    parent = ["-p", head.stdout.strip()] if head.returncode == 0 else []
    return git("commit-tree", tree, *parent, "-m", "snapshot").decode().strip()


def guard(before):
    after = snapshot()
    files = git("diff", "--name-only", before, after).decode().splitlines()
    if not files:
        return {"changed": False}
    fd, patch = tempfile.mkstemp(prefix="snapshot-guard-", suffix=".patch")
    with os.fdopen(fd, "wb") as f:
        f.write(git("diff-tree", "-p", "--binary", before, after))
    git("apply", "--binary", input=git("diff-tree", "-p", "--binary", after, before))
    return {"changed": True, "files": files, "patch": patch}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard", metavar="BEFORE")
    a = ap.parse_args()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        sys.exit("snapshot.py: not inside a git repository")
    os.chdir(top.stdout.strip())
    print(json.dumps(guard(a.guard)) if a.guard else snapshot())


if __name__ == "__main__":
    main()
