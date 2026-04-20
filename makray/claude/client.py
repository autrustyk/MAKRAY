"""Claude API client for MAKRAY.

Wraps the Anthropic SDK and integrates the MAKRAY filter layer so that
every conversation message is enriched with relevant Obsidian vault context.
"""

from __future__ import annotations

import os
from typing import Iterator

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

from makray.filter import MAKRAYFilter
from makray.obsidian import ObsidianVault


class ClaudeClient:
    """High-level Claude client that uses MAKRAY as an Obsidian filter.

    Parameters
    ----------
    vault_path:
        Path to the Obsidian vault directory.
    api_key:
        Anthropic API key.  Falls back to the ``ANTHROPIC_API_KEY``
        environment variable when *None*.
    model:
        Claude model identifier (default: ``claude-3-5-sonnet-20241022``).
    max_context_tokens:
        Token budget for the Obsidian context injected per request.
    top_k:
        Maximum notes the filter will retrieve per query.
    excerpt_chars:
        Maximum excerpt length per note.
    max_response_tokens:
        Maximum tokens Claude may use in a single reply.
    system_header:
        Custom system-prompt prefix for MAKRAY's persona.
    exclude_patterns:
        Glob patterns for vault files/folders to exclude.
    """

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(
        self,
        vault_path: str,
        *,
        api_key: str | None = None,
        model: str | None = None,
        max_context_tokens: int = 4000,
        top_k: int = 8,
        excerpt_chars: int = 600,
        max_response_tokens: int = 2048,
        system_header: str | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        if not _ANTHROPIC_AVAILABLE:
            raise ImportError(
                "The 'anthropic' package is required. "
                "Install it with: pip install anthropic"
            )

        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "An Anthropic API key is required. Set the "
                "ANTHROPIC_API_KEY environment variable or pass api_key=..."
            )

        self.model = model or self.DEFAULT_MODEL
        self.max_response_tokens = max_response_tokens

        self.vault = ObsidianVault(vault_path, exclude_patterns=exclude_patterns)
        self.filter = MAKRAYFilter(
            self.vault,
            max_context_tokens=max_context_tokens,
            top_k=top_k,
            excerpt_chars=excerpt_chars,
            system_header=system_header,
        )
        self._client = anthropic.Anthropic(api_key=self._api_key)
        self._history: list[dict[str, str]] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def chat(
        self,
        user_message: str,
        *,
        stream: bool = False,
    ) -> str:
        """Send *user_message* to Claude with injected vault context.

        Parameters
        ----------
        user_message:
            The user's query or instruction.
        stream:
            If *True*, print tokens to stdout as they arrive and return the
            full assembled response.

        Returns
        -------
        str
            Claude's full reply.
        """
        ctx = self.filter.build_context(user_message)
        self._history.append({"role": "user", "content": user_message})

        if stream:
            reply = self._stream(ctx.system_prompt)
        else:
            reply = self._send(ctx.system_prompt)

        self._history.append({"role": "assistant", "content": reply})
        return reply

    def search_vault(
        self,
        query: str,
        *,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search the vault and return a list of note summaries.

        Returns
        -------
        list of dict
            Each dict has keys: ``title``, ``path``, ``tags``, ``excerpt``.
        """
        notes = self.vault.search(query, tags=tags, limit=limit)
        results = []
        for note in notes:
            rel = str(note.path.relative_to(self.vault.vault_path))
            excerpt = note.body.strip()[: 200].replace("\n", " ")
            results.append(
                {
                    "title": note.title,
                    "path": rel,
                    "tags": note.tags,
                    "excerpt": excerpt,
                }
            )
        return results

    def reset_history(self) -> None:
        """Clear the conversation history."""
        self._history = []

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _send(self, system_prompt: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_response_tokens,
            system=system_prompt,
            messages=self._history,
        )
        return response.content[0].text

    def _stream(self, system_prompt: str) -> str:
        collected: list[str] = []
        with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_response_tokens,
            system=system_prompt,
            messages=self._history,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                collected.append(text)
        print()  # newline after streaming ends
        return "".join(collected)
