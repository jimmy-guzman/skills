#!/usr/bin/env python3
"""Build the review pack: the diff, the changed files, and a head start on discovery.

Reads a unified diff on stdin and writes, under --out:
  diff.patch     the diff as given
  files/<path>   each changed file at --rev (or from the working tree)
  callers.txt    git grep hits for symbols the diff defines or touches
  tests.txt      test files that name a changed file
Stdlib only. Runs from the repo root whatever the working directory.

Usage:
  <diff command> | pack.py --out DIR [--rev REV] [--extra PATH ...]

--extra copies untracked working-tree files into files/ (read-only mode, where
the diff can't show them). Prints a one-line JSON summary.
"""

import argparse
import codecs
import json
import os
import pathlib
import re
import subprocess
import sys

SYMBOL = re.compile(
    r"^[+-]\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:def|class|function|fn|func|interface|type|struct|enum|const|let|var)\s+([A-Za-z_]\w{2,})"
)
HUNK = re.compile(r"^@@ .* @@ .*?\b([A-Za-z_]\w{2,})\s*\(")
PREFIX = re.compile(r"^[abciwo]/")
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|[._-](test|spec)\.\w+$")
MAX_SYMBOLS, MAX_HITS = 60, 40


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else None


def unquote(p):
    """Undo git's C-style quoting of a path (core.quotePath), e.g. "b/caf\\303\\251.py"."""
    if p.startswith('"') and p.endswith('"'):
        p = codecs.escape_decode(p[1:-1].encode("utf-8"))[0].decode("utf-8", "replace")
    return p


def header_paths(diff):
    """Candidate paths per +++ header, best guess first.

    A diff has prefixes (a/ b/, or c/ i/ w/ o/ with mnemonicPrefix) or none (diff.noprefix). It has
    none when a ---/+++ pair names the same path, or when any +++ path lacks a one-letter prefix; then
    a real top-level b/ dir keeps its name. Otherwise strip first and keep the raw path as fallback."""
    # A header pair is `--- `, `+++ `, then `@@ ` (or a binary notice). Content lines that start with
    # `++ ` or `-- ` also render as `+++ `/`--- `, so one line alone is not a header.
    lines = diff.splitlines()
    pairs = []
    for i in range(1, len(lines) - 1):
        if lines[i].startswith("+++ ") and lines[i - 1].startswith("--- ") and lines[i + 1][:2] in ("@@", "Bi"):
            pairs.append((unquote(lines[i - 1][4:].rstrip("\t")), unquote(lines[i][4:].rstrip("\t"))))
    plus = [p for _, p in pairs if p != "/dev/null"]
    same = any(m == p for m, p in pairs if m and "/dev/null" not in (m, p))
    noprefix = same or not all(PREFIX.match(p) for p in plus)
    out = []
    for _, p in pairs:
        if p == "/dev/null":
            continue
        stripped = PREFIX.sub("", p)
        out.append((p,) if noprefix or stripped == p else (stripped, p))
    return out


def symbols(diff):
    seen = {}
    for line in diff.splitlines():
        m = SYMBOL.match(line) or HUNK.match(line)
        if m:
            seen.setdefault(m.group(1), None)
    return list(seen)[:MAX_SYMBOLS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--rev")
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    diff = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not diff.strip():
        sys.exit("pack.py: empty diff on stdin")
    top = git("rev-parse", "--show-toplevel")
    if top is None:
        sys.exit("pack.py: not inside a git repository")
    os.chdir(top.strip())
    (out / "files").mkdir(parents=True, exist_ok=True)
    (out / "diff.patch").write_text(diff)

    repo_root = pathlib.Path(top.strip()).resolve()
    files_root = (out / "files").resolve()
    paths = []
    for candidates in header_paths(diff) + [(p,) for p in a.extra]:
        for p in candidates:
            dest = out / "files" / p
            if not _contained(dest, files_root):
                continue
            content = git("show", f"{a.rev}:{p}") if a.rev and p not in a.extra else _read_tree(p, repo_root)
            if content is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)
                paths.append(p)
                break

    # ponytail: word-boundary grep over the whole tree, no language awareness.
    # Upgrade to an LSP/ctags pass if reviewers report the list is too noisy.
    rev_arg = [a.rev] if a.rev else ["--untracked"]
    strip = (lambda h: h.split(":", 1)[-1]) if a.rev else (lambda h: h)
    chunks = []
    for s in symbols(diff):
        hits = [strip(h) for h in (git("grep", "-n", "-w", "-I", "-e", s, *rev_arg) or "").splitlines()]
        if hits:
            chunks.append(f"## {s}\n" + "\n".join(hits[:MAX_HITS]) + "\n")
    (out / "callers.txt").write_text("".join(chunks))

    stems = {pathlib.Path(p).stem for p in paths if pathlib.Path(p).stem not in ("index", "__init__", "mod")}
    flags = [f for stem in sorted(stems) for f in ("-e", stem)]
    hits = (git("grep", "-l", "-I", "-F", *flags, *rev_arg) or "").splitlines() if flags else []
    tests = sorted({strip(h) for h in hits if TEST_PATH.search(strip(h))})
    (out / "tests.txt").write_text("\n".join(tests) + ("\n" if tests else ""))

    print(json.dumps({"pack": str(out), "files": len(paths), "symbols": len(chunks), "tests": len(tests)}))


def _contained(path, root):
    """True if path resolves to somewhere inside root (guards absolute paths and ../ escapes)."""
    try:
        return path.resolve().is_relative_to(root)
    except (OSError, ValueError):
        return False


def _read_tree(p, root):
    path = pathlib.Path(p)
    if not _contained(path, root):
        return None
    try:
        return path.read_text(errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return None


if __name__ == "__main__":
    main()
