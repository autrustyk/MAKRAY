# MAKRAY — Operational Intelligent System Navigator

**MAKRAY** is an AI-powered bridge that links your [Obsidian](https://obsidian.md) knowledge vault directly to [Claude](https://www.anthropic.com/claude), acting as an intelligent filter layer between your personal notes and the AI.

Every time you ask Claude a question, MAKRAY automatically retrieves the most relevant notes from your vault, scores and ranks them, and injects them as grounded context — so Claude answers based on *your* knowledge, not just its training data.

---

## Architecture

```
┌───────────────────────┐
│   Obsidian Vault      │  (.md files, YAML frontmatter, [[wikilinks]], #tags)
└──────────┬────────────┘
           │ vault.search()
           ▼
┌───────────────────────┐
│   MAKRAY Filter Layer │  relevance scoring · token budgeting · system-prompt assembly
└──────────┬────────────┘
           │ system_prompt + conversation history
           ▼
┌───────────────────────┐
│   Claude API          │  (Anthropic SDK — claude-3-5-sonnet, etc.)
└──────────┬────────────┘
           │ grounded reply
           ▼
        You 🧠
```

---

## Features

| Feature | Description |
|---|---|
| **Obsidian vault reader** | Reads `.md` files recursively; parses YAML frontmatter, inline `#tags`, `[[wikilinks]]`, headings |
| **MAKRAY filter** | TF-based relevance scoring with tag/heading bonuses; token-budget trimming; structured system-prompt assembly |
| **Claude integration** | Wraps the Anthropic Python SDK; supports streaming; maintains conversation history |
| **CLI** | `makray chat`, `makray search`, `makray list` — all configurable via flags or environment variables |
| **Extensible** | Clean Python package — import `MAKRAYFilter`, `ObsidianVault`, `ClaudeClient` directly |

---

## Installation

**Prerequisites:** Python 3.10+

```bash
# 1. Clone the repo
git clone https://github.com/autrustyk/MAKRAY.git
cd MAKRAY

# 2. Install (creates the `makray` CLI command)
pip install .

# 3. Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Set your vault path (or pass --vault each time)
export MAKRAY_VAULT="$HOME/my-obsidian-vault"
```

---

## Quick-start

### Interactive chat session

```bash
makray chat --vault ~/my-obsidian-vault
```

```
⚡ MAKRAY connected to vault: /home/user/my-obsidian-vault
   Model : claude-3-5-sonnet-20241022
   Type your question, or 'exit' / Ctrl-C to quit.

You › What is my project roadmap?

MAKRAY › Based on your "Project Roadmap" note (tagged #planning, #makray):
  Phase 1 — Obsidian integration …
```

### One-shot query

```bash
makray chat --vault ~/vault --query "Summarise my AI research notes"
```

### Search the vault (no Claude call)

```bash
makray search --vault ~/vault "obsidian claude filter"
makray search --vault ~/vault "roadmap" --tag planning --tag ai
```

### List all notes

```bash
makray list --vault ~/vault
makray list --vault ~/vault --tag project
```

---

## Configuration

Copy `config.yaml.example` to `config.yaml` and fill in your values, **or** use environment variables / CLI flags.

| Setting | Env var | CLI flag | Default |
|---|---|---|---|
| Vault path | `MAKRAY_VAULT` | `--vault` | *(required)* |
| API key | `ANTHROPIC_API_KEY` | `--api-key` | *(required)* |
| Model | — | `--model` | `claude-3-5-sonnet-20241022` |
| Context tokens | — | `--max-tokens` | `4000` |
| Top-K notes | — | `--top-k` | `8` |

---

## Python API

```python
from makray import ClaudeClient

client = ClaudeClient(
    vault_path="~/my-obsidian-vault",
    # api_key loaded from ANTHROPIC_API_KEY automatically
)

# Ask a question — MAKRAY retrieves relevant vault notes automatically
reply = client.chat("What are my notes on the MAKRAY project?", stream=True)

# Search the vault directly
results = client.search_vault("claude integration", tags=["ai"])
for r in results:
    print(r["title"], r["path"], r["tags"])
    print(r["excerpt"])
```

Lower-level access:

```python
from makray.obsidian import ObsidianVault
from makray.filter import MAKRAYFilter

vault = ObsidianVault("~/vault")
fltr = MAKRAYFilter(vault, max_context_tokens=6000, top_k=10)

ctx = fltr.build_context("project architecture")
print(ctx.system_prompt)   # what gets sent to Claude as the system prompt
print(ctx.token_estimate)  # rough token count
for note in ctx.notes:
    print(note.title, note.tags)
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Roadmap

- [ ] Watch mode — auto-reload vault on file changes
- [ ] Semantic search using embeddings (local or via API)
- [ ] Obsidian plugin to call MAKRAY directly from within Obsidian
- [ ] Per-conversation memory / session persistence
- [ ] Support for multiple vaults

---

Makray is a robot powered by AI. In the world of Makray, everybody is able to start any project from scratch while live-updated with the most efficient system algorithm. Makray will redefine the web as a universe of efficient, energy-conscious datacenter production. My vision!
