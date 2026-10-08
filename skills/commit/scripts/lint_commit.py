#!/usr/bin/env python3
"""Lint a drafted commit message before it is shown to the user.

Stdlib only.
"""

import re
import sys

USAGE = """\
Usage:
  lint_commit.py MESSAGE.md [HEADER_MAX]

Prints one line per problem: MESSAGE.md:LINE: message
Checks, anywhere:
  em dash, en dash, middle dot, curly quotes or apostrophes
Checks on the subject line (line 1):
  past-tense or gerund leading verb instead of imperative
  over HEADER_MAX characters (default 50)
  trailing period
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
NON_IMPERATIVE = re.compile(
    r"^(?:\w+\([^)]*\)|\w+)?:?\s*"
    r"(added|fixed|updated|removed|refactored|changed|moved|renamed|deleted|created|"
    r"adding|fixing|updating|removing|refactoring|changing|moving|renaming|deleting|creating)\b",
    re.IGNORECASE,
)
DEFAULT_HEADER_MAX = 50


def lint(lines, header_max):
    problems = []

    for n, line in enumerate(lines, 1):
        for ch, message in CHARS.items():
            if ch in line:
                problems.append((n, message))

    if not lines:
        return sorted(problems)

    subject = lines[0]

    m = NON_IMPERATIVE.match(subject)
    if m:
        problems.append((1, f"'{m.group(1)}' is not imperative: use the base verb form, e.g. 'add' not '{m.group(1)}'"))

    if len(subject) > header_max:
        problems.append((1, f"subject is {len(subject)} chars: keep it to {header_max} or fewer"))

    if subject.rstrip().endswith("."):
        problems.append((1, "subject ends with a period: drop it"))

    return sorted(problems)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    if len(argv) > 2:
        print(USAGE)
        return 2
    path = argv[0]
    header_max = DEFAULT_HEADER_MAX
    if len(argv) == 2:
        try:
            header_max = int(argv[1])
        except ValueError:
            print(USAGE)
            return 2
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: can't read {path}: {e}", file=sys.stderr)
        return 2
    problems = lint(lines, header_max)
    for n, message in problems:
        print(f"{path}:{n}: {message}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
