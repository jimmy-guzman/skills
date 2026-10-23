#!/usr/bin/env python3
"""Build the review pack: the diff, the changed files, and a head start on discovery.

Reads a unified diff on stdin and writes, under --out:
  diff.patch     the diff as given
  files/<path>   each changed file at --rev (or from the working tree)
  callers.txt    git grep hits for symbols the diff defines or touches
  tests.txt      test files that name a changed file
  anchors.txt    git grep hits for strings quoted in --spec, when given
Stdlib only. Runs from the repo root whatever the working directory.

Usage:
  <diff command> | pack.py --out DIR [--rev REV] [--extra PATH ...] [--spec PATH]

--extra copies untracked working-tree files into files/ (read-only mode, where
the diff can't show them). --spec is a text file holding the spec source (a
ticket, plan, or PR description): strings it quotes are grepped against the
tree so the Spec reviewer gets a head start on where they landed. Prints a
one-line JSON summary.
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
QUOTED = re.compile(r"`([^`]{4,120})`|[\"“]([^\"”]{4,120})[\"”]|'([^']{4,120})'")
MAX_SYMBOLS, MAX_HITS, MAX_ANCHORS = 60, 40, 40


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


def quoted_strings(text):
    """Backtick- or quote-delimited spans in a spec source, e.g. a ticket's exact output strings."""
    seen = {}
    for m in QUOTED.finditer(text):
        s = next(g for g in m.groups() if g is not None).strip()
        if s:
            seen.setdefault(s, None)
    return list(seen)[:MAX_ANCHORS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--rev")
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--spec")
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    diff = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not diff.strip():
        sys.exit("pack.py: empty diff on stdin")
    spec_text = pathlib.Path(a.spec).read_text(errors="replace") if a.spec else ""
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

    # ponytail: one word-boundary grep over the whole tree for all symbols, no language awareness.
    # Upgrade to an LSP/ctags pass if reviewers report the list is too noisy.
    rev_arg = [a.rev] if a.rev else ["--untracked"]
    strip = (lambda h: h.split(":", 1)[-1]) if a.rev else (lambda h: h)
    words = re.compile(r"\w+", re.ASCII)
    chunks = grouped_grep(symbols(diff), ["-w"], rev_arg, a.rev, lambda syms, text: syms & set(words.findall(text)))
    (out / "callers.txt").write_text("".join(chunks))

    anchor_chunks = grouped_grep(quoted_strings(spec_text), ["-F"], rev_arg, a.rev,
                                 lambda strs, text: {q for q in strs if q in text})
    (out / "anchors.txt").write_text("".join(anchor_chunks))

    stems = {pathlib.Path(p).stem for p in paths if pathlib.Path(p).stem not in ("index", "__init__", "mod")}
    flags = [f for stem in sorted(stems) for f in ("-e", stem)]
    hits = (git("grep", "-l", "-I", "-F", *flags, *rev_arg) or "").splitlines() if flags else []
    tests = sorted({strip(h) for h in hits if TEST_PATH.search(strip(h))})
    (out / "tests.txt").write_text("\n".join(tests) + ("\n" if tests else ""))

    print(json.dumps({
        "pack": str(out), "files": len(paths), "symbols": len(chunks),
        "tests": len(tests), "anchors": len(anchor_chunks),
    }))


def grouped_grep(patterns, flags, rev_arg, rev, matched):
    """One git grep for every pattern, then hits grouped under each pattern they match, in input order.

    One call costs about what one pattern does, where a call per pattern rescans the tree each time.
    `matched(set_of_patterns, line_text)` returns the patterns a hit line belongs to."""
    if not patterns:
        return []
    args = [x for p in patterns for x in ("-e", p)]
    groups = {p: [] for p in patterns}
    for line in (git("grep", "-n", "-z", "-I", *flags, *args, *rev_arg) or "").split("\n"):
        if not line:
            continue
        path, num, text = line.split("\0", 2)
        if rev:
            path = path.removeprefix(f"{rev}:")
        for p in matched(set(patterns), text):
            if len(groups[p]) < MAX_HITS:
                groups[p].append(f"{path}:{num}:{text}")
    return [f"## {p}\n" + "\n".join(hits) + "\n" for p, hits in groups.items() if hits]


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
