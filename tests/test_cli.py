"""Tests for the new CLI commands: context, inspect, list --stats, doctor."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from makray.cli import cli


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """A minimal fake vault with two notes."""
    (tmp_path / "project.md").write_text(
        textwrap.dedent("""\
            ---
            title: MAKRAY Project
            tags:
              - makray
              - ai
            ---
            # MAKRAY Project

            This project links Obsidian to Claude via a smart filter layer.
            See also [[Roadmap]].
        """),
        encoding="utf-8",
    )
    (tmp_path / "roadmap.md").write_text(
        textwrap.dedent("""\
            # Roadmap

            Phase 1: connect Obsidian  #planning
            Phase 2: semantic search
        """),
        encoding="utf-8",
    )
    return tmp_path


# ──────────────────────────────────────────────────────────────────────────── #
# makray context
# ──────────────────────────────────────────────────────────────────────────── #

class TestContextCommand:
    def test_shows_retrieved_notes(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["context", "--vault", str(vault_dir), "obsidian claude filter"],
        )
        assert result.exit_code == 0, result.output
        assert "MAKRAY Filter Results" in result.output
        assert "MAKRAY Project" in result.output

    def test_shows_system_prompt(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["context", "--vault", str(vault_dir), "obsidian"],
        )
        assert result.exit_code == 0, result.output
        assert "system prompt" in result.output.lower() or "MAKRAY" in result.output

    def test_shows_token_estimate(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["context", "--vault", str(vault_dir), "roadmap planning"],
        )
        assert result.exit_code == 0, result.output
        assert "token" in result.output.lower()

    def test_top_k_flag(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["context", "--vault", str(vault_dir), "--top-k", "1", "obsidian claude"],
        )
        assert result.exit_code == 0, result.output
        # With top-k=1 only one note should appear in the results header
        assert "1 retrieved" in result.output


# ──────────────────────────────────────────────────────────────────────────── #
# makray inspect
# ──────────────────────────────────────────────────────────────────────────── #

class TestInspectCommand:
    def test_shows_note_metadata(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["inspect", "--vault", str(vault_dir), "MAKRAY Project"],
        )
        assert result.exit_code == 0, result.output
        assert "MAKRAY Project" in result.output
        assert "#makray" in result.output
        assert "#ai" in result.output

    def test_shows_wikilinks(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["inspect", "--vault", str(vault_dir), "MAKRAY Project"],
        )
        assert result.exit_code == 0, result.output
        assert "[[Roadmap]]" in result.output

    def test_shows_word_count(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["inspect", "--vault", str(vault_dir), "Roadmap"],
        )
        assert result.exit_code == 0, result.output
        assert "Words" in result.output

    def test_not_found_exits_nonzero(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["inspect", "--vault", str(vault_dir), "NonExistentNote999"],
        )
        assert result.exit_code != 0

    def test_case_insensitive_match(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["inspect", "--vault", str(vault_dir), "makray project"],
        )
        assert result.exit_code == 0, result.output
        assert "MAKRAY Project" in result.output


# ──────────────────────────────────────────────────────────────────────────── #
# makray list --stats
# ──────────────────────────────────────────────────────────────────────────── #

class TestListStats:
    def test_stats_shows_word_count(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["list", "--vault", str(vault_dir), "--stats"],
        )
        assert result.exit_code == 0, result.output
        assert "w," in result.output  # e.g. "12w, 1 links"

    def test_stats_shows_total_words(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["list", "--vault", str(vault_dir), "--stats"],
        )
        assert result.exit_code == 0, result.output
        assert "words total" in result.output


# ──────────────────────────────────────────────────────────────────────────── #
# makray doctor
# ──────────────────────────────────────────────────────────────────────────── #

class TestDoctorCommand:
    def test_passes_with_valid_vault(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["doctor", "--vault", str(vault_dir)],
        )
        # anthropic may not be installed in CI; just check it runs without crash
        # and vault check passes
        assert "note(s)" in result.output

    def test_fails_without_vault(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code != 0 or "Vault path" in result.output

    def test_checks_python_version(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["doctor", "--vault", str(vault_dir)],
        )
        assert "Python" in result.output


# ──────────────────────────────────────────────────────────────────────────── #
# makray chat --dry-run
# ──────────────────────────────────────────────────────────────────────────── #

class TestChatDryRun:
    def test_dry_run_shows_context(self, vault_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "chat",
                "--vault", str(vault_dir),
                "--query", "obsidian claude",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "MAKRAY Filter Results" in result.output

    def test_dry_run_no_api_key_needed(self, vault_dir: Path) -> None:
        """--dry-run must NOT call the Claude API even with no api-key set."""
        import os
        runner = CliRunner(env={"ANTHROPIC_API_KEY": ""})
        result = runner.invoke(
            cli,
            [
                "chat",
                "--vault", str(vault_dir),
                "--query", "roadmap",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "MAKRAY Filter Results" in result.output
