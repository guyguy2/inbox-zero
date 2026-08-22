import pytest
from inbox_zero.analyzer import categorize_email, extract_action_items, extract_dates_and_events, analyze_email
from inbox_zero.models import EmailMessage, Sender


def test_categorization():
    assert categorize_email("AYSO Game Schedule", "coach@ayso.org", "Coach Mike", "Practice on Thursday") == "Sports & Activities"
    assert categorize_email("5th Grade Math", "teacher@nb27.org", "Mrs. Patel", "Math homework") == "School & Kids"
    assert categorize_email("Weekly Newsletter", "news@shabonee.org", "School", "Digest") == "School & Kids"
    assert categorize_email("Invoice for Order #123", "billing@aws.com", "AWS", "Your bill is $50") == "Finance & Bills"


def test_action_item_extraction():
    body = "Please bring shin guards and a soccer ball to practice. Also don't forget to fill out the emergency contact form."
    actions = extract_action_items(body)
    assert any("shin guards" in a.lower() for a in actions)
    assert any("emergency contact form" in a.lower() for a in actions)


def test_date_extraction():
    body = "The chorus meets on Tuesday at 8:00 AM. Our first rehearsal is August 25, 2026."
    events = extract_dates_and_events("Chorus Schedule", body)
    assert len(events) >= 1
    assert any("August 25" in e.start_time or "Tuesday" in e.start_time for e in events)


def test_analyze_email_full():
    msg = EmailMessage(
        id="12345",
        thread_id="thread1",
        subject="AYSO Soccer Info",
        sender=Sender(name="Coach Mike", email="mike@ayso.org"),
        date="Fri, 21 Aug 2026 12:00:00 -0500",
        body_text="Welcome to AYSO! Practice is on Thursday, August 28 at 5:00 PM. Please bring a ball.",
    )
    triage = analyze_email(msg)
    assert triage.category == "Sports & Activities"
    assert triage.message_id == "12345"
    assert len(triage.action_items) > 0
    assert len(triage.calendar_events) > 0
