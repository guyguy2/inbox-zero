"""Bridge utilities for integrating inbox-zero with Antigravity (AGY) and AI agents."""

from __future__ import annotations

import json
from typing import Any
from inbox_zero.analyzer import analyze_email, analyze_thread
from inbox_zero.client import GWSClient
from inbox_zero.models import TriageBatch, TriageItem


def prepare_agent_triage_payload(limit: int = 20, query: str = "is:unread") -> dict[str, Any]:
    """Fetch unread email threads, sanitize them, and format a structured prompt payload for an AI agent.
    
    This function is used by AGY or headless agents to get pre-filtered,
    privacy-safe email thread text without raw HTML junk or tracking code.
    """
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
