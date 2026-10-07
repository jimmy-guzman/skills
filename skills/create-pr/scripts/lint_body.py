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
Checks, anywhere:
  em dash, en dash, middle dot, curly quotes or apostrophes
Checks outside fenced code blocks, on bullets at any indent:
  3+ version arrows (->)
  more than 25 words (an inline code span counts as one)
  more than one semicolon
Checks under ## What, reported at the heading:
  more than 6 top-level bullets, or more than 10 bullets in all
Checks under ## Why, reported at the heading (a ticket-only line is skipped):
  more than 2 paragraphs, or more than 80 words

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
BULLET = re.compile(r"^( *)- (.*)")
CODE = re.compile(r"`[^`]+`")
TICKET = re.compile(
    r"^(?:(?i:closes|fixes|resolves|relates to)\s+)?"
    r"(?:#\d+|[A-Z][A-Z0-9]+-\d+|\[[A-Z][A-Z0-9]+-\d+\]\([^)]+\))\.?$"
)
MAX_WORDS = 25
MAX_TOP = 6
MAX_BULLETS = 10
MAX_PARAGRAPHS = 2
MAX_WHY_WORDS = 80


def words(text):
    if text.count("`") % 2:
        return len(text.split())
    return len(CODE.sub("x", text).split())


def lint(lines):
    problems = []
    fenced = False
    section = None  # (name, heading line)
    top = total = 0
    paragraphs = []  # each a list of lines
    current = []

    def end_paragraph():
        nonlocal current
        if current:
            paragraphs.append(current)
            current = []

    def end_section():
        if not section:
            return
        name, at = section
        if name == "What":
            if top > MAX_TOP:
                problems.append((at, f"{top} top-level bullets under ## What: group to {MAX_TOP} or fewer"))
            if total > MAX_BULLETS:
                problems.append((at, f"{total} bullets under ## What: keep it to {MAX_BULLETS} or fewer"))
        else:
            end_paragraph()
            prose = [p for p in paragraphs if not (len(p) == 1 and TICKET.match(p[0].strip()))]
            if len(prose) > MAX_PARAGRAPHS:
                problems.append((at, f"{len(prose)} paragraphs under ## Why: keep it to two"))
            count = sum(words(line) for p in prose for line in p)
            if count > MAX_WHY_WORDS:
                problems.append((at, f"## Why runs {count} words: keep it to {MAX_WHY_WORDS} or fewer"))

    for n, line in enumerate(lines, 1):
        for ch, message in CHARS.items():
            if ch in line:
                problems.append((n, message))
        if line.lstrip().startswith("```"):
            fenced = not fenced
            end_paragraph()
            continue
        if fenced:
            continue
        if line.startswith("## "):
            end_section()
            name = line[3:].strip()
            section = (name, n) if name in ("What", "Why") else None
            top = total = 0
            paragraphs, current = [], []
            continue
        if section and section[0] == "Why":
            if line.strip():
                current.append(line)
            else:
                end_paragraph()
        m = BULLET.match(line)
        if not m:
            continue
        indent, text = m.groups()
        if section and section[0] == "What":
            total += 1
            top += not indent
        if text.count("->") >= 3:
            problems.append((n, "3+ version arrows on one bullet: split into a sub-list"))
        if words(text) > MAX_WORDS:
            problems.append((n, f"bullet over {MAX_WORDS} words: say what changed, not how"))
        if text.count(";") > 1:
            problems.append((n, "more than one semicolon in a bullet: split it or cut a clause"))
    end_section()
    return sorted(problems)


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
