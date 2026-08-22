# 📬 inbox-zero

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Package Manager](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![CLI Integration](https://img.shields.io/badge/integration-Google%20Workspace%20CLI%20(gws)-green.svg)](https://github.com/googleworkspace/cli)
[![Tests](https://img.shields.io/badge/tests-91%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Intelligent, deterministic Email Triage, Action Item Extraction, Contextual Reply Generation, and Google Calendar Scheduling powered by **Google Workspace CLI (`gws`)**, **UV**, and **Pluggable AI Agents (AGY, Claude Code, Codex, Grok)**.

---

## 🌟 Overview

`inbox-zero` is a privacy-first, developer-centric email triage tool designed to help you reach and maintain **Inbox Zero**. By marrying fast deterministic Python parsing with the official Google Workspace CLI (`gws`) and pluggable AI agents, `inbox-zero` automatically:
- 📖 **Scans & Cleans Emails**: Parses raw Gmail threads, converts multipart HTML newsletters to clean markdown, and strips legal disclaimers.
- ⚡ **Extracts Action Items**: Surfaces explicit requests, required forms, payments, and deadlines.
- 📅 **Detects Calendar Events**: Isolates dates and times, suggesting 1-click Google Calendar additions.
- 💬 **Drafts Contextual Smart Replies**: Suggests natural quick replies for human senders (teachers, coaches, colleagues) while ignoring automated newsletters.
- 🤖 **Pluggable AI Agents (Subscription-Based)**: Plug in **AGY (default)**, **Claude Code**, **Codex**, **Grok**, or any custom CLI agent. Runs directly against your existing CLI tool subscriptions—**no per-token API billing**.
- 🛡️ **Fails Fast on Auth**: Immediately detects unauthenticated or expired `gws` sessions with clear recovery steps (`gws auth login`).

---

## 🏗️ Architecture & System Design

```
┌─────────────────────────────────────────────────────────────┐
│                       Google Workspace                      │
│                  (Gmail API & Google Calendar)              │
└──────────────────────────────▲──────────────────────────────┘
                               │
                       [ gws CLI Layer ]
                OAuth2 / Subprocess Orchestraction
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    inbox-zero Core Engine                   │
├───────────────────┬───────────────────┬─────────────────────┤
│   client.py       │     parser.py     │     analyzer.py     │
│   Deterministic   │ HTML -> Clean Text│ Action Items, Dates │
│   GWS Controller  │ Boilerplate Filter│ Contextual Replies  │
│   Fail-Fast Auth  │ Signature Strip   │ Event Deduplication │
└───────────────────┴───────────────────┴─────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 🖥️ Interactive CLI (Rich / Typer)        🤖 Pluggable AI Agents (agent_bridge.py)
 - Visual Triage Tables                   - AGY / Antigravity (Default)
 - Step-by-Step Email Review              - Claude Code (`claude -p`)
 - 1-Click Calendar Add & Mark Read       - Codex / ChatGPT CLI
 - 1-Click Contextual Reply Sending       - Grok / xAI CLI & Custom Runners
 - Zero Token API Billing Subscriptions   - Deterministic Decision Dispatch
```

### Repository Layout
```
inbox_zero/
├── pyproject.toml              # UV package specification & dependencies
├── uv.lock                     # Deterministic dependency lockfile
├── config.toml                 # User configuration file (review mode, agent provider)
├── README.md                   # Project documentation
├── src/
│   └── inbox_zero/
│       ├── __init__.py         # Public package exports
│       ├── config.py           # TOML/JSON configuration loader & schemas
│       ├── client.py           # Subprocess wrapper for gws CLI (Gmail + Calendar)
│       ├── models.py           # Pydantic schemas (EmailMessage, TriageItem, AgentDecisions)
│       ├── parser.py           # BeautifulSoup HTML cleaner & disclaimer filter
│       ├── analyzer.py         # Deterministic date/action heuristics & smart replies
│       ├── agent_bridge.py     # Pluggable AI Agent bridge & execution engine
│       ├── keys.py             # Single-keypress & directional arrow navigation reader
│       └── cli.py              # Interactive Rich / Typer terminal application
└── tests/
    ├── test_config.py          # Configuration loading & override tests
    ├── test_parser.py          # HTML parsing and cleanup tests
    ├── test_analyzer.py        # Heuristics, dates, and reply suggestion tests
    ├── test_client.py          # GWS client auth checks, timeouts & command tests
    ├── test_models.py          # Pydantic schema validation & serialization tests
    ├── test_agent_bridge.py    # AI Agent bridge & execution tests
    ├── test_keys.py            # Terminal single-keypress & alias mapping tests
    └── test_cli.py             # Typer CLI test suite (scan, review, agent, mark-read)
```

---

## 🚀 Quickstart

### 1. Prerequisites
- **Python 3.12+**
- **uv**: Modern, high-speed Python package manager ([Installation Guide](https://github.com/astral-sh/uv))
- **gws CLI**: Official Google Workspace CLI ([CLI Setup](https://github.com/googleworkspace/cli))

Check authentication:
```bash
gws auth status
```
*If not authenticated, run `gws auth login`.*

### 2. Installation & Setup
Clone the repository and synchronize the virtual environment:
```bash
git clone <repo-url>
cd inbox_zero
uv sync
```

Running `uv run inbox-zero` without arguments will show the available commands and help.

---

## ⚙️ Configuration

`inbox-zero` automatically looks for a configuration file in:
1. Custom path specified via `--config /path/to/config.toml`
2. `INBOX_ZERO_CONFIG` environment variable
3. Current working directory: `config.toml`, `inbox-zero.toml`, `.inbox-zero.toml`
4. User home directory: `~/.config/inbox-zero/config.toml`, `~/.inbox-zero.toml`

### Example `config.toml`
```toml
# inbox-zero configuration file

[review]
# By default, review mode shows title summary, overview, action items, dates, and suggested replies.
# Set show_body = true if you want to display the full email conversation thread body by default.
show_body = false

[agent]
# Pluggable AI Agent provider.
# Supported options: "agy" (default), "claude" (Claude Code), "codex", "grok", "custom"
# Uses your local CLI tool login/subscription with zero per-token API billing.
provider = "agy"

# Optional custom CLI command override (e.g. "claude -p", "codex", "grok --json")
# command = ""

# Automatically apply AI agent decisions without interactive confirmation (default: false)
auto_apply = false

# Default scan & review options:
# default_limit = 20
# default_query = "is:unread"
```

---

## 🛠️ CLI Usage & Workflows

### 1. Scan Unread Emails (Rich Table View)
Scan up to 20 unread emails with instant summary, detected action items, calendar suggestions, and draft replies:
```bash
uv run inbox-zero scan
```

Filter by custom queries or limits:
```bash
uv run inbox-zero scan --limit 10 --query "is:unread from:teacher@nb27.org"
```

### 2. Interactive Review Mode
Step through unread emails one by one with **instant single-keypress triage** and **directional arrow navigation**. By default, review mode displays the **title, summary, action items, calendar events, and suggested replies** without cluttering the screen with full email bodies.

```bash
uv run inbox-zero review
```

#### ⌨️ Single-Keypress & Arrow Controls
- **`[⏎]` (Enter)** or **`[→]` (Right Arrow)** or **`[d]`**: **Mark Read & Next** (Instantly mark thread read in Gmail and advance).
- **`[←]` (Left Arrow)** or **`[s]`**: **Keep Unread / Skip** (Leave email unread and advance).
- **`[↑]` (Up Arrow)** or **`[p]`**: **Previous Email** (Go back to the previous thread).
- **`[↓]` (Down Arrow)** or **`[v]`**: **View Full Thread** (Expand and view full email body).
- **`[r]`**: **Send Reply** (Instantly pick suggested replies `[1]`, `[2]` or type custom reply).
- **`[c]`**: **Add to Calendar** (Schedule detected meeting/date to Google Calendar).
- **`[?]` / `[h]`**: **Help** (Show interactive keyboard shortcuts).
- **`[q]` / `[Esc]`**: **Quit** interactive review.

#### Review Flags & Overrides
- `--show-body`: Show the full email thread body by default during review.
- `--no-show-body`: Hide the email thread body (even if enabled in `config.toml`).
- `--config <path>`: Load a specific configuration file.

### 3. Automated / Assisted AI Agent Triage
Run your chosen AI agent (AGY, Claude Code, Codex, Grok, or Custom) to evaluate unread messages, generate smart replies, create calendar events, and mark emails as read:

```bash
# Run with default agent (AGY)
uv run inbox-zero agent

# Run with Claude Code subscription
uv run inbox-zero agent --provider claude

# Run with Codex / Grok
uv run inbox-zero agent --provider codex
uv run inbox-zero agent --provider grok

# Auto-apply decisions without interactive confirmation prompt
uv run inbox-zero agent --provider claude --yes

# Dry-run: inspect prompt payload without executing the agent CLI
uv run inbox-zero agent --dry-run
```

### 4. Export Structured JSON (For Automation)
Output complete Pydantic-validated JSON payloads:
```bash
uv run inbox-zero scan --json
```

### 5. Direct Operations
Mark specific emails as read by ID:
```bash
uv run inbox-zero mark-read <MESSAGE_ID_1> <MESSAGE_ID_2>
```

---

## 🤖 Programmatic AI Agent Bridge Usage

You can also use [`agent_bridge.py`](file:///Users/guy/dev/ai/ai-tools/inbox_zero/src/inbox_zero/agent_bridge.py) directly in Python:

```python
from inbox_zero import prepare_agent_triage_payload, run_agent, apply_agent_decisions

# 1. Generate clean, sanitized payload for the AI agent
agent_payload = prepare_agent_triage_payload(limit=10)

# 2. Run agent via subscription CLI (e.g. claude, agy, grok, codex)
decisions = run_agent(agent_payload, provider="claude")

# 3. Apply the AI agent's decisions deterministically
results = apply_agent_decisions(decisions)
print("Execution Results:", results)
```

---

## 🧪 Testing

Run the full offline test suite:
```bash
uv run pytest
```

---

## 🔒 Security & Privacy
- **Local-Only Processing**: No email content or credentials leave your local machine.
- **Fail-Fast Safety**: Prevents unintended execution if OAuth credentials expire.
- **Explicit Confirmation**: No emails are marked read, replied to, or modified without user approval.
- **Stderr Protection**: Strict stderr stream separation prevents credentials or auth tokens from leaking into JSON parsing pipelines.

---

## 📜 License
MIT License. See [LICENSE](LICENSE) for details.
