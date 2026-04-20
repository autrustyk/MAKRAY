"""Tests for ObsidianNote and ObsidianVault."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from makray.obsidian.note import ObsidianNote
from makray.obsidian.vault import ObsidianVault


# ──────────────────────────────────────────────────────────────────────────── #
# Fixtures
# ──────────────────────────────────────────────────────────────────────────── #

@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """Create a minimal fake Obsidian vault."""
    # Note with frontmatter
    (tmp_path / "project.md").write_text(
        textwrap.dedent("""\
            ---
            title: My Project
            tags:
              - makray
              - planning
            ---
            # My Project

            This is the main project note.

            See also [[Ideas]] and [[Roadmap]].
        """),
        encoding="utf-8",
    )
    # Note without frontmatter
    (tmp_path / "Ideas.md").write_text(
        textwrap.dedent("""\
            # Ideas

            - Connect Obsidian to Claude
            - Build a filter layer  #ai #automation
        """),
        encoding="utf-8",
    )
    # Note in a sub-folder
    sub = tmp_path / "archive"
    sub.mkdir()
    (sub / "old-note.md").write_text("Old archived note.", encoding="utf-8")

    # Excluded folder
    obs = tmp_path / ".obsidian"
    obs.mkdir()
    (obs / "config.md").write_text("internal obsidian config", encoding="utf-8")

    return tmp_path


# ──────────────────────────────────────────────────────────────────────────── #
# ObsidianNote tests
# ──────────────────────────────────────────────────────────────────────────── #

class TestObsidianNote:
    def test_title_from_frontmatter(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "project.md")
        assert note.title == "My Project"

    def test_title_from_heading(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "Ideas.md")
        assert note.title == "Ideas"

    def test_title_fallback_to_stem(self, tmp_path: Path) -> None:
        p = tmp_path / "untitled.md"
        p.write_text("no heading here", encoding="utf-8")
        note = ObsidianNote.from_path(p)
        assert note.title == "untitled"

    def test_frontmatter_tags(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "project.md")
        assert "makray" in note.tags
        assert "planning" in note.tags

    def test_inline_tags(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "Ideas.md")
        assert "ai" in note.tags
        assert "automation" in note.tags

    def test_wikilinks(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "project.md")
        assert "Ideas" in note.links
        assert "Roadmap" in note.links

    def test_word_count(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "project.md")
        assert note.word_count > 0

    def test_body_excludes_frontmatter(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "project.md")
        assert "title:" not in note.body
        assert "tags:" not in note.body

    def test_headings(self, vault_dir: Path) -> None:
        note = ObsidianNote.from_path(vault_dir / "project.md")
        assert "My Project" in note.headings


# ──────────────────────────────────────────────────────────────────────────── #
# ObsidianVault tests
# ──────────────────────────────────────────────────────────────────────────── #

class TestObsidianVault:
    def test_iter_notes_yields_md_files(self, vault_dir: Path) -> None:
        vault = ObsidianVault(vault_dir)
        titles = {n.title for n in vault.iter_notes()}
        assert "My Project" in titles
        assert "Ideas" in titles

    def test_excluded_obsidian_folder(self, vault_dir: Path) -> None:
        vault = ObsidianVault(vault_dir)
        paths = [n.path for n in vault.iter_notes()]
        assert not any(".obsidian" in str(p) for p in paths)

    def test_sub_folder_notes_included(self, vault_dir: Path) -> None:
        vault = ObsidianVault(vault_dir)
        titles = {n.title for n in vault.iter_notes()}
        assert "old-note" in titles

    def test_load_all_caches(self, vault_dir: Path) -> None:
        vault = ObsidianVault(vault_dir)
        d1 = vault.load_all()
        d2 = vault.load_all()
        assert d1 is d2

    def test_search_returns_relevant(self, vault_dir: Path) -> None:
        vault = ObsidianVault(vault_dir)
        results = vault.search("obsidian claude filter")
        titles = [n.title for n in results]
        assert "Ideas" in titles

    def test_search_empty_query(self, vault_dir: Path) -> None:
        vault = ObsidianVault(vault_dir)
        results = vault.search("")
        # Empty query returns all notes
        assert len(results) > 0

    def test_search_tag_filter(self, vault_dir: Path) -> None:
        vault = ObsidianVault(vault_dir)
        results = vault.search("", tags=["ai"])
        titles = [n.title for n in results]
        assert "Ideas" in titles
        # project note doesn't have #ai tag
        assert "My Project" not in titles

    def test_nonexistent_vault_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ObsidianVault(tmp_path / "no-such-dir")
