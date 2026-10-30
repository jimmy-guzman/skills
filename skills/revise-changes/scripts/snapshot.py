#!/usr/bin/env python3
"""Save the working tree as a commit, or undo edits made since one.

One plain command in place of a shell pipeline, so hosts that refuse $(...),
&& chains, or pipes (a Claude Code session running inside a worktree) can run it.
Stdlib only. Runs from the repo root whatever the working directory.

Usage:
  snapshot.py                     print the SHA of a commit holding the working tree
  snapshot.py --guard BEFORE      undo every change since BEFORE, print JSON
  snapshot.py --cleanup TARGET... remove reviewer worktrees and branches, print JSON

The snapshot includes untracked files and leaves the user's index and files
alone: it stages into a copy of the index. ':/' is the root of the current
worktree, so sibling worktrees never land in it; worktrees nested under it
(any `git worktree list` reports there, where hosts put subagent worktrees) are
left out so they never land as gitlinks.

--guard takes a fresh snapshot as AFTER. When the trees match it prints
{"changed": false}. Otherwise it saves `git diff-tree -p --binary BEFORE AFTER`
to a temp file, applies the reverse to the working tree, and prints
{"changed": true, "files": [...], "patch": "<path>"}.

--cleanup takes worktree paths or branch names. For a worktree it records
`git status --porcelain` there, removes it with --force, and deletes the
branch it had checked out. A branch name alone is deleted, for hosts that
remove the worktree but leave its branch. It never touches the worktree it runs
from, and git itself refuses the main worktree and any branch still checked
out. Prints one {"target", "dirty", "removed", "error"} object per target.
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
    r = subprocess.run(["git", *args], capture_output=True, env=env, input=input, check=False)
    if r.returncode != 0:
        sys.exit(f"snapshot.py: git {args[0]} failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def nested_worktrees():
    top = pathlib.Path.cwd().resolve()
    for line in git("worktree", "list", "--porcelain").decode().splitlines():
        if line.startswith("worktree "):
            p = pathlib.Path(line[len("worktree ") :]).resolve()
            if p != top and p.is_relative_to(top):
                yield p.relative_to(top).as_posix()


def snapshot():
    tmp = tempfile.mkdtemp()
    try:
        idx = pathlib.Path(tmp) / "index"
        real = pathlib.Path(git("rev-parse", "--git-path", "index").decode().strip())
        if real.exists():
            shutil.copy2(real, idx)  # keep mtime so git still rechecks racily-clean files
        env = {**os.environ, "GIT_INDEX_FILE": str(idx)}
        # git add refuses any pathspec naming an ignored path, exclusions included,
        # and an ignored worktree is skipped without one.
        excludes = [
            f":!/{p}" for p in nested_worktrees() if subprocess.run(["git", "check-ignore", "-q", p], check=False).returncode != 0
        ]
        git("add", "-A", "--", ":/", *excludes, env=env)
        tree = git("write-tree", env=env).decode().strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    head = subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], capture_output=True, text=True, check=False)
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


def cleanup_one(t, here):
    res = {"target": t, "dirty": [], "removed": [], "error": None}

    def run(*args):
        r = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
        if r.returncode != 0 and res["error"] is None:
            res["error"] = f"git {args[0]}: {r.stderr.strip()}"
        return r

    path = pathlib.Path(t).expanduser()
    if not path.is_dir():
        if run("branch", "-D", t).returncode == 0:
            res["removed"].append(f"branch {t}")
        return res
    if path.resolve() == here:
        res["error"] = "refusing to remove the worktree this runs from"
        return res
    res["dirty"] = run("-C", str(path), "status", "--porcelain").stdout.splitlines()
    branch = run("-C", str(path), "branch", "--show-current").stdout.strip()
    if run("worktree", "remove", "--force", str(path)).returncode != 0:
        return res
    res["removed"].append(f"worktree {t}")
    if branch and run("branch", "-D", branch).returncode == 0:
        res["removed"].append(f"branch {branch}")
    return res


def cleanup(targets):
    here = pathlib.Path.cwd().resolve()
    return [cleanup_one(t, here) for t in targets]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard", metavar="BEFORE")
    ap.add_argument("--cleanup", metavar="TARGET", nargs="+")
    a = ap.parse_args()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if top.returncode != 0:
        sys.exit("snapshot.py: not inside a git repository")
    os.chdir(top.stdout.strip())
    if a.cleanup:
        print(json.dumps(cleanup(a.cleanup)))
    else:
        print(json.dumps(guard(a.guard)) if a.guard else snapshot())


if __name__ == "__main__":
    main()
