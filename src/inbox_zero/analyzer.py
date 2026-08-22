"""Deterministic analysis engine for emails: action items, summaries, dates, and suggested replies."""

from __future__ import annotations

import re
from inbox_zero.models import CalendarEventSuggestion, EmailAttachment, EmailMessage, Sender, TriageItem
from inbox_zero.parser import truncate_preview


# Common date and time regex patterns
DATE_PATTERNS = [
    # Full dates e.g. Friday, August 21, 2026 or Aug 21, 2026
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?",
    # Day & Time e.g. Wednesday, Sept. 9 at 9:30am or Friday, Sept. 18, from 4:30-6:30pm
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^,\n\.]*?(?:January|February|March|April|May|June|July|August|September|October|November|December|Sept|Aug|Sep)\.?\s+\d{1,2}(?:[^\.\n]{0,40}?\b\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))?",
    # Date formats e.g. 8/21/2026 or 08/21/26
    r"\b\d{1,2}/\d{1,2}/(?:20\d{2}|\d{2})\b",
]

# Action item trigger phrases
ACTION_TRIGGERS = [
    r"please\s+([^\.\n\?!]+)",
    r"don't\s+forget\s+to\s+([^\.\n\?!]+)",
    r"make\s+sure\s+to\s+([^\.\n\?!]+)",
    r"remember\s+to\s+([^\.\n\?!]+)",
    r"reply\s+by\s+([^\.\n\?!]+)",
    r"let\s+me\s+know\s+([^\.\n\?!]+)",
    r"sign\s+up\s+([^\.\n\?!]+)",
    r"fill\s+out\s+([^\.\n\?!]+)",
    r"bring\s+([^\.\n\?!]+)",
    r"due\s+([^\.\n\?!]+)",
    r"register\s+([^\.\n\?!]+)",
]

# Boilerplate phrases to ignore in action items
DISCLAIMER_PHRASES = [
    "destroy all copies",
    "contact the sender by reply",
    "intended only for the person",
    "confidential and/or privileged",
    "unauthorized review",
    "acceptable use policies",
    "participating in one or more classes using canvas",
    "turn off email notifications",
    "get outlook for android",
    "unsubscribe",
    "click here",
    "view in browser",
    "all rights reserved",
]

AUTOMATED_SENDER_PATTERNS = [
    "noreply",
    "no-reply",
    "donotreply",
    "notifications@",
    "mailer-daemon",
    "alert@",
    "news@",
]


def is_automated_sender(sender_email: str) -> bool:
    """Check if the sender is an automated bot or newsletter."""
    lower = sender_email.lower()
    return any(p in lower for p in AUTOMATED_SENDER_PATTERNS)


def is_disclaimer(text: str) -> bool:
    """Check if a line or action item is standard email disclaimer boilerplate."""
    lower = text.lower()
    return any(p in lower for p in DISCLAIMER_PHRASES)


def categorize_email(subject: str, sender_email: str, sender_name: str, body: str) -> str:
    """Categorize the email based on domain, sender, and content keywords."""
    combined = f"{subject} {sender_email} {sender_name} {body}".lower()

    if any(k in combined for k in ["ayso", "soccer", "practice", "game schedule", "coach"]):
        return "Sports & Activities"
    if any(k in combined for k in ["nb27", "school", "shabonee", "math", "chorus", "instructure", "canvas", "teacher", "grade"]):
        return "School & Kids"
    if any(k in combined for k in ["newsletter", "digest", "no-reply", "noreply", "announcement", "updates"]):
        return "Newsletters & Updates"
    if any(k in combined for k in ["invoice", "receipt", "order", "payment", "bank", "statement"]):
        return "Finance & Bills"
    if any(k in combined for k in ["security alert", "verify", "password", "sign-in"]):
        return "Security & Account"
    return "General"


