"""MAKRAY command-line interface.

Usage examples
--------------
Interactive chat with vault context::

    makray chat --vault ~/my-vault

One-shot query (non-interactive)::

    makray chat --vault ~/my-vault --query "What is my project roadmap?"

Dry-run (show context that would be sent to Claude, no API call)::

    makray chat --vault ~/my-vault --query "What is my roadmap?" --dry-run

Inspect the MAKRAY filter for a query (no API key needed)::

    makray context --vault ~/my-vault "obsidian claude integration"

Inspect a note's parsed metadata::

    makray inspect --vault ~/my-vault "My Note Title"

Search the vault without calling Claude::

    makray search --vault ~/my-vault "obsidian claude integration"

List all notes in the vault::

    makray list --vault ~/my-vault

Validate the setup::

    makray doctor --vault ~/my-vault
"""

from __future__ import annotations

import sys

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

_excerpt_option = click.option(
    "--excerpt-chars",
    default=600,
    show_default=True,
    type=int,
    help="Max characters taken from each note as an excerpt.",
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
@_excerpt_option
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
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help=(
        "Show the system prompt that would be sent to Claude "
        "(no API call, no API key needed)."
    ),
)
def chat(
    vault: str,
    api_key: str | None,
    model: str,
    top_k: int,
    max_tokens: int,
    excerpt_chars: int,
    query: str | None,
    stream: bool,
    dry_run: bool,
) -> None:
    """Start an interactive chat session grounded in your Obsidian vault."""
    from makray.filter import MAKRAYFilter
    from makray.obsidian import ObsidianVault

    if dry_run:
        # No API key needed — just show what would be sent to Claude.
        try:
            v = ObsidianVault(vault)
        except FileNotFoundError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        fltr = MAKRAYFilter(
            v, max_context_tokens=max_tokens, top_k=top_k, excerpt_chars=excerpt_chars
        )
        q = query or click.prompt(click.style("Query", fg="green", bold=True))
        _print_context(fltr, q, vault)
        return

    from makray.claude import ClaudeClient

    try:
        client = ClaudeClient(
            vault,
            api_key=api_key,
            model=model,
            max_context_tokens=max_tokens,
            top_k=top_k,
            excerpt_chars=excerpt_chars,
        )
    except (ImportError, ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(
        click.style(
            f"⚡ MAKRAY connected to vault: {vault}", fg="cyan", bold=True
        )
    )
    click.echo(click.style(f"   Model : {model}", fg="cyan"))
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
# makray context  (filter inspector — no API key needed)
# ──────────────────────────────────────────────────────────────────────────── #

@cli.command()
@_vault_option
@_top_k_option
@_max_tokens_option
@_excerpt_option
@click.argument("query")
def context(
    vault: str,
    top_k: int,
    max_tokens: int,
    excerpt_chars: int,
    query: str,
) -> None:
    """Show which vault notes MAKRAY would inject into Claude for QUERY.

    Runs the full filter pipeline and prints the assembled system prompt
    without making any API calls.  Use this to tune --top-k, --max-tokens,
    and --excerpt-chars before running a real chat session.
    """
    from makray.filter import MAKRAYFilter
    from makray.obsidian import ObsidianVault

    try:
        v = ObsidianVault(vault)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    fltr = MAKRAYFilter(
        v, max_context_tokens=max_tokens, top_k=top_k, excerpt_chars=excerpt_chars
    )
    _print_context(fltr, query, vault)


def _print_context(fltr: "MAKRAYFilter", query: str, vault_path: str) -> None:
    """Shared helper: print filter results for *query*."""
    from makray.obsidian import ObsidianVault

    ctx = fltr.build_context(query)

    click.echo(
        click.style("⚡ MAKRAY Filter Results", fg="cyan", bold=True)
        + click.style(f"  —  query: {query!r}", fg="cyan")
    )
    click.echo(
        click.style(
            f"   Vault  : {vault_path}", fg="bright_black"
        )
    )
    click.echo(
        click.style(
            f"   Notes  : {len(ctx.notes)} retrieved  |  "
            f"~{ctx.token_estimate} tokens in context",
            fg="bright_black",
        )
    )
    click.echo()

    if ctx.notes:
        click.echo(click.style("── Retrieved notes ─────────────────────", fg="yellow"))
        for i, note in enumerate(ctx.notes, 1):
            v = fltr.vault
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
        click.echo()

    click.echo(click.style("── Assembled system prompt ──────────────", fg="yellow"))
    click.echo(ctx.system_prompt)


# ──────────────────────────────────────────────────────────────────────────── #
# makray inspect
# ──────────────────────────────────────────────────────────────────────────── #

@cli.command()
@_vault_option
@click.argument("note_title")
def inspect(vault: str, note_title: str) -> None:
    """Show parsed metadata for a note matching NOTE_TITLE.

    Displays the frontmatter, tags, wiki-links, headings, and word count
    as MAKRAY sees them — useful for verifying that your notes are indexed
    correctly.
    """
    from makray.obsidian import ObsidianVault

    try:
        v = ObsidianVault(vault)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Case-insensitive prefix/substring match on title
    query_lower = note_title.lower()
    matches = [
        n for n in v.iter_notes()
        if query_lower in n.title.lower()
    ]

    if not matches:
        click.echo(
            click.style(
                f"No note matching {note_title!r} found in vault.", fg="red"
            )
        )
        sys.exit(1)

    if len(matches) > 1:
        click.echo(
            click.style(
                f"{len(matches)} notes match {note_title!r}. Showing the first match.\n",
                fg="yellow",
            )
        )

    note = matches[0]
    rel = str(note.path.relative_to(v.vault_path))

    click.echo(click.style("── Note metadata ────────────────────────", fg="cyan"))
    click.echo(click.style("  Title      : ", fg="bright_black") + click.style(note.title, bold=True))
    click.echo(click.style("  File       : ", fg="bright_black") + rel)
    click.echo(click.style("  Words      : ", fg="bright_black") + str(note.word_count))

    if note.frontmatter:
        click.echo(click.style("  Frontmatter: ", fg="bright_black"))
        for k, val in note.frontmatter.items():
            click.echo(f"    {k}: {val}")

    if note.tags:
        click.echo(
            click.style("  Tags       : ", fg="bright_black")
            + click.style("  ".join(f"#{t}" for t in note.tags), fg="cyan")
        )

    if note.links:
        click.echo(
            click.style("  Links      : ", fg="bright_black")
            + "  ".join(f"[[{l}]]" for l in note.links)
        )

    if note.headings:
        click.echo(click.style("  Headings   : ", fg="bright_black"))
        for h in note.headings:
            click.echo(f"    • {h}")

    click.echo()
    click.echo(click.style("── Body preview (first 400 chars) ───────", fg="cyan"))
    preview = note.body.strip()[:400]
    click.echo(preview)
    if len(note.body.strip()) > 400:
        click.echo(click.style("  … (truncated)", fg="bright_black"))


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
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Show per-note word count and link count.",
)
def list_notes(vault: str, tag: tuple[str, ...], stats: bool) -> None:
    """List all notes in the Obsidian vault."""
    from makray.obsidian import ObsidianVault

    try:
        v = ObsidianVault(vault)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    tags = list(tag) if tag else None
    count = 0
    total_words = 0
    for note in v.iter_notes():
        if tags and not all(
            any(t.lower() in nt.lower() for nt in note.tags) for t in tags
        ):
            continue
        rel = str(note.path.relative_to(v.vault_path))
        tags_str = (
            "  " + " ".join(f"#{t}" for t in note.tags) if note.tags else ""
        )
        line = (
            click.style(note.title, bold=True)
            + click.style(f"  ({rel})", fg="bright_black")
            + click.style(tags_str, fg="cyan")
        )
        if stats:
            line += click.style(
                f"  [{note.word_count}w, {len(note.links)} links]",
                fg="bright_black",
            )
        click.echo(line)
        count += 1
        total_words += note.word_count

    summary = f"\n{count} note(s) total."
    if stats and count:
        summary += f"  {total_words} words total."
    click.echo(click.style(summary, fg="cyan"))


