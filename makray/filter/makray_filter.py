"""MAKRAY filter layer.

This module is the heart of the Obsidian → Claude pipeline.
It decides *what* context from the vault is relevant to a given user query,
ranks it, and assembles it into a compact system-prompt block that Claude
can use as grounded knowledge.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from makray.obsidian.note import ObsidianNote
    from makray.obsidian.vault import ObsidianVault


_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "can", "could", "should", "may", "might", "shall", "i", "you",
        "he", "she", "it", "we", "they", "me", "him", "her", "us",
        "them", "my", "your", "his", "its", "our", "their",
    }
)


@dataclass
class FilteredContext:
    """The distilled context block produced by the MAKRAY filter."""

    notes: list["ObsidianNote"]
    query: str
    system_prompt: str
    token_estimate: int


class MAKRAYFilter:
    """Intelligent filter between an Obsidian vault and the Claude API.

    Responsibilities
    ----------------
    1. Accept a natural-language query from the user.
    2. Search the vault for relevant notes using keyword scoring.
    3. Rank and trim notes so the combined context stays within the
       configured token budget.
    4. Assemble a structured *system prompt* that introduces the Obsidian
       context to Claude.

    Parameters
    ----------
    vault:
        An initialised :class:`~makray.obsidian.vault.ObsidianVault`.
    max_context_tokens:
        Approximate token ceiling for the injected Obsidian context
        (1 token ≈ 4 characters).
    top_k:
        Maximum number of notes to consider before trimming.
    excerpt_chars:
        Maximum characters taken from each note body as an excerpt.
    system_header:
        Prefix prepended to the assembled system prompt.
    """

    def __init__(
        self,
        vault: "ObsidianVault",
        *,
        max_context_tokens: int = 4000,
        top_k: int = 8,
        excerpt_chars: int = 600,
        system_header: str | None = None,
    ) -> None:
        self.vault = vault
        self.max_context_tokens = max_context_tokens
        self.top_k = top_k
        self.excerpt_chars = excerpt_chars
        self.system_header = system_header or (
            "You are MAKRAY, an Operational Intelligent System Navigator. "
            "You assist the user by drawing on their personal Obsidian vault "
            "as a knowledge base. Below is relevant context retrieved from "
            "the vault for the current query. Use it to give grounded, "
            "precise answers — and acknowledge when information is absent.\n"
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def build_context(self, query: str) -> FilteredContext:
        """Return a :class:`FilteredContext` for *query*.

        This is the main entry-point called by the Claude client before each
        API request.
        """
        candidates = self.vault.search(query, limit=self.top_k)
        ranked = self._rank(query, candidates)
        trimmed = self._trim_to_budget(ranked)
        system_prompt = self._assemble_system_prompt(query, trimmed)
        token_estimate = len(system_prompt) // 4
        return FilteredContext(
            notes=trimmed,
            query=query,
            system_prompt=system_prompt,
            token_estimate=token_estimate,
        )

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return [w for w in words if w not in _STOP_WORDS]

    def _score(self, query: str, note: "ObsidianNote") -> float:
        """TF-based relevance score of *note* against *query*."""
        q_tokens = set(self._tokenise(query))
        if not q_tokens:
            return 0.0

        body_tokens = self._tokenise(note.title + " " + note.body)
        if not body_tokens:
            return 0.0

        matches = sum(1 for t in body_tokens if t in q_tokens)
        tf = matches / len(body_tokens)

        # Bonus for tag overlap
        tag_tokens = set(self._tokenise(" ".join(note.tags)))
        tag_overlap = len(q_tokens & tag_tokens) / max(len(q_tokens), 1)

        # Heading bonus
        heading_tokens = set(self._tokenise(" ".join(note.headings)))
        heading_overlap = len(q_tokens & heading_tokens) / max(
            len(q_tokens), 1
        )

        return tf + 0.3 * tag_overlap + 0.2 * heading_overlap

    def _rank(
        self, query: str, notes: list["ObsidianNote"]
    ) -> list["ObsidianNote"]:
        scored = [(self._score(query, n), n) for n in notes]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored]

    def _trim_to_budget(
        self, notes: list["ObsidianNote"]
    ) -> list["ObsidianNote"]:
        """Keep notes until we would exceed the token budget."""
        budget_chars = self.max_context_tokens * 4
        used = len(self.system_header)
        kept: list["ObsidianNote"] = []
        for note in notes:
            excerpt_len = min(len(note.body), self.excerpt_chars)
            # Rough size of one note block in the system prompt
            block_size = len(note.title) + excerpt_len + 80
            if used + block_size > budget_chars:
                break
            kept.append(note)
            used += block_size
        return kept

    def _excerpt(self, note: "ObsidianNote") -> str:
        """Return a readable excerpt from *note*."""
        text = note.body.strip()
        if len(text) <= self.excerpt_chars:
            return text
        # Try to cut at a sentence boundary
        cut = text[: self.excerpt_chars]
        last_period = max(cut.rfind(". "), cut.rfind("\n"))
        if last_period > self.excerpt_chars // 2:
            cut = cut[: last_period + 1]
        return cut + " …"

    def _assemble_system_prompt(
        self, query: str, notes: list["ObsidianNote"]
    ) -> str:
        parts: list[str] = [self.system_header]

        if not notes:
            parts.append(
                "No directly relevant notes were found in the vault for "
                f"this query: {query!r}. Answer based on general knowledge "
                "and remind the user they can add notes to their vault.\n"
            )
            return "\n".join(parts)

        parts.append(
            f"## Obsidian Vault Context  ({len(notes)} note(s) retrieved)\n"
        )
        for i, note in enumerate(notes, 1):
            rel_path = str(note.path.relative_to(self.vault.vault_path))
            tags_str = (
                "  |  Tags: " + ", ".join(f"#{t}" for t in note.tags)
                if note.tags
                else ""
            )
            block = textwrap.dedent(f"""\
                ### [{i}] {note.title}
                _Path: {rel_path}{tags_str}_

                {self._excerpt(note)}
            """)
            parts.append(block)

        parts.append(
            "\n---\nAnswer the user's question using the vault context above. "
            "Cite note titles when referencing specific information."
        )
        return "\n".join(parts)
