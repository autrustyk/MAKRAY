"""MAKRAY — Operational Intelligent System Navigator.

Obsidian ↔ Claude integration with intelligent context filtering.
"""

from makray.claude import ClaudeClient
from makray.filter import MAKRAYFilter
from makray.obsidian import ObsidianNote, ObsidianVault

__version__ = "0.1.0"

__all__ = [
    "ClaudeClient",
    "MAKRAYFilter",
    "ObsidianNote",
    "ObsidianVault",
    "__version__",
]
