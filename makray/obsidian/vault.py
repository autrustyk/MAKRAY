"""Obsidian vault reader."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterator

from .note import ObsidianNote


class ObsidianVault:
    """Read and index an Obsidian vault directory.

    Parameters
    ----------
    vault_path:
        Absolute or relative path to the root of the Obsidian vault.
    exclude_patterns:
        List of glob patterns for directories or files to skip (e.g.
        ``[".obsidian", "templates/*"]``).
    """

    def __init__(
        self,
        vault_path: str | Path,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        self.vault_path = Path(vault_path).expanduser().resolve()
        if not self.vault_path.is_dir():
            raise FileNotFoundError(
                f"Vault directory not found: {self.vault_path}"
            )
        self.exclude_patterns: list[str] = exclude_patterns or [
            ".obsidian",
            ".trash",
            "*.excalidraw.md",
        ]
        self._notes: dict[str, ObsidianNote] | None = None

    # ------------------------------------------------------------------ #
    def _is_excluded(self, path: Path) -> bool:
        rel = str(path.relative_to(self.vault_path))
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(
                path.name, pattern
            ):
                return True
            # Match any path component against the pattern
            for part in path.parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    # ------------------------------------------------------------------ #
    def iter_notes(self) -> Iterator[ObsidianNote]:
        """Yield every markdown note in the vault."""
        for root, dirs, files in os.walk(self.vault_path):
            root_path = Path(root)
            # Prune excluded directories in-place so os.walk skips them
            dirs[:] = [
                d
                for d in dirs
                if not self._is_excluded(root_path / d)
            ]
            for filename in sorted(files):
                if not filename.endswith(".md"):
                    continue
                file_path = root_path / filename
                if self._is_excluded(file_path):
                    continue
                try:
                    yield ObsidianNote.from_path(file_path)
                except Exception:
                    # Skip unreadable notes silently
                    continue

    # ------------------------------------------------------------------ #
    def load_all(self, force: bool = False) -> dict[str, ObsidianNote]:
        """Load and cache all notes, keyed by their title."""
        if self._notes is not None and not force:
            return self._notes
        self._notes = {}
        for note in self.iter_notes():
            self._notes[note.title] = note
        return self._notes

    # ------------------------------------------------------------------ #
    def search(
        self,
        query: str,
        *,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[ObsidianNote]:
        """Simple keyword + tag search across all notes.

        Parameters
        ----------
        query:
            Free-text search string.  Each whitespace-separated token must
            appear in the note title, body, or tags (case-insensitive).
        tags:
            Optional additional tag filter — all listed tags must be present.
        limit:
            Maximum number of results to return.
        """
        tokens = query.lower().split() if query else []
        results: list[tuple[int, ObsidianNote]] = []

        for note in self.iter_notes():
            haystack = (
                note.title.lower()
                + " "
                + note.body.lower()
                + " "
                + " ".join(note.tags).lower()
            )
            score = sum(1 for t in tokens if t in haystack)
            if tokens and score == 0:
                continue
            if tags and not all(
                any(t.lower() in nt.lower() for nt in note.tags)
                for t in tags
            ):
                continue
            results.append((score, note))

        results.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in results[:limit]]
