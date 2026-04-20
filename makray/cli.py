"""MAKRAY command-line interface.

Usage examples
--------------
Interactive chat with vault context::

    makray chat --vault ~/my-vault

One-shot query (non-interactive)::

    makray chat --vault ~/my-vault --query "What is my project roadmap?"

Search the vault without calling Claude::

    makray search --vault ~/my-vault "obsidian claude integration"

List all notes in the vault::

    makray list --vault ~/my-vault
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import click
except ImportError:
    print(
        "click is required for the CLI. Install it with: pip install click",
        file=sys.stderr,
    )
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────── #
# Shared option helpers
# ──────────────────────────────────────────────────────────────────────────── #

_vault_option = click.option(
    "--vault",
    "-v",
    envvar="MAKRAY_VAULT",
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Path to the Obsidian vault directory (or set MAKRAY_VAULT).",
)

_api_key_option = click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key (or set ANTHROPIC_API_KEY).",
)

_model_option = click.option(
    "--model",
    default="claude-3-5-sonnet-20241022",
    show_default=True,
    help="Claude model to use.",
)

_top_k_option = click.option(
    "--top-k",
    default=8,
    show_default=True,
    type=int,
    help="Max notes retrieved from the vault per query.",
)

_max_tokens_option = click.option(
    "--max-tokens",
    default=4000,
    show_default=True,
    type=int,
    help="Token budget for Obsidian context injected into each request.",
)


# ──────────────────────────────────────────────────────────────────────────── #
# CLI group
# ──────────────────────────────────────────────────────────────────────────── #

@click.group()
@click.version_option(package_name="makray")
def cli() -> None:
    """MAKRAY — Operational Intelligent System Navigator.

    Bridge your Obsidian vault to Claude with intelligent context filtering.
    """


# ──────────────────────────────────────────────────────────────────────────── #
# makray chat
# ──────────────────────────────────────────────────────────────────────────── #

@cli.command()
@_vault_option
@_api_key_option
@_model_option
@_top_k_option
@_max_tokens_option
@click.option(
    "--query",
    "-q",
    default=None,
    help="One-shot query (skips interactive loop).",
)
@click.option(
    "--stream/--no-stream",
    default=True,
    show_default=True,
    help="Stream Claude responses token-by-token.",
)
def chat(
    vault: str,
    api_key: str | None,
    model: str,
    top_k: int,
    max_tokens: int,
    query: str | None,
    stream: bool,
) -> None:
    """Start an interactive chat session grounded in your Obsidian vault."""
    from makray.claude import ClaudeClient

    try:
        client = ClaudeClient(
            vault,
            api_key=api_key,
            model=model,
            max_context_tokens=max_tokens,
            top_k=top_k,
        )
    except (ImportError, ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(
        click.style(
            f"⚡ MAKRAY connected to vault: {vault}", fg="cyan", bold=True
        )
    )
    click.echo(
        click.style(f"   Model : {model}", fg="cyan")
    )
    click.echo(
        click.style(
            "   Type your question, or 'exit' / Ctrl-C to quit.\n", fg="cyan"
        )
    )

    if query:
        _handle_query(client, query, stream)
        return

    # Interactive loop
    while True:
        try:
            user_input = click.prompt(
                click.style("You", fg="green", bold=True), prompt_suffix=" › "
            )
        except (click.Abort, EOFError):
            click.echo("\nGoodbye!")
            break

        if user_input.strip().lower() in {"exit", "quit", "q"}:
            click.echo("Goodbye!")
            break

        if not user_input.strip():
            continue

        _handle_query(client, user_input, stream)


def _handle_query(client: "ClaudeClient", query: str, stream: bool) -> None:
    click.echo(click.style("\nMAKRAY › ", fg="yellow", bold=True), nl=False)
    try:
        reply = client.chat(query, stream=stream)
        if not stream:
            click.echo(reply)
    except Exception as exc:
        click.echo(
            click.style(f"Claude API error: {exc}", fg="red"), err=True
        )
    click.echo()


# ──────────────────────────────────────────────────────────────────────────── #
# makray search
# ──────────────────────────────────────────────────────────────────────────── #

@cli.command()
@_vault_option
@click.argument("query")
@click.option(
    "--limit",
    "-n",
    default=10,
    show_default=True,
    type=int,
    help="Maximum results to show.",
)
@click.option(
    "--tag",
    "-t",
    multiple=True,
    help="Filter by tag (can be repeated).",
)
def search(vault: str, query: str, limit: int, tag: tuple[str, ...]) -> None:
    """Search your Obsidian vault for notes matching QUERY."""
    from makray.obsidian import ObsidianVault

    try:
        v = ObsidianVault(vault)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    tags = list(tag) if tag else None
    results = v.search(query, tags=tags, limit=limit)

    if not results:
        click.echo("No matching notes found.")
        return

    click.echo(
        click.style(
            f"Found {len(results)} note(s) for query: {query!r}\n",
            fg="cyan",
        )
    )
    for i, note in enumerate(results, 1):
        rel = str(note.path.relative_to(v.vault_path))
        tags_str = (
            "  " + " ".join(f"#{t}" for t in note.tags) if note.tags else ""
        )
        click.echo(
            click.style(f"  [{i}] ", fg="yellow")
            + click.style(note.title, bold=True)
            + click.style(f"  ({rel})", fg="bright_black")
            + click.style(tags_str, fg="cyan")
        )
        excerpt = note.body.strip()[:120].replace("\n", " ")
        click.echo(f"       {excerpt}…\n")


# ──────────────────────────────────────────────────────────────────────────── #
# makray list
# ──────────────────────────────────────────────────────────────────────────── #

@cli.command("list")
@_vault_option
@click.option(
    "--tag",
    "-t",
    multiple=True,
    help="Filter by tag (can be repeated).",
)
def list_notes(vault: str, tag: tuple[str, ...]) -> None:
    """List all notes in the Obsidian vault."""
    from makray.obsidian import ObsidianVault

    try:
        v = ObsidianVault(vault)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    tags = list(tag) if tag else None
    count = 0
    for note in v.iter_notes():
        if tags and not all(
            any(t.lower() in nt.lower() for nt in note.tags) for t in tags
        ):
            continue
        rel = str(note.path.relative_to(v.vault_path))
        tags_str = (
            "  " + " ".join(f"#{t}" for t in note.tags) if note.tags else ""
        )
        click.echo(
            click.style(note.title, bold=True)
            + click.style(f"  ({rel})", fg="bright_black")
            + click.style(tags_str, fg="cyan")
        )
        count += 1

    click.echo(click.style(f"\n{count} note(s) total.", fg="cyan"))


# ──────────────────────────────────────────────────────────────────────────── #
# Entry-point
# ──────────────────────────────────────────────────────────────────────────── #

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
