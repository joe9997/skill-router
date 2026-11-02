#!/usr/bin/env python3
"""Scan installed agent skills and emit a routing catalog.

The scanner exists for runtimes that do not surface skill descriptions in
context. It is deliberately dumb: it parses frontmatter and reports what is on
disk. Ranking is lexical overlap -- a hint for ordering, never a routing
decision.

Usage:
    python scripts/scan_skills.py
    python scripts/scan_skills.py --query "make a pptx deck" --format table
    python scripts/scan_skills.py --path ./my-skills --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", re.DOTALL)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
CJK_RE = re.compile(r"[一-鿿]+")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#._-]*")
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "be", "this", "that", "it", "as", "at", "by", "from",
    "use", "using", "when", "how", "what", "which", "you", "your", "we",
}


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace("\\n", "\n")
        return inner.replace("''", "'")
    return value


def parse_frontmatter(text: str) -> dict:
    """Parse the small YAML subset skills actually use.

    Full YAML would mean a dependency; skills only need scalars, quoted
    scalars, and | / > blocks, so that is what this handles.
    """
    match = FRONTMATTER_RE.match(text.lstrip("﻿"))
    if not match:
        return {}

    data: dict = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Continuation lines are consumed by the block-scalar branch below.
        if line[:1].isspace():
            continue

        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()

        if value in ("|", ">", "|-", ">-", "|+", ">+"):
            block = []
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() and not candidate[:1].isspace():
                    break
                block.append(candidate.strip())
                index += 1
            joiner = "\n" if value.startswith("|") else " "
            data[key] = joiner.join(part for part in block if part)
        else:
            data[key] = _unquote(value)

    return data


def default_roots() -> list[Path]:
    roots: list[Path] = []

    for variable in ("CHERRY_STUDIO_SKILLS_DIR", "CLAUDE_SKILLS_DIR", "AGENT_SKILLS_DIR"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value))

    roots.extend(
        [
            Path.cwd() / ".claude" / "skills",
            Path.cwd() / "skills",
            Path.home() / ".claude" / "skills",
            Path.home() / ".config" / "claude" / "skills",
            Path.home() / ".agents" / "skills",
        ]
    )
    return roots


def unique_roots(roots: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result = []
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_dir():
            result.append(resolved)
    return result


def discover_skills(root: Path, max_depth: int) -> list[Path]:
    """Return directories containing a SKILL.md, within max_depth of root."""
    found: list[Path] = []
    root_depth = len(root.parts)

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [
            name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".cache")
        ]
        if len(current.parts) - root_depth >= max_depth:
            dirnames[:] = []
        if "SKILL.md" in filenames:
            found.append(current)
            dirnames[:] = []  # a skill does not contain nested skills

    return found


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = [word for word in WORD_RE.findall(lowered) if word not in STOPWORDS and len(word) > 1]
    for run in CJK_RE.findall(lowered):
        tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def lexical_score(query: str, name: str, description: str) -> int:
    """Crude overlap score. Ordering hint only -- not a routing decision."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0

    name_lower = name.lower()
    description_lower = description.lower()
    score = 0
    for token in set(query_tokens):
        if token in name_lower:
            score += 3
        if token in description_lower:
            score += 1

    # Reward a contiguous phrase match: it is much stronger evidence than
    # scattered tokens that happen to co-occur.
    query_lower = query.lower().strip()
    if len(query_lower) > 3 and query_lower in description_lower:
        score += 8

    return score


def load_catalog(roots: list[Path], max_depth: int) -> tuple[list[dict], list[str]]:
    skills: list[dict] = []
    warnings: list[str] = []
    seen: dict[str, dict] = {}

    for root in roots:
        for skill_dir in discover_skills(root, max_depth):
            skill_file = skill_dir / "SKILL.md"
            try:
                text = skill_file.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                warnings.append(f"unreadable: {skill_file} ({error})")
                continue

            meta = parse_frontmatter(text)
            name = (meta.get("name") or "").strip()
            description = (meta.get("description") or "").strip()

            if not name:
                warnings.append(f"missing name: {skill_file}")
                continue
            if name != skill_dir.name:
                warnings.append(f"name/dir mismatch: {name!r} in {skill_dir.name!r}")
            if not description:
                warnings.append(f"missing description: {skill_file}")

            entry = {
                "name": name,
                "description": description,
                "path": str(skill_file),
                "root": str(root),
                "modified": int(skill_file.stat().st_mtime),
            }

            # First root wins: roots are ordered by authority, so an explicit
            # --path beats a user-level install with the same skill name.
            if name in seen:
                warnings.append(f"duplicate name ignored: {name} at {skill_file}")
                continue
            seen[name] = entry
            skills.append(entry)

    skills.sort(key=lambda item: item["name"].lower())
    return skills, warnings


def render_table(skills: list[dict], query: str | None) -> str:
    headers = ["NAME", "SCORE", "DESCRIPTION", "PATH"] if query else ["NAME", "DESCRIPTION", "PATH"]
    rows = []
    for skill in skills:
        description = " ".join(skill["description"].split())
        if len(description) > 70:
            description = description[:67] + "..."
        if query:
            rows.append([skill["name"], str(skill.get("score", 0)), description, skill["path"]])
        else:
            rows.append([skill["name"], description, skill["path"]])

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    output = [line(headers), line(["-" * width for width in widths])]
    output.extend(line(row) for row in rows)
    return "\n".join(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan installed agent skills.")
    parser.add_argument("--path", action="append", default=[], help="extra skill root (repeatable)")
    parser.add_argument("--query", default=None, help="rank skills against this text")
    parser.add_argument("--format", choices=("json", "table"), default="json")
    parser.add_argument("--max-depth", type=int, default=3, help="directory depth to search")
    parser.add_argument(
        "--no-defaults", action="store_true", help="scan only --path roots, ignoring standard locations"
    )
    parser.add_argument("--strict", action="store_true", help="exit 1 if any warning was emitted")
    args = parser.parse_args(argv)

    roots = [Path(path) for path in args.path]
    if not args.no_defaults:
        roots += default_roots()
    roots = unique_roots(roots)
    if not roots:
        print("No skill roots found. Pass --path DIR.", file=sys.stderr)
        return 2

    skills, warnings = load_catalog(roots, args.max_depth)

    if args.query:
        for skill in skills:
            skill["score"] = lexical_score(args.query, skill["name"], skill["description"])
        skills.sort(key=lambda item: (-item["score"], item["name"].lower()))

    if args.format == "table":
        print(render_table(skills, args.query))
    else:
        print(
            json.dumps(
                {"roots": [str(root) for root in roots], "skills": skills, "warnings": warnings},
                ensure_ascii=False,
                indent=2,
            )
        )

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
