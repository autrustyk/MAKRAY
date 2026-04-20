"""Obsidian note model."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
_TAG_INLINE_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_/-]*)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class ObsidianNote:
    """Represents a single Obsidian markdown note."""

    path: Path
    raw: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    @classmethod
    def from_path(cls, path: Path) -> "ObsidianNote":
        """Read and parse a note from *path*."""
        raw = path.read_text(encoding="utf-8")
        note = cls(path=path, raw=raw)
        note._parse()
        return note

    # ------------------------------------------------------------------ #
    def _parse(self) -> None:
        """Extract frontmatter, tags, wiki-links and headings."""
        try:
            import yaml  # soft dependency
        except ImportError:
            yaml = None  # type: ignore[assignment]

        text = self.raw
        fm_match = _FRONTMATTER_RE.match(text)
        if fm_match and yaml:
            try:
                self.frontmatter = yaml.safe_load(fm_match.group(1)) or {}
            except Exception:
                self.frontmatter = {}
            self.body = text[fm_match.end():]
        else:
            self.body = text

        # Frontmatter tags (list or space-separated string)
        fm_tags = self.frontmatter.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = fm_tags.split()
        self.tags = [str(t).lstrip("#") for t in fm_tags]

        # Inline #tags
        for match in _TAG_INLINE_RE.finditer(self.body):
            tag = match.group(1)
            if tag not in self.tags:
                self.tags.append(tag)

        # [[Wiki-links]]
        self.links = list(dict.fromkeys(_WIKILINK_RE.findall(self.body)))

        # Headings
        self.headings = [
            m.group(2).strip() for m in _HEADING_RE.finditer(self.body)
        ]

    # ------------------------------------------------------------------ #
    @property
    def title(self) -> str:
        """Return the note title (frontmatter > first heading > filename)."""
        if self.frontmatter.get("title"):
            return str(self.frontmatter["title"])
        if self.headings:
            return self.headings[0]
        return self.path.stem

    @property
    def word_count(self) -> int:
        return len(self.body.split())

    def __repr__(self) -> str:
        return f"<ObsidianNote title={self.title!r} tags={self.tags}>"
