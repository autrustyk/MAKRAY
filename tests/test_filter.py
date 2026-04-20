"""Tests for the MAKRAY filter layer."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from makray.filter import MAKRAYFilter
from makray.obsidian.vault import ObsidianVault


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    (tmp_path / "ai.md").write_text(
        textwrap.dedent("""\
            ---
            tags: [ai, machine-learning]
            ---
            # Artificial Intelligence

            AI is transforming every industry.
            Deep learning models like Claude can reason about complex topics.
        """),
        encoding="utf-8",
    )
    (tmp_path / "obsidian.md").write_text(
        textwrap.dedent("""\
            # Obsidian

            Obsidian is a powerful knowledge management tool.
            It stores notes as plain markdown files in a local vault.
            Tags: #pkm #notes
        """),
        encoding="utf-8",
    )
    (tmp_path / "unrelated.md").write_text(
        "Cooking recipe for pasta carbonara.", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def vault(vault_dir: Path) -> ObsidianVault:
    return ObsidianVault(vault_dir)


@pytest.fixture()
def makray_filter(vault: ObsidianVault) -> MAKRAYFilter:
    return MAKRAYFilter(vault, max_context_tokens=2000, top_k=5, excerpt_chars=200)


class TestMAKRAYFilter:
    def test_build_context_returns_notes(self, makray_filter: MAKRAYFilter) -> None:
        ctx = makray_filter.build_context("artificial intelligence claude")
        assert len(ctx.notes) > 0
        titles = [n.title for n in ctx.notes]
        assert "Artificial Intelligence" in titles

    def test_system_prompt_contains_header(self, makray_filter: MAKRAYFilter) -> None:
        ctx = makray_filter.build_context("obsidian notes")
        assert "MAKRAY" in ctx.system_prompt

    def test_system_prompt_contains_note_title(
        self, makray_filter: MAKRAYFilter
    ) -> None:
        ctx = makray_filter.build_context("obsidian notes vault")
        assert "Obsidian" in ctx.system_prompt

    def test_no_match_produces_fallback(self, vault: ObsidianVault) -> None:
        # Build a filter with an empty vault to guarantee no matches
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            empty_vault = ObsidianVault(d)
            f = MAKRAYFilter(empty_vault)
            ctx = f.build_context("some query")
        assert "No directly relevant notes" in ctx.system_prompt

    def test_token_estimate_positive(self, makray_filter: MAKRAYFilter) -> None:
        ctx = makray_filter.build_context("ai")
        assert ctx.token_estimate > 0

    def test_token_budget_respected(self, vault: ObsidianVault) -> None:
        # Very small budget — should trim aggressively
        f = MAKRAYFilter(vault, max_context_tokens=10, top_k=5, excerpt_chars=50)
        ctx = f.build_context("ai obsidian notes")
        # token_estimate should stay near the ceiling (rough check)
        assert ctx.token_estimate < 500  # well within 10-token * 4 chars + overhead

    def test_custom_system_header(self, vault: ObsidianVault) -> None:
        custom_header = "Custom test header."
        f = MAKRAYFilter(vault, system_header=custom_header)
        ctx = f.build_context("ai")
        assert custom_header in ctx.system_prompt

    def test_query_stored(self, makray_filter: MAKRAYFilter) -> None:
        query = "machine learning notes"
        ctx = makray_filter.build_context(query)
        assert ctx.query == query
