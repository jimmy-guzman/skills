#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Validate every skills/*/SKILL.md against the Agent Skills spec and this repo's rules.

Usage:
  validate_skills.py [--root DIR]

Exit codes:
  0 no errors (warnings allowed)
  1 at least one error
  2 bad arguments or invalid root
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ALLOWED_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
EM_EN_RE = re.compile(r"[–—]")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
TOKEN_RATIO = 3.7

def _rec(records, relpath, line, kind, msg):
    records.append((relpath, line, kind, msg))


def _check_name(name, folder, relpath, records):
    if not isinstance(name, str) or not name:
        _rec(records, relpath, 1, "error", "name is missing or empty")
        return
    if name != folder:
        _rec(records, relpath, 1, "error",
             f"name '{name}' does not match folder '{folder}'")
    if not (1 <= len(name) <= 64):
        _rec(records, relpath, 1, "error",
             f"name length {len(name)} not in 1..64")
    if not NAME_RE.match(name):
        _rec(records, relpath, 1, "error",
             "name must be lowercase letters, digits, and single hyphens")
    low = name.lower()
    if "claude" in low or "anthropic" in low:
        _rec(records, relpath, 1, "error",
             "name may not contain 'claude' or 'anthropic'")


def _check_description(desc, relpath, records):
    if desc is None or desc == "":
        _rec(records, relpath, 1, "error", "description is missing or empty")
        return
    if not isinstance(desc, str):
        _rec(records, relpath, 1, "error", "description must be a string")
        return
    if len(desc) > 1024:
        _rec(records, relpath, 1, "error",
             f"description length {len(desc)} > 1024")


def _check_compatibility(compat, relpath, records):
    if compat is None:
        return
    if not isinstance(compat, str):
        _rec(records, relpath, 1, "error", "compatibility must be a string")
        return
    if len(compat) > 500:
        _rec(records, relpath, 1, "error",
             f"compatibility length {len(compat)} > 500")


def _check_unknown_fields(fm, relpath, records):
    for key in fm:
        if key not in ALLOWED_FIELDS:
            _rec(records, relpath, 1, "error",
                 f"unknown frontmatter field: {key}")


INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
FENCE_RE = re.compile(r"^\s*```")


def _check_links(skill_dir, skill_md_text, body_start_line, relpath, records):
    skill_root = skill_dir.resolve()
    in_fence = False
    for lineno, line in enumerate(skill_md_text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or lineno < body_start_line:
            continue
        stripped = INLINE_CODE_RE.sub("", line)
        for match in LINK_RE.finditer(stripped):
            target = match.group(2).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#") or not target:
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (skill_dir / path_part).resolve()
            try:
                resolved.relative_to(skill_root)
            except ValueError:
                _rec(records, relpath, lineno, "error",
                     f"link target escapes skill folder: {target}")
                continue
            if not resolved.exists():
                _rec(records, relpath, lineno, "error",
                     f"link target does not exist: {target}")


def _check_dashes(skill_dir, folder, records):
    for md_path in sorted(skill_dir.rglob("*.md")):
        rel = f"skills/{folder}/{md_path.relative_to(skill_dir).as_posix()}"
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError as e:
            _rec(records, rel, 1, "error", f"could not read: {e}")
            continue
        in_fence = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if EM_EN_RE.search(line):
                _rec(records, rel, lineno, "warning",
                     "em-dash or en-dash; use ASCII hyphen or rewrite")


def _check_body_size(body_text, relpath, records):
    line_count = body_text.count("\n")
    char_count = len(body_text)
    est_tokens = int(char_count / TOKEN_RATIO)
    if line_count > 500:
        _rec(records, relpath, 1, "warning",
             f"body is {line_count} lines (>500)")
    if est_tokens > 5000:
        _rec(records, relpath, 1, "warning",
             f"body is ~{est_tokens} tokens, est. (chars/{TOKEN_RATIO:.1f}) (>5000)")


def _check_skill(skill_dir, records):
    folder = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    relpath = f"skills/{folder}/SKILL.md"

    if not skill_md.is_file():
        _rec(records, f"skills/{folder}", 1, "error", "SKILL.md is missing")
        return

    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as e:
        _rec(records, relpath, 1, "error", f"could not read: {e}")
        return

    m = FRONTMATTER_RE.match(text)
    if not m:
        _rec(records, relpath, 1, "error",
             "frontmatter missing or malformed (must open with '---' on line 1)")
        _check_dashes(skill_dir, folder, records)
        return

    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        _rec(records, relpath, 1, "error",
             f"frontmatter YAML error: {e}")
        _check_dashes(skill_dir, folder, records)
        return

    if not isinstance(fm, dict):
        _rec(records, relpath, 1, "error",
             "frontmatter must be a YAML mapping")
        _check_dashes(skill_dir, folder, records)
        return

    body_start_line = text[: m.end()].count("\n") + 1
    _check_unknown_fields(fm, relpath, records)
    _check_name(fm.get("name"), folder, relpath, records)
    _check_description(fm.get("description"), relpath, records)
    _check_compatibility(fm.get("compatibility"), relpath, records)
    _check_links(skill_dir, text, body_start_line, relpath, records)
    _check_dashes(skill_dir, folder, records)
    _check_body_size(text[m.end():], relpath, records)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=("Validate every skills/*/SKILL.md against the Agent Skills "
                     "spec and this repo's rules."),
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repo root; defaults to the current working directory",
    )
    args = ap.parse_args(argv)

    skills_dir = (args.root / "skills").resolve()
    if not skills_dir.is_dir():
        print(f"error: {skills_dir} is not a directory", file=sys.stderr)
        return 2

    records = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        _check_skill(skill_dir, records)

    errors = [r for r in records if r[2] == "error"]
    warnings = [r for r in records if r[2] == "warning"]

    for relpath, line, kind, msg in records:
        print(f"{relpath}:{line}: {kind}: {msg}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
