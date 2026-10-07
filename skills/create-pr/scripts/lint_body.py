#!/usr/bin/env python3
"""Lint a drafted PR or MR body before it is shown to the user.

Stdlib only.
"""

import re
import sys

USAGE = """\
Usage:
  lint_body.py BODY.md

Prints one line per problem: BODY.md:LINE: message
Checks:
  em dash, en dash, middle dot, curly quotes or apostrophes
  a top-level bullet with 3+ version arrows (->)
  a top-level bullet naming 3+ backticked items in a comma list

Exit codes:
  0 clean
  1 problems found; fix every line before showing the body
  2 bad arguments or unreadable file
"""

CHARS = {
    "—": "em dash: replace with period, comma, or hyphen",
    "–": "en dash: replace with period, comma, or hyphen",
    "·": "middle dot: replace with period, comma, or hyphen",
    "“": "curly quote: replace with straight quote",
    "”": "curly quote: replace with straight quote",
    "‘": "curly apostrophe: replace with straight apostrophe",
    "’": "curly apostrophe: replace with straight apostrophe",
}
TOP_BULLET = re.compile(r"^- ")
CODE = re.compile(r"`[^`]+`")


def lint(lines):
    problems = []
    for n, line in enumerate(lines, 1):
        for ch, message in CHARS.items():
            if ch in line:
                problems.append((n, message))
        if not TOP_BULLET.match(line):
            continue
        if line.count("->") >= 3:
            problems.append((n, "3+ version arrows on one bullet: split into a sub-list"))
        if len(CODE.findall(line)) >= 3 and line.count(",") >= 2:
            problems.append((n, "3+ named items on one bullet: split into a sub-list"))
    return problems


def main(argv):
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    path = argv[0]
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: can't read {path}: {e}", file=sys.stderr)
        return 2
    problems = lint(lines)
    for n, message in problems:
        print(f"{path}:{n}: {message}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
