"""Bridge utilities for integrating inbox-zero with Antigravity (AGY), Claude Code, Codex, Grok, and custom AI agents."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from typing import Any

from inbox_zero.analyzer import analyze_email, analyze_thread
from inbox_zero.client import GWSClient
from inbox_zero.models import AgentDecisions, TriageBatch, TriageItem


class AgentExecutionError(Exception):
    """Raised when an external agent command fails or returns invalid output."""

    pass


DEFAULT_AGENT_SYSTEM_PROMPT = """You are an intelligent email triage assistant.
You are given a JSON payload containing unread email threads with extracted action items, dates, and sender information.
Your task is to review the unread items and produce a JSON decision object with three main actions:
1. "replies": List of replies to send for relevant emails (e.g. acknowledging instructions, confirming attendance, answering questions). Do not reply to automated newsletters.
   Each reply object must have:
   - "message_id": ID of message to reply to
   - "body": Text content of the reply
2. "calendar_events": List of calendar events to insert for explicitly mentioned events or meetings.
   Each event object must have:
   - "summary": Event title
   - "start_time": ISO-8601 string (e.g. "2026-08-27T17:00:00") or "YYYY-MM-DD"
   - "end_time": (optional ISO-8601 string)
   - "description": (optional notes)
   - "location": (optional location)
3. "mark_as_read": List of thread_ids or message_ids to mark as read (e.g. acknowledged emails, automated updates, or replied threads).

Return ONLY a valid JSON object matching this schema:
{
  "reasoning": "Short 1-2 sentence explanation of your decisions",
  "replies": [
    {"message_id": "...", "body": "..."}
  ],
  "calendar_events": [
    {"summary": "...", "start_time": "...", "end_time": null, "description": "...", "location": "..."}
  ],
  "mark_as_read": ["..."]
}
"""

PROVIDER_DEFAULT_COMMANDS: dict[str, list[str]] = {
    "agy": ["agy", "run"],
    "claude": ["claude", "-p"],
    "codex": ["codex"],
    "grok": ["grok"],
}


def get_agent_command(provider: str = "agy", custom_command: str | None = None) -> list[str]:
    """Resolve CLI command args for the chosen agent provider."""
    if custom_command:
        return shlex.split(custom_command)
    prov = provider.lower().strip()
    if prov in PROVIDER_DEFAULT_COMMANDS:
        return list(PROVIDER_DEFAULT_COMMANDS[prov])
    # Fallback to provider name as command
    return [prov]


def extract_json_from_agent_output(raw_output: str) -> dict[str, Any]:
    """Extract and parse structured JSON decisions from agent response."""
    text = raw_output.strip()
    if not text:
        raise AgentExecutionError("Agent returned empty output.")

    # 1. Direct JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Markdown fenced code block ```json ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1).strip())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 3. Outer curly braces search
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            data = json.loads(text[first_brace : last_brace + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    raise AgentExecutionError(f"Could not extract valid JSON decisions from agent output:\n{raw_output[:500]}")


def build_agent_prompt(
    payload: dict[str, Any],
    system_prompt: str | None = None,
) -> str:
    """Combine system prompt instructions and triage JSON payload into a single prompt string."""
    sys_prompt = system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT
    payload_json = json.dumps(payload, indent=2)
    return f"{sys_prompt.strip()}\n\nHere is the triage payload:\n```json\n{payload_json}\n```\n\nReturn your JSON decision object now:"


def run_agent(
    payload: dict[str, Any],
    provider: str = "agy",
    custom_command: str | None = None,
    system_prompt: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Execute a local subscription-based AI agent (AGY, Claude Code, Codex, Grok, etc.) to triage emails.

    This invokes the agent's CLI tool directly using your active subscription session
    with zero per-token API billing.
    """
    cmd = get_agent_command(provider=provider, custom_command=custom_command)
    prompt_str = build_agent_prompt(payload, system_prompt=system_prompt)

    try:
        if cmd == ["claude", "-p"]:
            exec_cmd = cmd + [prompt_str]
            proc = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        else:
            proc = subprocess.run(
                cmd,
                input=prompt_str,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Process exited with code {proc.returncode}"
            raise AgentExecutionError(f"Agent '{provider}' command failed ({' '.join(cmd)}): {err_msg}")

        return extract_json_from_agent_output(proc.stdout)
    except FileNotFoundError as e:
        raise AgentExecutionError(
            f"Agent CLI binary '{cmd[0]}' not found in PATH.\n"
            f"Please ensure '{provider}' is installed and authenticated via subscription, or configure a custom command."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise AgentExecutionError(f"Agent '{provider}' timed out after {timeout}s.") from e


def prepare_agent_triage_payload(
    limit: int = 20,
    query: str = "is:unread",
    client: GWSClient | None = None,
) -> dict[str, Any]:
    """Fetch unread email threads, sanitize them, and format a structured prompt payload for an AI agent.

    This function is used by AGY or headless agents to get pre-filtered,
    privacy-safe email thread text without raw HTML junk or tracking code.
    """
    if client is None:
        client = GWSClient(check_auth_on_init=True)
    unread_threads = client.list_unread_threads(max_results=limit, query=query)

    items: list[TriageItem] = []
    total_messages = 0

    if unread_threads:
        for t in unread_threads:
            tid = t.get("id")
            if not tid:
                continue
            try:
                messages = client.get_thread(tid)
                if not messages:
                    continue
                item = analyze_thread(messages)
                items.append(item)
                total_messages += len(messages)
            except Exception:
                continue
    else:
        # Fallback to message-level triage if threads API returns empty
        unread_messages = client.list_unread_messages(max_results=limit, query=query)
        for m in unread_messages:
            mid = m.get("id")
            if not mid:
                continue
            try:
                msg = client.get_message(mid)
                item = analyze_email(msg)
                items.append(item)
                total_messages += 1
            except Exception:
                continue

    batch = TriageBatch(total_unread=len(items), total_messages=total_messages, items=items)
    return batch.model_dump()


def apply_agent_decisions(
    decisions: dict[str, Any],
    client: GWSClient | None = None,
) -> dict[str, Any]:
    """Apply structured actions returned by AGY or an AI reasoning agent.

    Expected schema for decisions:
    {
        "mark_as_read": ["message_id_or_thread_id_1", "..."],
        "replies": [{"message_id": "...", "body": "..."}],
        "calendar_events": [{"summary": "...", "start_time": "...", "description": "..."}]
    }
    """
    if client is None:
        client = GWSClient(check_auth_on_init=True)

    results = {
        "marked_read": {},
        "replies_sent": {},
        "events_created": [],
    }

    # 1. Process replies
    for rep in decisions.get("replies", []):
        mid = rep.get("message_id")
        body = rep.get("body")
        if mid and body:
            success = client.send_reply(mid, body)
            results["replies_sent"][mid] = success

    # 2. Process calendar events
    for ev in decisions.get("calendar_events", []):
        summary = ev.get("summary")
        start = ev.get("start_time")
        if summary and start:
            res = client.insert_calendar_event(
                summary=summary,
                start_time=start,
                end_time=ev.get("end_time"),
                description=ev.get("description", ""),
                location=ev.get("location", ""),
            )
            results["events_created"].append(res)

    # 3. Process mark as read (threads or messages)
    for target_id in decisions.get("mark_as_read", []):
        # Try thread modify first, then message modify
        success = bool(client.mark_thread_as_read(target_id) or client.mark_as_read(target_id))
        results["marked_read"][target_id] = success

    return results
