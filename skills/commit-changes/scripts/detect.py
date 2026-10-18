#!/usr/bin/env python3
"""Print everything commit-changes needs to know about the repo, in one block.

Branch, hooks, gitzy/commitlint/template config, the shape of recent human
commits, a ticket id, and what is staged, unstaged, and untracked.
Stdlib only. Runs from the repo root whatever the working directory.

Usage:
  detect.py
"""

import collections
import fnmatch
import json
import os
import re
import subprocess
import sys

PROTECTED = {"main", "master", "trunk", "develop"}
BOT = re.compile(r"\[bot\]|dependabot|renovate", re.IGNORECASE)
HEADER = re.compile(r"^(\w+)(\([^)]*\))?(!)?:\s*(.*)$")
EMOJI = re.compile(r"^([^\w\s\x00-\x7f]+)\s")
TICKET = re.compile(r"\b([A-Z][A-Z0-9]+)-(\d+)\b")
LOOKALIKE = {"UTF", "ISO", "ES", "SHA", "RFC", "CVE"}
TRAILER = re.compile(r"^[\w-]+: .+$")
SECRET = ["*.env*", "*secret*", "*.key", "*.pem", "credentials*", "*.p12"]
GITZY_FILES = [".gitzyrc", ".gitzyrc.json", ".gitzyrc.js", ".gitzyrc.cjs", ".gitzyrc.mjs"] + [
    f"gitzy.config.{ext}" for ext in ("js", "cjs", "mjs", "ts", "mts")
]
COMMITLINT_FILES = [f"commitlint.config.{ext}" for ext in ("js", "cjs", "mjs", "ts", "cts", "mts")] + [
    f".commitlintrc{ext}" for ext in ("", ".json", ".js", ".cjs", ".mjs", ".yml", ".yaml")
]
MAX_FILES = 30


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace", check=False)
    return r.stdout.rstrip("\n") if r.returncode == 0 else ""


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def package_json():
    try:
        return json.loads(read("package.json") or "{}")
    except ValueError:
        return {}


def config_hit(files, pkg, key):
    hits = [f for f in files if os.path.isfile(f)] + [f".config/{f}" for f in files if os.path.isfile(f".config/{f}")]
    if key in pkg:
        hits.append(f"package.json#{key}")
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if any(key in d for d in deps):
        hits.append("package.json deps")
    return ", ".join(hits) or "none"