def extract_dates_and_events(subject: str, body: str, ref_date_str: str | None = None) -> list[CalendarEventSuggestion]:
    """Extract dates and calendar events mentioned in subject and body."""
    events: list[CalendarEventSuggestion] = []
    seen_summaries: set[str] = set()

    lines = body.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 8 or is_disclaimer(line_clean):
            continue

        for pattern in DATE_PATTERNS:
            matches = list(re.finditer(pattern, line_clean, re.IGNORECASE))
            for match in matches:
                date_text = match.group(0).strip()
                # Check for time attached to this line
                time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)(?:\s*-\s*\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))?)\b", line_clean, re.IGNORECASE)
                time_info = time_match.group(0) if time_match else ""

                # Build event title
                clean_snippet = re.sub(r"\s+", " ", line_clean)
                if len(clean_snippet) > 100:
                    clean_snippet = clean_snippet[:100].rsplit(" ", 1)[0] + "..."

                event_title = f"{clean_snippet}"

                # Extract location if mentioned (e.g. 'at Wood Oaks Field 3' or 'in School Gym')
                loc = None
                at_match = re.search(r"\bat\s+([A-Z][A-Za-z0-9\s,\-]{2,40}?)(?:\.|\s+in\b|\s+on\b|$)", line_clean)
                if at_match and not re.search(r"^\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)", at_match.group(1).strip(), re.IGNORECASE):
                    loc = at_match.group(1).strip().rstrip(".,")
                if not loc:
                    in_match = re.search(r"\bin\s+(?:the\s+)?([A-Z][A-Za-z0-9\s,\-]{2,40}?)(?:\.|\s+on\b|\s+at\b|$)", line_clean)
                    if in_match:
                        loc = in_match.group(1).strip().rstrip(".,")

                if date_text not in seen_summaries:
                    seen_summaries.add(date_text)
                    events.append(
                        CalendarEventSuggestion(
                            summary=event_title,
                            start_time=date_text + (f" ({time_info})" if time_info and time_info not in date_text else ""),
                            description=line_clean,
                            location=loc,
                        )
                    )

    return events[:8]


def extract_action_items(body: str) -> list[str]:
    """Extract actionable tasks from the email body text."""
    actions: list[str] = []
    seen: set[str] = set()

    # Look for bullet points with action items first
    for line in body.splitlines():
        line_s = line.strip()
        if is_disclaimer(line_s):
            continue
        if (line_s.startswith("- [ ]") or line_s.startswith("- ") or line_s.startswith("* ") or line_s.startswith("• ")) and len(line_s) > 10:
            item = line_s.lstrip("-*• [ ]").strip()
            item = re.sub(r"\s+", " ", item).rstrip(".:,;")
            if 10 < len(item) < 120 and item.lower() not in seen and not is_disclaimer(item):
                seen.add(item.lower())
                actions.append(item)

    for pattern in ACTION_TRIGGERS:
        for match in re.finditer(pattern, body, re.IGNORECASE):
            action_text = match.group(0).strip()
            if is_disclaimer(action_text):
                continue
            # Clean up action text
            action_text = re.sub(r"\s+", " ", action_text)
            action_text = action_text.rstrip(".:,;")
            lower_val = action_text.lower()
            
            # Avoid adding substring subsets of already added actions
            if 10 < len(action_text) < 120 and not any(lower_val in existing for existing in seen):
                seen.add(lower_val)
                actions.append(action_text)

    return actions[:8]


def suggest_replies(message: EmailMessage, category: str) -> list[str]:
    """Generate contextual quick-reply drafts when relevant."""
    # Don't suggest replies for automated bot accounts or newsletters
    if is_automated_sender(message.sender.email):
        return []

    body_lower = message.body_text.lower()
    subject_lower = message.subject.lower()
    sender_name = message.sender.name or "there"

    # If it's a short thank-you acknowledgement reply from family, no reply needed
    if ("thank you" in body_lower or "thanks" in body_lower) and len(message.body_text.strip()) < 150:
        return []

    replies: list[str] = []

    # Teacher / School update
    if category == "School & Kids" or "nb27.org" in message.sender.email:
        first_name = sender_name.split()[0] if sender_name else "Teacher"
        replies.append(f"Thank you so much {sender_name}! We really appreciate the update and are looking forward to a great year.")
        replies.append(f"Thanks {first_name}, glad to hear it! Looking forward to seeing you at Back-to-School Night.")

    # Sports / Coach update
    elif category == "Sports & Activities" or "coach" in body_lower or "ayso" in body_lower:
        replies.append(f"Thanks Coach! We have the schedule noted and all gear ready for practice.")
        replies.append(f"Thank you for the update! Looking forward to a fun season.")

    # General direct inquiries
    else:
        replies.append("Thanks for reaching out! Received and noted.")
        replies.append("Thank you for the update! Let me know if you need anything else from our end.")

    return replies[:3]


def clean_subject(subject: str) -> str:
    """Remove leading Re:, Fw:, Fwd: prefixes from subject."""
    clean = subject.strip()
    changed = True
    while changed:
        changed = False
        for prefix in ["re:", "fw:", "fwd:"]:
            if clean.lower().startswith(prefix):
                clean = clean[len(prefix):].strip()
                changed = True
    return clean or "(No Subject)"


