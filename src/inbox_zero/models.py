"""Data models for inbox-zero."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class Sender(BaseModel):
    """Email sender information."""
    name: str | None = None
    email: str

    @classmethod
    def from_gws(cls, raw: Any) -> Sender:
        """Parse sender from gws output."""
        if isinstance(raw, dict):
            return cls(
                name=raw.get("name"),
                email=raw.get("email") or raw.get("address") or "unknown@unknown.com",
            )
        if isinstance(raw, str):
            # Parse 'Name <email@domain>' or just 'email@domain'
            if "<" in raw and raw.endswith(">"):
                parts = raw.split("<", 1)
                return cls(name=parts[0].strip().strip('"'), email=parts[1].rstrip(">").strip())
            return cls(email=raw.strip())
        return cls(email="unknown@unknown.com")


class CalendarEventSuggestion(BaseModel):
    """A suggested calendar event extracted from an email."""
    summary: str = Field(description="Event title / subject")
    start_time: str = Field(description="ISO-8601 formatted start datetime with timezone or YYYY-MM-DD")
    end_time: str | None = Field(default=None, description="ISO-8601 formatted end datetime")
    description: str | None = Field(default=None, description="Event description or notes")
    location: str | None = Field(default=None, description="Event location or link")


class EmailMessage(BaseModel):
    """Raw/normalized email message from Google Workspace."""
    id: str
    thread_id: str
    subject: str = "(No Subject)"
    sender: Sender
    date: str
    body_text: str = ""
    body_html: str | None = None
    snippet: str | None = None
    is_unread: bool = True


class TriageItem(BaseModel):
    """Enriched triage analysis for an individual email."""
    message_id: str
    thread_id: str
    sender_name: str | None = None
    sender_email: str
    date: str
    subject: str
    title_summary: str = Field(description="One-line punchy summary")
    brief_summary: str = Field(description="2-3 sentence overview of content")
    category: str = Field(default="General", description="Category e.g. School, Sports, Work, Newsletter")
    action_items: list[str] = Field(default_factory=list, description="Action items requiring user attention")
    calendar_events: list[CalendarEventSuggestion] = Field(
        default_factory=list, description="Extracted dates/events"
    )
    raw_body_preview: str = ""


class TriageBatch(BaseModel):
    """A collection of triaged items."""
    total_unread: int
    items: list[TriageItem] = Field(default_factory=list)
