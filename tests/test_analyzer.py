import pytest
from inbox_zero.analyzer import (
    categorize_email,
    extract_action_items,
    extract_dates_and_events,
    suggest_replies,
    is_disclaimer,
    is_automated_sender,
    analyze_email,
    analyze_thread,
)
from inbox_zero.models import EmailAttachment, EmailMessage, Sender


def test_categorization():
    assert categorize_email("AYSO Game Schedule", "coach@ayso.org", "Coach Mike", "Practice on Thursday") == "Sports & Activities"
    assert categorize_email("5th Grade Math", "teacher@nb27.org", "Mrs. Patel", "Math homework") == "School & Kids"
    assert categorize_email("Weekly Newsletter", "news@shabonee.org", "School", "Digest") == "School & Kids"
    assert categorize_email("Invoice for Order #123", "billing@aws.com", "AWS", "Your bill is $50") == "Finance & Bills"
    assert categorize_email("Security Alert: New Sign-in", "security@google.com", "Google", "Sign-in alert") == "Security & Account"
    assert categorize_email("Hello friend", "friend@gmail.com", "Friend", "How are you?") == "General"


def test_is_disclaimer():
    assert is_disclaimer("If you are not the intended recipient, please contact the sender and destroy all copies.") is True
    assert is_disclaimer("This email message is intended only for the person to whom it is addressed.") is True
    assert is_disclaimer("Get Outlook for Android") is True
    assert is_disclaimer("Please bring your soccer ball tomorrow.") is False


def test_is_automated_sender():
    assert is_automated_sender("noreply@nb27.org") is True
    assert is_automated_sender("notifications@instructure.com") is True
    assert is_automated_sender("teacher@nb27.org") is False


def test_action_item_extraction():
    body = (
        "Please bring shin guards and a soccer ball to practice.\n"
        "Also don't forget to fill out the emergency contact form.\n"
        "- [ ] Pay the activity registration fee\n"
        "* Submit the health form\n"
        "• Bring 2 water bottles\n"
        "If you are not the intended recipient, please contact the sender and destroy all copies.\n"
    )
    actions = extract_action_items(body)
    assert any("shin guards" in a.lower() for a in actions)
    assert any("emergency contact form" in a.lower() for a in actions)
    assert any("registration fee" in a.lower() for a in actions)
    assert any("health form" in a.lower() for a in actions)
    assert any("water bottles" in a.lower() for a in actions)
    # Ensure disclaimer is excluded
    assert not any("destroy all copies" in a.lower() for a in actions)


def test_date_extraction_various_formats():
    body = (
        "First practice: Thursday, August 27, 2026 from 5:00-6:30pm at Wood Oaks Field 3.\n"
        "Back to school night is Wednesday, Sept. 9 at 9:30am.\n"
        "Meeting on 08/21/2026.\n"
    )
    events = extract_dates_and_events("Fall Schedule", body)
    assert len(events) >= 2
    assert any("August 27" in e.start_time or "5:00" in e.start_time for e in events)
    assert any("Sept" in e.start_time or "September" in e.start_time for e in events)


def test_suggest_replies_teacher():
    msg = EmailMessage(
        id="123",
        thread_id="t1",
        subject="Ben's First Day",
        sender=Sender(name="Roshani Patel", email="patel.r@nb27.org"),
        date="Fri, 21 Aug 2026",
        body_text="Ben had a wonderful first day in 5th grade honors math!",
    )
    replies = suggest_replies(msg, "School & Kids")
    assert len(replies) > 0
    assert any("Roshani" in r or "Thank you" in r for r in replies)


def test_suggest_replies_sports_coach():
    msg = EmailMessage(
        id="125",
        thread_id="t3",
        subject="AYSO Soccer Info",
        sender=Sender(name="Coach Mike", email="mike@ayso.org"),
        date="Fri, 21 Aug 2026",
        body_text="Welcome to the soccer team! First practice is next Thursday.",
    )
    replies = suggest_replies(msg, "Sports & Activities")
    assert len(replies) > 0
    assert any("Coach" in r or "practice" in r for r in replies)


def test_suggest_replies_automated_skipped():
    msg = EmailMessage(
        id="124",
        thread_id="t2",
        subject="Weekly District Newsletter",
        sender=Sender(name="School District", email="noreply@nb27.org"),
        date="Fri, 21 Aug 2026",
        body_text="Here is the newsletter for this week.",
    )
    replies = suggest_replies(msg, "Newsletters & Updates")
    assert len(replies) == 0


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
    assert len(triage.suggested_replies) > 0


def test_analyze_thread_multi_messages():
    msg1 = EmailMessage(
        id="m1",
        thread_id="t1",
        subject="Liam and Ben's start to the year",
        sender=Sender(name="Stefani Wiemann", email="wiemann.s@nb27.org"),
        date="Fri, 21 Aug 2026 12:48:42 -0500",
        body_text="Good morning! Great having Liam and Ben in class. Back to school night is Sept 9 at 9:30am. Please bring notebook.",
    )
    msg2 = EmailMessage(
        id="m2",
        thread_id="t1",
        subject="Re: Liam and Ben's start to the year",
        sender=Sender(name="Hanni", email="hanni1976.hf@gmail.com"),
        date="Fri, 21 Aug 2026 20:25:17 +0000",
        body_text="Thank you for your email! We will make sure to bring the notebook.",
    )
    triage = analyze_thread([msg1, msg2])
    assert triage.thread_id == "t1"
    assert triage.message_id == "m2"
    assert triage.message_count == 2
    assert len(triage.senders) == 2
    assert triage.title_summary == "Liam and Ben's start to the year"
    assert "Stefani Wiemann:" in triage.brief_summary
    assert "Hanni:" in triage.brief_summary
    assert any("notebook" in a.lower() for a in triage.action_items)
    assert any("Sept 9" in ev.start_time or "September" in ev.start_time for ev in triage.calendar_events)


def test_analyze_thread_with_attachments():
    att1 = EmailAttachment(
        filename="field_trip_permission.pdf",
        mime_type="application/pdf",
        size_bytes=24000,
        extracted_text="Field trip to Science Museum on Friday, October 16 at 9:00am. Please sign and return by Wednesday.",
    )
    msg = EmailMessage(
        id="m_att",
        thread_id="t_att",
        subject="Field Trip Notice",
        sender=Sender(name="Teacher", email="teacher@school.org"),
        date="Fri, 21 Aug 2026",
        body_text="Dear Parents, please see attached permission slip.",
        attachments=[att1],
    )
    triage = analyze_thread([msg])
    assert len(triage.attachments) == 1
    assert triage.attachments[0].filename == "field_trip_permission.pdf"
    # Action item extracted from PDF attachment
    assert any("sign" in a.lower() for a in triage.action_items)
    # Calendar date extracted from PDF attachment
    assert any("October 16" in ev.start_time or "10-16" in ev.start_time or "Science Museum" in ev.summary for ev in triage.calendar_events)


