# 📬 inbox-zero

> Intelligent, deterministic Email Triage, Action Item Extraction, and Google Calendar Scheduling powered by **Google Workspace CLI (`gws`)**, **UV**, and **AI Agents**.

---

## 🌟 Overview

`inbox-zero` is a developer-centric, privacy-first email triage assistant designed to help you reach and maintain **Inbox Zero**. By marrying deterministic Python extraction pipelines with the official Google Workspace CLI (`gws`), `inbox-zero` quickly parses unread emails, isolates key action items, extracts dates/events for calendar addition, and allows single-key batch or itemized email disposition.

---

## 🏗️ Architecture & Design

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
│   gws_client.py   │     parser.py     │     analyzer.py     │
│   Deterministic   │ HTML -> Clean Text│ Action Items, Dates │
│   GWS Controller  │ Boilerplate Filter│ Event Deduplication │
└───────────────────┴───────────────────┴─────────────────────┘
                               │
           ┌───────────────────┴───────────────────┐
           ▼                                       ▼
 🖥️ Interactive CLI (Rich / Typer)        🤖 AI Agent Interface (JSON / CLI)
 - Visual Triage Tables                   - Structured Pydantic Payloads
 - Step-by-Step Email Review              - Contextual Reasoning & Q&A
 - 1-Click Calendar Add & Mark Read       - Automated Inbox Management
```

### Key Architectural Decisions
1. **Zero Raw Token Overhead / Direct gws Integration**: Uses local `gws` OAuth2 authentication rather than managing separate API keys or heavy Google API client libraries.
2. **Robust HTML-to-Text Fallbacks**: Gracefully converts rich newsletter HTML, handles base64 decoding, and strips email signatures and legal disclaimers.
3. **Deterministic + AI Hybrid**: Deterministic regex and heuristic parsers provide instant, zero-cost analysis; structured JSON exports allow AI coding assistants and LLMs to provide deep contextual summaries and automated decision-making.
4. **Reproducible Environment with UV**: Utilizes astral's `uv` for sub-second virtualenv resolution, packaging, and dependency locking.

---

## 🚀 Quickstart

### 1. Prerequisites
- **Python 3.12+**
- **uv**: Modern Python package and project manager ([installation guide](https://github.com/astral-sh/uv))
- **gws CLI**: Authenticated Google Workspace CLI ([Google Workspace CLI](https://github.com/googleworkspace/cli))

Ensure `gws` is authenticated:
```bash
gws auth status
```

### 2. Installation
Clone the repository and install dependencies using `uv`:
```bash
git clone <repo-url>
cd inbox_zero
uv sync
```

---

## 🛠️ Usage

### 1. Scan Unread Emails (Rich Table View)
Scan up to 20 unread emails with instant summary, detected action items, and calendar suggestions:
```bash
uv run inbox-zero scan
```

Scan with custom query filters:
```bash
uv run inbox-zero scan --limit 10 --query "is:unread from:teacher@nb27.org"
```

### 2. Export Structured JSON (For AI Agents & Automation)
Output complete Pydantic-validated JSON payloads:
```bash
uv run inbox-zero scan --json
```

### 3. Interactive Review Mode
Step through each unread message one-by-one. View the summary, action items, and calendar dates. Press `[y]` to mark as read, `[c]` to add events to Google Calendar, or `[n]` to keep unread:
```bash
uv run inbox-zero review
```

### 4. Direct Operations
Mark specific emails as read:
```bash
uv run inbox-zero mark-read <MESSAGE_ID_1> <MESSAGE_ID_2>
```

---

## 🧪 Testing

Run the test suite:
```bash
uv run pytest
```

---

## 🔒 Security & Privacy
- **Local-Only Execution**: No email bodies or tokens leave your local environment.
- **Explicit User Confirmation**: No email is modified or marked as read without explicit user confirmation.
- **Strict Stderr Isolation**: Adheres to `gws` subprocess guidelines, preventing stderr credential leaks into parsed stdout pipes.

---

## 📜 License
MIT