def runs(text):
    """Name what a commit-msg hook runs: commitlint, gitzy, or the first custom command."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    body = "\n".join(lines)
    if "commitlint" in body:
        return "commitlint"
    if "gitzy" in body:
        return "gitzy"
    return f"custom ({lines[-1]})" if lines else "empty"


def hooks():
    found = []
    husky = read(".husky/commit-msg")
    if husky:
        found.append(f"commit-msg: {runs(husky)}")
    for name in ("lefthook.yml", "lefthook.yaml", ".lefthook.yml", ".lefthook.yaml"):
        text = read(name)
        if text and re.search(r"^commit-msg:", text, re.MULTILINE):
            found.append(f"commit-msg ({name}): {runs(text)}")
        if text and re.search(r"^pre-commit:", text, re.MULTILINE):
            found.append(f"pre-commit ({name})")
    hooks_dir = git("rev-parse", "--git-path", "hooks")
    plain = os.path.join(hooks_dir, "commit-msg")
    if not husky and os.access(plain, os.X_OK):
        found.append(f"commit-msg (.git/hooks): {runs(read(plain))}")
    if os.path.isfile(".husky/pre-commit") or os.access(os.path.join(hooks_dir, "pre-commit"), os.X_OK):
        found.append("pre-commit")
    return " | ".join(found) or "none"


def recent():
    """Last 20 human commits as (subject, body lines without trailers, trailers)."""
    out = git("log", "--no-merges", "-n", "50", "--format=%an%x1f%s%x1f%b%x1e")
    commits = []
    for rec in out.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) != 3 or BOT.search(parts[0]):
            continue
        body = [ln for ln in parts[2].splitlines() if ln.strip()]
        trailers = [ln for ln in body if TRAILER.match(ln)]
        commits.append((parts[1], [ln for ln in body if ln not in trailers], trailers))
    return commits[:20]


def shape(commits):
    n = len(commits)
    if not n:
        return "no human commits"
    kinds = collections.Counter()
    emoji = collections.defaultdict(collections.Counter)
    lower = bang = 0
    for subject, _, _ in commits:
        m = HEADER.match(subject)
        if not m:
            kinds["plain"] += 1
            lower += subject[:1].islower()
            continue
        kinds["type(scope):" if m.group(2) else "type:"] += 1
        bang += bool(m.group(3))
        rest = m.group(4)
        e = EMOJI.match(rest)
        if e:
            emoji[m.group(1)][e.group(1)] += 1
            rest = rest[e.end():]
        lower += rest[:1].islower()
    footer = sum("BREAKING CHANGE" in " ".join(b + t) for _, b, t in commits)
    bodies = sum(bool(b) for _, b, _ in commits)
    coauthor = sum(any(t.lower().startswith("co-authored-by:") for t in ts) for _, _, ts in commits)
    parts = [", ".join(f"{k} {v}" for k, v in kinds.most_common())]
    if emoji:
        parts.append("emoji after colon: " + ", ".join(f"{t} {c.most_common(1)[0][0]}" for t, c in emoji.items()))
    parts.append(f"lowercase {lower}/{n}")
    parts.append(f"longest {max(len(s) for s, _, _ in commits)} chars")
    marks = [m for m, hit in (("!", bang), ("footer", footer)) if hit]
    if marks:
        parts.append("breaking: " + "+".join(marks))
    parts.append(f"bodies {bodies}/{n}")
    parts.append(f"co-author {coauthor}/{n}")
    return " | ".join(parts)


def tickets(text):
    return [m.group(0) for m in TICKET.finditer(text) if m.group(1) not in LOOKALIKE]


def ticket(branch, commits):
    ids = tickets(branch)
    found = f"{ids[0]} (branch)" if ids else "none"
    used = sum(bool(tickets(s) or re.search(r"#\d+", s)) for s, _, _ in commits)
    return f"{found} | subjects with ids {used}/{len(commits)}"


def flag(path):
    marks = []
    base = os.path.basename(path)
    if any(fnmatch.fnmatch(base.lower(), g) for g in SECRET):
        marks.append("secret?")
    try:
        if os.path.getsize(path) > 1_000_000:
            marks.append(">1MB")
    except OSError:
        pass
    return f"  {path}" + (f"  [{', '.join(marks)}]" if marks else "")


def listing(label, paths, stat=""):
    lines = [f"{label}: {len(paths)}" + (f" ({stat.strip()})" if stat else "")]
    lines += [flag(p) for p in paths[:MAX_FILES]]
    if len(paths) > MAX_FILES:
        lines.append(f"  +{len(paths) - MAX_FILES} more")
    return lines


def main():
    root = git("rev-parse", "--show-toplevel")
    if not root:
        print("error: not a git repository", file=sys.stderr)
        return 2
    os.chdir(root)

    branch = git("branch", "--show-current") or "(detached)"
    protected = branch in PROTECTED or branch.startswith("release/")
    pkg = package_json()
    commits = recent()
    staged = git("diff", "--cached", "--name-only").splitlines()
    unstaged = git("diff", "--name-only").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    template = git("config", "--get", "commit.template") or (".gitmessage" if os.path.isfile(".gitmessage") else "none")

    out = [
        f"branch: {branch}" + (" (protected)" if protected else ""),
        f"hooks: {hooks()}",
        f"gitzy: {config_hit(GITZY_FILES, pkg, 'gitzy')}",
        f"commitlint: {config_hit(COMMITLINT_FILES, pkg, 'commitlint')}",
        f"template: {template}",
        f"shape: {shape(commits)}",
        f"ticket: {ticket(branch, commits)}",
    ]
    if not (staged or unstaged or untracked):
        out.append("changes: nothing to commit")
    else:
        out += listing("staged", staged, git("diff", "--cached", "--shortstat"))
        out += listing("unstaged", unstaged, git("diff", "--shortstat"))
        out += listing("untracked", untracked)
    out.append("subjects:")
    out += [f"  {s}" for s, _, _ in commits]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