# ──────────────────────────────────────────────────────────────────────────── #
# makray doctor
# ──────────────────────────────────────────────────────────────────────────── #

@cli.command()
@click.option(
    "--vault",
    "-v",
    envvar="MAKRAY_VAULT",
    default=None,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Path to the Obsidian vault directory (or set MAKRAY_VAULT).",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key (or set ANTHROPIC_API_KEY).",
)
def doctor(vault: str | None, api_key: str | None) -> None:
    """Validate the MAKRAY setup and report any issues."""
    import importlib
    import os
    from pathlib import Path

    ok = True

    def _check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        icon = click.style("✓", fg="green") if passed else click.style("✗", fg="red")
        msg = click.style(f"  {icon}  {label}", bold=passed)
        if detail:
            msg += click.style(f"  — {detail}", fg="bright_black")
        click.echo(msg)
        if not passed:
            ok = False

    click.echo(click.style("⚡ MAKRAY doctor", fg="cyan", bold=True) + "\n")

    # 1. Python version
    import sys as _sys
    py_ok = _sys.version_info >= (3, 10)
    _check(
        "Python ≥ 3.10",
        py_ok,
        f"running {_sys.version.split()[0]}",
    )

    # 2. anthropic package
    anthropic_ok = importlib.util.find_spec("anthropic") is not None
    _check(
        "anthropic package installed",
        anthropic_ok,
        "" if anthropic_ok else "run: pip install anthropic",
    )

    # 3. pyyaml package
    yaml_ok = importlib.util.find_spec("yaml") is not None
    _check(
        "pyyaml package installed",
        yaml_ok,
        "" if yaml_ok else "run: pip install pyyaml  (needed for frontmatter parsing)",
    )

    # 4. API key
    effective_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    key_ok = bool(effective_key)
    _check(
        "ANTHROPIC_API_KEY set",
        key_ok,
        "set the environment variable or pass --api-key" if not key_ok else "found",
    )

    # 5. Vault path
    if vault:
        vault_path = Path(vault)
        vault_exists = vault_path.is_dir()
        _check(
            f"Vault exists: {vault}",
            vault_exists,
            "" if vault_exists else "directory not found",
        )
        if vault_exists:
            from makray.obsidian import ObsidianVault
            v = ObsidianVault(vault_path)
            note_count = sum(1 for _ in v.iter_notes())
            _check(
                f"Vault readable ({note_count} note(s) found)",
                note_count >= 0,
                f"{note_count} note(s)",
            )
    else:
        _check("Vault path", False, "pass --vault or set MAKRAY_VAULT")

    click.echo()
    if ok:
        click.echo(click.style("All checks passed. MAKRAY is ready!", fg="green", bold=True))
    else:
        click.echo(click.style("Some checks failed. Fix the issues above before using MAKRAY.", fg="red"))
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────── #
# Entry-point
# ──────────────────────────────────────────────────────────────────────────── #

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
