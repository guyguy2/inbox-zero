# 📬 inbox-zero

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Package Manager](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![CLI Integration](https://img.shields.io/badge/integration-Google%20Workspace%20CLI%20(gws)-green.svg)](https://github.com/googleworkspace/cli)
[![Tests](https://img.shields.io/badge/tests-41%20passed-brightgreen.svg)]()
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
- 🤖 **Empowers AI Agents**: Emits Pydantic-validated structured JSON for LLM orchestration and Antigravity (AGY) workflows.

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
 🖥️ Interactive CLI (Rich / Typer)        🤖 AI Agent Bridge (agent_bridge.py)
 - Visual Triage Tables                   - Structured Pydantic Payloads
 - Step-by-Step Email Review              - Programmatic Decision Dispatch
 - 1-Click Calendar Add & Mark Read       - Two-way AGY Agent Integration
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
│       ├── agent_bridge.py     # AI Agent & AGY ingestion / decision execution bridge
│       └── cli.py              # Interactive Rich / Typer terminal application
└── tests/
    ├── test_parser.py          # HTML parsing and cleanup tests
    ├── test_analyzer.py        # Heuristics, dates, and reply suggestion tests
    ├── test_client.py          # GWS client auth checks, timeouts & command tests
    ├── test_models.py          # Pydantic schema validation & serialization tests
    ├── test_agent_bridge.py    # AI Agent payload preparation & decision dispatch tests
    └── test_cli.py             # Typer CLI test suite (table, review, JSON, mark-read)
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

## 🤖 AI Agent & AGY Bridge Usage

You can use [`agent_bridge.py`](file:///Users/guy/dev/ai/ai-tools/inbox_zero/src/inbox_zero/agent_bridge.py) to integrate `inbox-zero` with Antigravity (AGY) or any LLM agent in two simple steps:

```python
from inbox_zero import prepare_agent_triage_payload, apply_agent_decisions

# 1. Generate clean, sanitized payload for the AI agent
agent_payload = prepare_agent_triage_payload(limit=10)

# 2. Pass agent_payload to AGY / LLM for reasoning...
# (The LLM reviews summaries, identifies conflicts, and generates decision JSON)

# 3. Apply the AI agent's decisions deterministically
decisions = {
    "replies": [
        {"message_id": "1a025fb2f98bed9f", "body": "Thank you Mrs. Patel for the update!"}
    ],
    "calendar_events": [
        {
            "summary": "AYSO Soccer Practice",
            "start_time": "2026-08-27T17:00:00-05:00",
            "location": "Wood Oaks Field 3"
        }
    ],
    "mark_as_read": ["1a025fb2f98bed9f"]
}

results = apply_agent_decisions(decisions)
print("Execution Results:", results)
```

---

## 🧪 Testing

Run the full offline test suite:
```bash
uv run pytest -v
```

Output:
```text
tests/test_agent_bridge.py::test_prepare_agent_triage_payload PASSED
tests/test_agent_bridge.py::test_apply_agent_decisions PASSED
tests/test_analyzer.py::test_categorization PASSED
tests/test_analyzer.py::test_is_disclaimer PASSED
tests/test_analyzer.py::test_is_automated_sender PASSED
tests/test_analyzer.py::test_action_item_extraction PASSED
tests/test_analyzer.py::test_date_extraction_various_formats PASSED
tests/test_analyzer.py::test_suggest_replies_teacher PASSED
tests/test_analyzer.py::test_suggest_replies_sports_coach PASSED
tests/test_analyzer.py::test_suggest_replies_automated_skipped PASSED
tests/test_analyzer.py::test_analyze_email_full PASSED
tests/test_cli.py::test_cli_scan_auth_failure PASSED
tests/test_cli.py::test_cli_scan_empty PASSED
tests/test_cli.py::test_cli_scan_with_messages PASSED
tests/test_cli.py::test_cli_scan_json PASSED
tests/test_cli.py::test_cli_mark_read_subcommand PASSED
tests/test_cli.py::test_cli_review_mode_mark_read PASSED
tests/test_cli.py::test_cli_review_mode_quit PASSED
tests/test_client.py::test_ensure_authenticated_success PASSED
tests/test_client.py::test_ensure_authenticated_failure_invalid_token PASSED
tests/test_client.py::test_ensure_authenticated_failure_exit_code_2 PASSED
tests/test_client.py::test_list_unread_messages_success PASSED
tests/test_client.py::test_get_message_success PASSED
tests/test_client.py::test_mark_as_read_success PASSED
tests/test_client.py::test_mark_multiple_as_read PASSED
tests/test_client.py::test_send_reply_success PASSED
tests/test_client.py::test_insert_calendar_event PASSED
tests/test_client.py::test_client_timeout_error PASSED
tests/test_client.py::test_client_not_found_error PASSED
tests/test_client.py::test_client_invalid_json_error PASSED
tests/test_models.py::test_sender_from_dict PASSED
tests/test_models.py::test_sender_from_dict_address_fallback PASSED
tests/test_models.py::test_sender_from_formatted_string PASSED
tests/test_models.py::test_sender_from_plain_string PASSED
tests/test_models.py::test_sender_from_invalid PASSED
tests/test_models.py::test_calendar_event_suggestion_model PASSED
tests/test_models.py::test_triage_batch_json_serialization PASSED
tests/test_parser.py::test_clean_html PASSED
tests/test_parser.py::test_extract_clean_email_body_fallback PASSED
tests/test_parser.py::test_sender_parsing PASSED
tests/test_parser.py::test_truncate_preview PASSED

============================== 41 passed in 0.13s ==============================
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
