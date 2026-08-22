# 📬 inbox-zero

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Package Manager](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![CLI Integration](https://img.shields.io/badge/integration-Google%20Workspace%20CLI%20(gws)-green.svg)](https://github.com/googleworkspace/cli)
[![Tests](https://img.shields.io/badge/tests-20%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Intelligent, deterministic Email Triage, Action Item Extraction, Contextual Reply Generation, and Google Calendar Scheduling powered by **Google Workspace CLI (`gws`)**, **UV**, and **AI Agents**.

---

## 🌟 Overview

`inbox-zero` is a privacy-first, developer-centric email triage tool designed to help you reach and maintain **Inbox Zero**. By marrying fast deterministic Python parsing with the official Google Workspace CLI (`gws`), `inbox-zero` automatically:
- 📖 **Scans & Cleans Emails**: Parses raw Gmail threads, converts multipart HTML newsletters to clean markdown, and strips legal disclaimers.
- ⚡ **Extracts Action Items**: Surfaces explicit requests, required forms, payments, and deadlines.
- 📅 **Detects Calendar Events**: Isolates dates and times, suggesting 1-click Google Calendar additions.
- 💬 **Drafts Contextual Smart Replies**: Suggests natural quick replies for human senders (teachers, coaches, colleagues) while ignoring automated newsletters.
- 🛡️ **Fails Fast on Auth**: Immediately detects unauthenticated or expired `gws` sessions with clear recovery steps (`gws auth login`).
- 🤖 **Empowers AI Agents**: Emits Pydantic-validated structured JSON for LLM orchestration and pair-programming assistants.

---

## 🏗️ Architecture & System Design

```
┌─────────────────────────────────────────────────────────────┐
│                       Google Workspace                      │
│                  (Gmail API & Google Calendar)              │
└──────────────────────────────▲──────────────────────────────┘
                               │
                       [ gws CLI Layer ]
                OAuth2 / Subprocess Orchestration
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
           ┌───────────────────┴───────────────────┐
           ▼                                       ▼
 🖥️ Interactive CLI (Rich / Typer)        🤖 AI Agent Interface (JSON / CLI)
 - Visual Triage Tables                   - Structured Pydantic Payloads
 - Step-by-Step Email Review              - Contextual Reasoning & Q&A
 - 1-Click Calendar Add & Mark Read       - Automated Inbox Management
 - 1-Click Contextual Reply Sending
```

### Repository Layout
```
inbox_zero/
├── pyproject.toml              # UV package specification & dependencies
├── uv.lock                     # Deterministic dependency lockfile
├── README.md                   # Project documentation
├── src/
│   └── inbox_zero/
│       ├── __init__.py         # Public package exports
│       ├── client.py           # Subprocess wrapper for gws CLI (Gmail + Calendar)
│       ├── models.py           # Pydantic schemas (EmailMessage, TriageItem, CalendarEventSuggestion)
│       ├── parser.py           # BeautifulSoup HTML cleaner & disclaimer filter
│       ├── analyzer.py         # Deterministic date/action heuristics & smart replies
│       └── cli.py              # Interactive Rich / Typer terminal application
└── tests/
    ├── test_parser.py          # HTML parsing and cleanup tests
    ├── test_analyzer.py        # Heuristics, dates, and reply suggestion tests
    ├── test_client.py          # GWS client auth checks & command tests
    └── test_cli.py             # Typer CLI test suite (table, review, JSON)
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

### 2. Export Structured JSON (For AI Agents & Automation)
Output complete Pydantic-validated JSON payloads:
```bash
uv run inbox-zero scan --json
```

### 3. Interactive Review Mode
Step through unread emails one by one. Choose actions interactively:
- `[y]` **Mark Read**: Removes the unread label in Gmail.
- `[n]` **Keep Unread**: Leaves email untouched.
- `[c]` **Add to Calendar**: Inserts detected dates/times into Google Calendar.
- `[r]` **Send Reply**: Choose a suggested draft or compose a custom reply.
- `[q]` **Quit**: Exit triage safely.

```bash
uv run inbox-zero review
```

### 4. Direct Operations
Mark specific emails as read by ID:
```bash
uv run inbox-zero mark-read <MESSAGE_ID_1> <MESSAGE_ID_2>
```

---

## 🐍 Python API Usage

You can also import and use `inbox_zero` programmatically in your own Python scripts and agents:

```python
from inbox_zero import GWSClient, analyze_email

# 1. Initialize client (fails fast if gws is not authenticated)
client = GWSClient(check_auth_on_init=True)

# 2. Fetch unread messages
unread = client.list_unread_messages(max_results=10)

# 3. Analyze each message
for m in unread:
    msg = client.get_message(m["id"])
    triage = analyze_email(msg)
    
    print(f"[{triage.category}] {triage.title_summary}")
    print(f"Actions: {triage.action_items}")
    print(f"Events: {[e.summary for e in triage.calendar_events]}")
    print(f"Replies: {triage.suggested_replies}")
```

---

## 🧪 Testing

Run the test suite (100% offline, mocked GWS client):
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
