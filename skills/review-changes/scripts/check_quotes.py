#!/usr/bin/env python3
"""Check that each finding's quoted code sits at its file:line.

Catches made-up or drifted line numbers before a finding is reported or
posted. Stdlib only. Run with the repo as the working directory.
"""

import json
import re
import subprocess
import sys

USAGE = """\
Usage:
  check_quotes.py [--rev REV] FINDINGS.json
  check_quotes.py [--rev REV] -            (read findings from stdin)

FINDINGS.json is a list of objects:
  {"id": 1, "path": "src/tabs.ts", "line": "88", "quote": "const active = next[index] ?? null;"}
"line" is N or N-M. "quote" is one line of code, or part of one. Before
comparing, runs of whitespace collapse to one space and curly quotes become
straight ones, in both the quote and the file. Case still matters.

--rev reads files at a commit (the reviewed head). Without it, files are
read from the working tree, which is right for uncommitted changes.

Prints a JSON list, one entry per finding:
  {"id": 1, "status": "ok"}
  {"id": 2, "status": "moved", "found_at": [91]}    quote is elsewhere in the file
  {"id": 3, "status": "missing", "near": {...}}     quote is not in the file;
                                                    "near" holds the lines
                                                    around the claimed line,
                                                    to re-quote from
  {"id": 4, "status": "no-file"}                    path doesn't exist at REV

Exit codes:
  0 every quote is where its finding says
  1 at least one moved, missing, or no-file; fix or drop those findings
  2 bad arguments or input
"""


CURLY = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
NEAR = 3


def normalize(text):
    return re.sub(r"\s+", " ", text.translate(CURLY)).strip()


def read_file(path, rev):
    if rev:
        p = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True)
        return p.stdout.splitlines() if p.returncode == 0 else None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return None


def span(raw):
    parts = str(raw).split("-")
    start = int(parts[0])
    end = int(parts[1]) if len(parts) > 1 else start
    if start < 1 or end < start:
        raise ValueError(raw)
    return start, end


def check(finding, rev, cache):
    fid = finding.get("id")
    path, quote = finding["path"], normalize(finding["quote"])
    if not quote:
        return {"id": fid, "status": "missing", "reason": "empty quote"}
    if path not in cache:
        lines = read_file(path, rev)
        cache[path] = (lines, [normalize(t) for t in lines] if lines is not None else None)
    lines, flat = cache[path]
    if lines is None:
        return {"id": fid, "status": "no-file"}
    start, end = span(finding["line"])
    if any(quote in flat[i - 1] for i in range(start, min(end, len(flat)) + 1)):
        return {"id": fid, "status": "ok"}
    found = [n for n, text in enumerate(flat, 1) if quote in text]
    if found:
        return {"id": fid, "status": "moved", "found_at": found[:5]}
    lo, hi = max(1, start - NEAR), min(len(lines), end + NEAR)
    near = {str(n): lines[n - 1][:200] for n in range(lo, hi + 1)}
    return {"id": fid, "status": "missing", "near": near}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    rev = None
    if argv[0] == "--rev":
        if len(argv) < 3:
            print("error: --rev needs a value and a findings file\n" + USAGE, file=sys.stderr)
            return 2
        rev, argv = argv[1], argv[2:]
    src = argv[0]
    try:
        raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
        findings = json.loads(raw)
        cache = {}
        results = [check(f, rev, cache) for f in findings]
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"error: can't read findings ({e}). Each needs path, line, and quote.", file=sys.stderr)
        return 2
    print(json.dumps(results, indent=1))
    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