def generate_title_and_summary(message: EmailMessage) -> tuple[str, str]:
    """Generate punchy title summary and 2-3 sentence overview deterministically."""
    subject = message.subject.strip()
    body = message.body_text.strip()

    title_summary = clean_subject(subject)

    valid_lines = [line.strip() for line in body.splitlines() if line.strip() and not is_disclaimer(line)]
    clean_body = " ".join(valid_lines)

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_body) if s.strip() and len(s) > 15 and not is_disclaimer(s)]
    if sentences:
        brief_summary = " ".join(sentences[:3])
    else:
        brief_summary = truncate_preview(clean_body, 200) or "No message content provided."

    return title_summary, brief_summary


def analyze_thread(messages: list[EmailMessage]) -> TriageItem:
    """Perform comprehensive triage analysis of a conversation thread."""
    if not messages:
        raise ValueError("Cannot analyze empty thread messages")

    root = messages[0]
    latest = messages[-1]

    # Collect distinct senders in chronological order of appearance
    senders: list[Sender] = []
    seen_emails: set[str] = set()
    for m in messages:
        if m.sender.email.lower() not in seen_emails:
            seen_emails.add(m.sender.email.lower())
            senders.append(m.sender)

    title_summary = clean_subject(root.subject)

    # Collect all attachments across thread
    all_attachments: list[EmailAttachment] = []
    for m in messages:
        all_attachments.extend(m.attachments)

    # Conversation summary
    if len(messages) == 1:
        _, brief_summary = generate_title_and_summary(latest)
    else:
        parts: list[str] = []
        for m in messages:
            s_name = m.sender.name or m.sender.email.split("@")[0]
            _, m_sum = generate_title_and_summary(m)
            parts.append(f"{s_name}: {m_sum}")
        brief_summary = " | ".join(parts)

    att_texts = [f"{att.filename}: {att.extracted_text}" for att in all_attachments if att.extracted_text]
    combined_body = "\n\n".join(m.body_text for m in messages)
    if att_texts:
        combined_body += "\n\n" + "\n\n".join(att_texts)

    category = categorize_email(
        root.subject,
        latest.sender.email,
        latest.sender.name or root.sender.name or "",
        combined_body,
    )

    # Extract all action items across the thread (deduplicated)
    action_items: list[str] = []
    seen_actions: set[str] = set()
    for m in messages:
        for action in extract_action_items(m.body_text):
            if action.lower() not in seen_actions:
                seen_actions.add(action.lower())
                action_items.append(action)
        for att in m.attachments:
            if att.extracted_text:
                for action in extract_action_items(att.extracted_text):
                    if action.lower() not in seen_actions:
                        seen_actions.add(action.lower())
                        action_items.append(f"[📎 {att.filename}] {action}")

    # Extract all calendar events across the thread (deduplicated)
    calendar_events: list[CalendarEventSuggestion] = []
    seen_events: set[str] = set()
    for m in messages:
        for ev in extract_dates_and_events(m.subject, m.body_text, m.date):
            if ev.summary.lower() not in seen_events:
                seen_events.add(ev.summary.lower())
                calendar_events.append(ev)
        for att in m.attachments:
            if att.extracted_text:
                for ev in extract_dates_and_events(f"{att.filename}: {m.subject}", att.extracted_text, m.date):
                    if ev.summary.lower() not in seen_events:
                        seen_events.add(ev.summary.lower())
                        calendar_events.append(ev)

    # Suggested replies targeting the latest message in thread
    suggested_replies = suggest_replies(latest, category)

    return TriageItem(
        message_id=latest.id,
        thread_id=root.thread_id or latest.thread_id,
        sender_name=latest.sender.name or root.sender.name,
        sender_email=latest.sender.email,
        date=latest.date,
        subject=root.subject,
        title_summary=title_summary,
        brief_summary=brief_summary,
        category=category,
        action_items=action_items,
        calendar_events=calendar_events,
        suggested_replies=suggested_replies,
        attachments=all_attachments,
        raw_body_preview=truncate_preview(latest.body_text, 250),
        senders=senders,
        messages=messages,
        message_count=len(messages),
        unread_count=sum(1 for m in messages if m.is_unread),
    )


def analyze_email(message: EmailMessage) -> TriageItem:
    """Perform comprehensive analysis of an individual email message."""
    return analyze_thread([message])
