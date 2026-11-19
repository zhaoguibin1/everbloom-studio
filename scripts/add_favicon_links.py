#!/usr/bin/env python3
"""Insert the site's three favicon <link> tags into every HTML page.

The tags use root-absolute hrefs:

    <link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="apple-touch-icon" href="/apple-touch-icon.png" />

Running the script again does not add duplicates. Existing icon links
(including relative hrefs, shortcut icons, and repeats) are removed and
replaced by this set. A page that already has exactly these three tags
is left byte-for-byte unchanged.

Usage:
    python3 scripts/add_favicon_links.py [ROOT]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CANONICAL = (
    '<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48" />',
    '<link rel="icon" href="/favicon.svg" type="image/svg+xml" />',
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png" />',
)

LINK_RE = re.compile(r"<link\b[^>]*?>", re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(
    r"""([:\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""",
    re.IGNORECASE,
)
VIEWPORT_RE = re.compile(
    r"""^[ \t]*<meta\b[^>]*\bname=["']viewport["'][^>]*>[ \t]*\r?\n""",
    re.IGNORECASE | re.MULTILINE,
)
HEAD_CLOSE_RE = re.compile(r"^[ \t]*</head>[ \t]*\r?\n?", re.IGNORECASE | re.MULTILINE)
INDENT_RE = re.compile(r"^([ \t]*)<meta\b", re.MULTILINE)

ICON_RELS = frozenset(
    {"icon", "apple-touch-icon", "apple-touch-icon-precomposed", "mask-icon"}
)


def parse_attrs(tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(tag):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        attrs[match.group(1).lower()] = value
    return attrs


def is_icon_tag(tag: str) -> bool:
    rel = parse_attrs(tag).get("rel", "").lower().split()
    return any(token in ICON_RELS for token in rel)


def icon_tags(text: str) -> list[str]:
    return [match.group(0) for match in LINK_RE.finditer(text) if is_icon_tag(match.group(0))]


def already_good(text: str) -> bool:
    return [tag.strip() for tag in icon_tags(text)] == list(CANONICAL)


def remove_icon_tags(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return "" if is_icon_tag(match.group(0)) else match.group(0)

    stripped = LINK_RE.sub(repl, text)
    kept: list[str] = []
    for line in stripped.splitlines(keepends=True):
        core = line.strip("\r\n")
        # Drop the indent left behind when a whole-line icon tag was removed.
        # Real blank lines in these files are empty, not space-only.
        if core != "" and core.strip() == "":
            continue
        kept.append(line)
    return "".join(kept)


def insert_icons(text: str) -> str:
    indent_match = INDENT_RE.search(text)
    indent = indent_match.group(1) if indent_match else "    "
    newline = "\r\n" if "\r\n" in text else "\n"
    block = "".join(f"{indent}{tag}{newline}" for tag in CANONICAL)
    viewport = VIEWPORT_RE.search(text)
    if viewport:
        at = viewport.end()
        return text[:at] + block + text[at:]
    head = HEAD_CLOSE_RE.search(text)
    if not head:
        raise ValueError("no <meta name=\"viewport\"> or </head> found")
    return text[: head.start()] + block + text[head.start() :]


def process(text: str) -> tuple[str, str]:
    if already_good(text):
        return text, "unchanged"
    updated = insert_icons(remove_icon_tags(text))
    if not already_good(updated):
        raise RuntimeError("favicon tags were not in the canonical form after editing")
    return updated, "updated"


def html_files(root: Path) -> list[Path]:
    files = [
        path
        for path in root.rglob("*.html")
        if ".git" not in path.parts and path.is_file()
    ]
    return sorted(files, key=lambda path: path.as_posix())


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parents[1]
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1
    pages = html_files(root)
    if not pages:
        print(f"No HTML files under {root}", file=sys.stderr)
        return 1
    updated = 0
    unchanged = 0
    for path in pages:
        original = path.read_text(encoding="utf-8")
        try:
            new_text, status = process(original)
        except (ValueError, RuntimeError) as exc:
            print(f"{path.relative_to(root).as_posix()}: error: {exc}", file=sys.stderr)
            return 1
        rel = path.relative_to(root).as_posix()
        if status == "updated" and new_text != original:
            path.write_text(new_text, encoding="utf-8")
            updated += 1
            print(f"{rel}: updated")
        else:
            unchanged += 1
            print(f"{rel}: unchanged")
    print(f"{updated} updated, {unchanged} unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
