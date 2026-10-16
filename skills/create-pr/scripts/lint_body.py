#!/usr/bin/env python3
"""Lint a drafted PR or MR body before it is shown to the user.

Stdlib only.
"""

import re
import sys

USAGE = """\
Usage:
  lint_body.py BODY.md [--files CHANGED.txt]

Prints one line per problem: BODY.md:LINE: message
CHANGED.txt holds one changed path per line (git diff --name-only).

Checks, anywhere:
  em dash, en dash, middle dot, curly quotes or apostrophes
Checks outside fenced code blocks:
  bullets at any indent: 3+ version arrows (->), more than 25 words
    (an inline code span counts as one), more than one semicolon
  assertions without evidence ("tests pass", "tested locally", ...)
  self-grading words ("robust", "comprehensive", "properly", ...)
Checks when the body uses the default shape (a **Why.** / **Approach.** /
**Review.** label opens a paragraph):
  a label other than those three, or a label with nothing after it
  Why first (only a ticket line may precede it), Review last
  Why opening with "This PR", "This change", "Adds", and the like
  Why over 80 words, Approach prose over 100, Review over 60
  more than 6 top-level bullets or 10 in all
  more than 180 words in all, fenced blocks excluded
Checks with --files:
  a backticked path that is not in the diff
  a claim of a new or added test when no test file changed

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
CODE = re.compile(r"`([^`]+)`")
LABEL = re.compile(r"^\*\*([A-Za-z]+)\.\*\*(.*)$")
LABELS = ("Why", "Approach", "Review")
TICKET = re.compile(
    r"^(?:(?i:closes|fixes|resolves|relates to)\s+)?"
    r"(?:#\d+|[A-Z][A-Z0-9]+-\d+|\[[A-Z][A-Z0-9]+-\d+\]\([^)]+\))\.?$"
)
OPENERS = re.compile(
    r"^(?:this (?:pr|mr|change|commit|patch)\b|introduc(?:es|ing)\b|adds?\b"
    r"|updates?\b|implements?\b|refactors?\b)",
    re.IGNORECASE,
)
ASSERTIONS = re.compile(
    r"\b(?:(?:all )?tests (?:pass|are passing|passed)|tested locally"
    r"|verified locally|manually tested|fully backwards? compatible"
    r"|backwards? compatible|works as expected|no regressions?|should work)\b",
    re.IGNORECASE,
)
SELF_GRADING = re.compile(
    r"\b(comprehensive(?:ly)?|robust(?:ly)?|seamless(?:ly)?|properly|correctly"
    r"|enhanc(?:e|es|ed|ing)|leverag(?:e|es|ed|ing)|streamlin(?:e|es|ed|ing))\b",
    re.IGNORECASE,
)
TEST_CLAIM = re.compile(
    r"\b(?:adds?|added|new|wrote|writes?|introduc(?:es|ed))\b[^.;]{0,30}?"
    r"\b(?:unit |integration |e2e |snapshot |regression )?tests?\b",
    re.IGNORECASE,
)
TEST_FILE = re.compile(r"(?:^|/)(?:tests?|__tests__|spec)/|[._-](?:test|spec)\.|_test\.")
EXTENSIONS = {
    "ts", "tsx", "js", "jsx", "mjs", "cjs", "vue", "svelte", "astro", "css", "scss",
    "less", "html", "md", "mdx", "json", "yaml", "yml", "toml", "ini", "env", "txt",
    "rs", "py", "go", "java", "kt", "kts", "rb", "php", "cs", "swift", "c", "h",
    "cpp", "hpp", "sh", "bash", "zsh", "sql", "graphql", "gql", "prisma", "proto",
    "lock", "sum", "mod", "xml", "csv", "dockerfile", "tf", "hcl",
}
PATH = re.compile(r"^(?:[\w.-]+/)*[\w.-]+\.([A-Za-z]\w{0,10})$")
MAX_WORDS = 25
MAX_TOP = 6
MAX_BULLETS = 10
MAX_BODY_WORDS = 180
MAX_LABEL_WORDS = {"Why": 80, "Approach": 100, "Review": 60}


def words(text):
    if text.count("`") % 2:
        return len(text.split())
    return len(CODE.sub("x", text).split())


def path_like(token):
    if token.startswith("@") or "://" in token or " " in token or "<" in token:
        return False
    m = PATH.match(token)
    return bool(m) and m.group(1).lower() in EXTENSIONS


def in_diff(token, files):
    if token in files:
        return True
    base = token.rsplit("/", 1)[-1]
    return any(f == token or f.endswith("/" + token) or f.rsplit("/", 1)[-1] == base for f in files)


def lint(lines, files=None):
    problems = []
    fenced = False
    label = None  # (name, heading line)
    seen = []  # labels in order, with their line numbers
    counts = {name: 0 for name in LABELS}  # words per label section
    top = total = body_words = 0
    preceded = False  # text other than a ticket line appeared before **Why.**
    review_para = False  # inside the Review paragraph itself
    review_done = False  # the Review paragraph has ended
    review_end = None  # line of the first text after the Review paragraph
    test_claims = []

    for n, line in enumerate(lines, 1):
        for ch, message in CHARS.items():
            if ch in line:
                problems.append((n, message))
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        stripped = line.strip()
        if not stripped:
            if review_para:
                review_para, review_done = False, True
            continue
        if review_done and review_end is None:
            review_end = n

        m = LABEL.match(stripped)
        if m:
            name, rest = m.group(1), m.group(2).strip()
            if name not in LABELS:
                problems.append((n, f"unknown label **{name}.**: use Why, Approach, or Review"))
                label = None
            else:
                if not rest:
                    problems.append((n, f"**{name}.** stands alone: attach it to a sentence"))
                if name in dict(seen):
                    problems.append((n, f"**{name}.** appears twice: merge the paragraphs"))
                seen.append((name, n))
                label = (name, n)
                review_para = name == "Review"
                if name == "Why" and preceded:
                    problems.append((n, "**Why.** must come first: only the ticket line may precede it"))
                if name == "Why" and rest and OPENERS.match(rest):
                    problems.append((n, "Why opens with the change, not the problem: start with what was wrong"))
            preceded = True
            text_for_count = rest
        elif line.startswith(("## ", "### ")):
            label = None
            preceded = True
            text_for_count = None
        else:
            text_for_count = stripped
            if not TICKET.match(stripped):
                preceded = True

        for am in ASSERTIONS.finditer(stripped):
            problems.append((n, f'assertion without evidence "{am.group(0)}": show the before and after, or cut'))
        for sm in SELF_GRADING.finditer(stripped):
            problems.append((n, f'self-grading word "{sm.group(1)}": cut it or say what it means'))
        if files is not None:
            for token in CODE.findall(stripped):
                if path_like(token) and not in_diff(token, files):
                    problems.append((n, f"`{token}` is not in the diff: fix the name or drop the claim"))
            if TEST_CLAIM.search(stripped):
                test_claims.append(n)

        b = BULLET.match(line)
        if b:
            indent, text = b.groups()
            total += 1
            top += not indent
            if text.count("->") >= 3:
                problems.append((n, "3+ version arrows on one bullet: split into a sub-list"))
            if words(text) > MAX_WORDS:
                problems.append((n, f"bullet over {MAX_WORDS} words: say what changed, not how"))
            if text.count(";") > 1:
                problems.append((n, "more than one semicolon in a bullet: split it or cut a clause"))
            if label and label[0] != "Approach":
                counts[label[0]] += words(text)
            if label:
                body_words += words(text)
        elif label and text_for_count is not None:
            w = words(text_for_count)
            counts[label[0]] += w
            body_words += w

    if not seen:
        return sorted(problems)

    for name, at in seen:
        limit = MAX_LABEL_WORDS[name]
        what = "prose " if name == "Approach" else ""
        if counts[name] > limit:
            problems.append((at, f"{name} runs {counts[name]} {what}words: keep it to {limit} or fewer"))
    if "Why" not in dict(seen):
        problems.append((seen[0][1], "no **Why.** paragraph: the body needs the problem first"))
    if "Review" in dict(seen) and review_end is not None:
        problems.append((review_end, "text after **Review.**: the Review paragraph closes the body"))
    first_label_line = seen[0][1]
    if top > MAX_TOP:
        problems.append((first_label_line, f"{top} top-level bullets: group to {MAX_TOP} or fewer"))
    if total > MAX_BULLETS:
        problems.append((first_label_line, f"{total} bullets: keep it to {MAX_BULLETS} or fewer"))
    if body_words > MAX_BODY_WORDS:
        problems.append((first_label_line, f"body runs {body_words} words: keep it to {MAX_BODY_WORDS} or fewer"))
    if files is not None and test_claims and not any(TEST_FILE.search(f) for f in files):
        for n in test_claims:
            problems.append((n, "claims a test change, but no test file is in the diff"))
    return sorted(problems)


def read_lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    path, files = argv[0], None
    rest = argv[1:]
    if rest == ["--files"] or len(rest) not in (0, 2) or (rest and rest[0] != "--files"):
        print(USAGE)
        return 2
    try:
        lines = read_lines(path)
        if rest:
            files = [f.strip() for f in read_lines(rest[1]) if f.strip()]
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: can't read: {e}", file=sys.stderr)
        return 2
    problems = lint(lines, files)
    for n, message in problems:
        print(f"{path}:{n}: {message}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
