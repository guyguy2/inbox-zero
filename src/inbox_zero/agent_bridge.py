"""Bridge utilities for integrating inbox-zero with Antigravity (AGY) and AI agents."""

from __future__ import annotations

import json
from typing import Any
from inbox_zero.client import GWSClient
from inbox_zero.analyzer import analyze_email
from inbox_zero.models import TriageBatch, TriageItem


def prepare_agent_triage_payload(limit: int = 20, query: str = "is:unread") -> dict[str, Any]:
    """Fetch unread emails, sanitize them, and format a structured prompt payload for an AI agent.
    
    This function is used by AGY or headless agents to get pre-filtered,
    privacy-safe email text without raw HTML junk or tracking code.
    """
    client = GWSClient(check_auth_on_init=True)
    unread_messages = client.list_unread_messages(max_results=limit, query=query)
    
    items: list[TriageItem] = []
    for m in unread_messages:
        mid = m.get("id")
        if not mid:
            continue
        try:
            msg = client.get_message(mid)
            item = analyze_email(msg)
            items.append(item)
        except Exception:
            continue
            
    batch = TriageBatch(total_unread=len(items), items=items)
    return batch.model_dump()


def apply_agent_decisions(
    decisions: dict[str, Any],
    client: GWSClient | None = None,
) -> dict[str, Any]:
    """Apply structured actions returned by AGY or an AI reasoning agent.
    
    Expected schema for decisions:
    {
        "mark_as_read": ["message_id_1", "message_id_2"],
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

    # 3. Process mark as read
    for mid in decisions.get("mark_as_read", []):
        success = client.mark_as_read(mid)
        results["marked_read"][mid] = success

    return results
