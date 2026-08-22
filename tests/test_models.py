import json
import pytest
from inbox_zero.models import (
    Sender,
    EmailMessage,
    CalendarEventSuggestion,
    TriageItem,
    TriageBatch,
)


def test_sender_from_dict():
    s = Sender.from_gws({"name": "Jane Doe", "email": "jane@example.com"})
    assert s.name == "Jane Doe"
    assert s.email == "jane@example.com"


def test_sender_from_dict_address_fallback():
    s = Sender.from_gws({"address": "fallback@example.com"})
    assert s.name is None
    assert s.email == "fallback@example.com"


def test_sender_from_formatted_string():
    s = Sender.from_gws('"John Smith" <john@example.com>')
    assert s.name == "John Smith"
    assert s.email == "john@example.com"


def test_sender_from_plain_string():
    s = Sender.from_gws("plain@example.com")
    assert s.name is None
    assert s.email == "plain@example.com"


def test_sender_from_invalid():
    s = Sender.from_gws(None)
    assert s.email == "unknown@unknown.com"


def test_calendar_event_suggestion_model():
    event = CalendarEventSuggestion(
        summary="Team Meeting",
        start_time="2026-08-25T10:00:00-05:00",
        end_time="2026-08-25T11:00:00-05:00",
        description="Discuss roadmap",
        location="Room 101",
    )
    assert event.summary == "Team Meeting"
    assert event.location == "Room 101"
    dumped = event.model_dump()
    assert dumped["start_time"] == "2026-08-25T10:00:00-05:00"


def test_triage_batch_json_serialization():
    msg1 = EmailMessage(
        id="msg_001",
        thread_id="thread_001",
        subject="Weekly Update",
        sender=Sender(name="Teacher", email="teacher@nb27.org"),
        date="Fri, 21 Aug 2026",
        body_text="First message",
    )
    msg2 = EmailMessage(
        id="msg_002",
        thread_id="thread_001",
        subject="Re: Weekly Update",
        sender=Sender(name="Parent", email="parent@example.com"),
        date="Fri, 21 Aug 2026",
        body_text="Second message",
    )
    item = TriageItem(
        message_id="msg_002",
        thread_id="thread_001",
        sender_name="Teacher",
        sender_email="teacher@nb27.org",
        date="Fri, 21 Aug 2026",
        subject="Weekly Update",
        title_summary="Weekly Classroom Update",
        brief_summary="Everything went well this week.",
        category="School & Kids",
        action_items=["Sign permission slip"],
        calendar_events=[
            CalendarEventSuggestion(summary="Field Trip", start_time="2026-09-01")
        ],
        suggested_replies=["Thank you for the update!"],
        raw_body_preview="Clean body preview...",
        senders=[Sender(name="Teacher", email="teacher@nb27.org"), Sender(name="Parent", email="parent@example.com")],
        messages=[msg1, msg2],
        message_count=2,
        unread_count=2,
    )
    batch = TriageBatch(total_unread=1, total_messages=2, items=[item])
    json_str = batch.model_dump_json()
    data = json.loads(json_str)
    assert data["total_unread"] == 1
    assert data["total_messages"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["message_count"] == 2
    assert len(data["items"][0]["messages"]) == 2
    assert len(data["items"][0]["senders"]) == 2
    assert data["items"][0]["action_items"] == ["Sign permission slip"]
