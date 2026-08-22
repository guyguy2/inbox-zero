from __future__ import annotations

import base64
import io
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from bs4 import BeautifulSoup
import dateutil.parser
import pypdf


def parse_email_date(date_str: str | None) -> datetime:
    """Parse an email date string (RFC 2822 or ISO) into a timezone-aware datetime for robust sorting."""
    if not date_str or not str(date_str).strip():
        return datetime.min.replace(tzinfo=timezone.utc)
    raw = str(date_str).strip()
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    return datetime.min.replace(tzinfo=timezone.utc)


def decode_base64url(s: str) -> bytes:
    """Decode a base64url-encoded string (RFC 4648) safely."""
    if not s:
        return b""
    s_clean = s.replace("-", "+").replace("_", "/")
    missing_padding = len(s_clean) % 4
    if missing_padding:
        s_clean += "=" * (4 - missing_padding)
    try:
        return base64.b64decode(s_clean)
    except Exception:
        return b""


def extract_attachment_metadata(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Recursively discover all attachment parts in a Gmail message payload."""
    attachments: list[dict[str, Any]] = []

    def walk_parts(part: dict[str, Any]) -> None:
        filename = part.get("filename", "").strip()
        body = part.get("body", {})
        att_id = body.get("attachmentId")
        inline_data = body.get("data")
        size = body.get("size", 0)
        mime_type = part.get("mimeType", "application/octet-stream")

        if filename and (att_id or inline_data or size > 0):
            attachments.append({
                "id": att_id,
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": size,
                "inline_data": inline_data,
            })

        for sub_part in part.get("parts", []):
            walk_parts(sub_part)

    if isinstance(payload, dict):
        walk_parts(payload)
    return attachments


def parse_attachment_bytes(data: bytes, filename: str, mime_type: str = "") -> str:
    """Extract plain text from an attachment's raw byte stream (PDF, text, CSV, HTML, etc.)."""
    if not data:
        return ""
    fn_lower = filename.lower()
    mime_lower = mime_type.lower()

    # PDF documents
    if fn_lower.endswith(".pdf") or "pdf" in mime_lower:
        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages_text: list[str] = []
            for page in reader.pages:
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(txt.strip())
            return "\n\n".join(pages_text).strip()
        except Exception:
            return ""

    # Plain text, CSV, Markdown, JSON, XML, log files
    if (
        fn_lower.endswith((".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".log", ".yaml", ".yml"))
        or mime_lower.startswith("text/")
        or "json" in mime_lower
        or "xml" in mime_lower
        or "csv" in mime_lower
    ):
        try:
            text = data.decode("utf-8", errors="replace")
            if fn_lower.endswith((".html", ".htm")) or "html" in mime_lower:
                return clean_html_to_text(text)
            return text.strip()
        except Exception:
            try:
                text = data.decode("latin-1", errors="replace")
                return text.strip()
            except Exception:
                return ""

    return ""


def clean_html_to_text(html_content: str) -> str:
    """Convert raw HTML email to clean, readable plain text."""
    if not html_content or not html_content.strip():
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script, style, head, noscript, and meta elements
    for element in soup(["script", "style", "head", "meta", "noscript", "svg"]):
        element.decompose()

    # Replace breaks and paragraphs with newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")

    for p in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"]):
        p.insert_before("\n")
        p.insert_after("\n")

    # Extract text
    text = soup.get_text()

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines()]
    # Collapse consecutive empty lines
    cleaned_lines: list[str] = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned_lines.append("")
                prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False

    cleaned_text = "\n".join(cleaned_lines).strip()
    return cleaned_text


def extract_clean_email_body(body_text: str | None, body_html: str | None) -> str:
    """Extract the best text representation from an email message.
    
    If body_text is empty or a placeholder (e.g. <!--placeholder-->),
    fall back to parsing body_html.
    """
    text = (body_text or "").strip()
    
    # Check if text is just a placeholder or too minimal
    is_placeholder = (
        not text
        or text == "<!--placeholder-->"
        or text.startswith("<!--") and len(text) < 50
    )

    if is_placeholder and body_html:
        html_clean = clean_html_to_text(body_html)
        if html_clean:
            return html_clean

    if not text and body_html:
        return clean_html_to_text(body_html)

    # Clean up standard text formatting
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_preview(text: str, max_chars: int = 300) -> str:
    """Return a single-line or shortened preview of text."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[:max_chars].rstrip() + "..."


TIME_SPAN_PATTERN = r"\b(?:from\s+)?(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)|\d{1,2}:\d{2})\s*(?:-|–|—|\bto\b)\s*(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?|\d{1,2}:\d{2})\b"


def parse_time_span(time_str: str) -> tuple[int, int, int, int] | None:
    """Extract start and end hour/minute from a time range like '5:00-6:30pm' or '9:00am - 10:00am'."""
    if not time_str:
        return None

    for match in re.finditer(
        r"\b(\d{1,2}(?::\d{2})?)\s*(am|pm|a\.m\.|p\.m\.)?\s*(?:-|–|—|\bto\b)\s*(\d{1,2}(?::\d{2})?)\s*(am|pm|a\.m\.|p\.m\.)?\b",
        time_str,
        re.IGNORECASE,
    ):
        t1_str, t1_ampm = match.group(1), match.group(2)
        t2_str, t2_ampm = match.group(3), match.group(4)
        has_time_indicator = bool(t1_ampm or t2_ampm or ":" in t1_str or ":" in t2_str)
        if not has_time_indicator:
            continue

        effective_t1_ampm = t1_ampm or t2_ampm
        effective_t2_ampm = t2_ampm or t1_ampm

        def to_h_m(val: str, ampm: str | None) -> tuple[int, int] | None:
            parts = val.split(":")
            try:
                h = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 else 0
            except ValueError:
                return None
            if h < 0 or h > 23 or m < 0 or m > 59:
                return None
            ampm_str = (ampm or "").lower().replace(".", "")
            if ampm_str == "pm" and h < 12:
                h += 12
            elif ampm_str == "am" and h == 12:
                h = 0
            elif not ampm_str and h < 8:
                h += 12
            if h < 0 or h > 23 or m < 0 or m > 59:
                return None
            return h, m

        res1 = to_h_m(t1_str, effective_t1_ampm)
        res2 = to_h_m(t2_str, effective_t2_ampm)
        if res1 and res2:
            return res1[0], res1[1], res2[0], res2[1]

    return None


def parse_single_time(time_str: str) -> tuple[int, int] | None:
    """Extract a single time (hour, minute) from a string like '9:30am' or '5:00 PM' or '14:30'."""
    if not time_str:
        return None

    match = re.search(r"\b(\d{1,2}(?::\d{2})?)\s*(am|pm|a\.m\.|p\.m\.)\b", time_str, re.IGNORECASE)
    if match:
        val = match.group(1)
        ampm = match.group(2).lower().replace(".", "")
        parts = re.sub(r"[^\d:]", "", val).split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            return None
        if ampm == "pm" and h < 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        return h, m

    match_24 = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", time_str)
    if match_24:
        return int(match_24.group(1)), int(match_24.group(2))

    return None


def normalize_event_datetimes(
    start_str: str,
    end_str: str | None = None,
    ref_date: datetime | str | None = None,
    default_duration_minutes: int = 30,
) -> tuple[str, str]:
    """Normalize raw or natural language date/time strings into valid ISO-8601 datetimes with timezone offset.
    
    Guarantees both a start and end datetime string suitable for Google Calendar (gws calendar +insert).
    If end time is unknown or omitted, defaults to 30 minutes after start time.
    """
    if not start_str or not start_str.strip():
        raise ValueError("start_time cannot be empty")

    start_raw = start_str.strip()
    end_raw = (end_str or "").strip()
    default_delta = timedelta(minutes=default_duration_minutes)

    # Always assume local system timezone
    local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    default_tz = local_tz

    # Determine reference year from email date if provided
    ref_year = None
    if isinstance(ref_date, str):
        parsed_ref = parse_email_date(ref_date)
        if parsed_ref != datetime.min.replace(tzinfo=timezone.utc):
            ref_year = parsed_ref.year
    elif isinstance(ref_date, datetime):
        ref_year = ref_date.year

    if not ref_year or ref_year <= 1900:
        ref_year = datetime.now().year

    # 1. If start_str is already a valid ISO-8601 with date & time (e.g. 2026-08-27T17:00:00 or 2026-08-27T17:00:00-05:00)
    if "T" in start_raw or (len(start_raw) >= 19 and start_raw[10] in (" ", "T")):
        try:
            dt_start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            if dt_start.tzinfo is None:
                dt_start = dt_start.replace(tzinfo=default_tz)
            if end_raw:
                try:
                    dt_end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
                    if dt_end.tzinfo is None:
                        dt_end = dt_end.replace(tzinfo=dt_start.tzinfo)
                except Exception:
                    dt_end = dt_start + default_delta
            else:
                dt_end = dt_start + default_delta
            if dt_end <= dt_start:
                dt_end = dt_start + default_delta
            return dt_start.isoformat(), dt_end.isoformat()
        except ValueError:
            pass

    # 2. Check for time span in start_raw
    span = parse_time_span(start_raw)

    # Clean string for dateutil base date parsing
    clean_date_str = re.sub(r"\bSept\b\.?", "Sep", start_raw, flags=re.IGNORECASE)
    clean_date_str = re.sub(TIME_SPAN_PATTERN, "", clean_date_str, flags=re.IGNORECASE)
    clean_date_str = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)\b", "", clean_date_str, flags=re.IGNORECASE)
    clean_date_str = re.sub(r"\s*\([^)]*\)", "", clean_date_str)
    clean_date_str = re.sub(r"\s+at\s+[A-Z0-9].*$", "", clean_date_str)
    clean_date_str = clean_date_str.strip()

    default_dt = datetime(ref_year, 1, 1, 9, 0, 0, tzinfo=default_tz)

    try:
        parsed_base = dateutil.parser.parse(clean_date_str, fuzzy=True, default=default_dt)
    except Exception:
        try:
            parsed_base = dateutil.parser.parse(start_raw, fuzzy=True, default=default_dt)
        except Exception:
            parsed_base = default_dt

    if parsed_base.tzinfo is None:
        parsed_base = parsed_base.replace(tzinfo=default_tz)

    if span:
        h1, m1, h2, m2 = span
        dt_start = parsed_base.replace(hour=h1, minute=m1, second=0, microsecond=0)
        dt_end = parsed_base.replace(hour=h2, minute=m2, second=0, microsecond=0)
        if dt_end <= dt_start:
            dt_end = dt_start + default_delta
    else:
        single_time = parse_single_time(start_raw)
        if single_time:
            h, m = single_time
            dt_start = parsed_base.replace(hour=h, minute=m, second=0, microsecond=0)
        else:
            # Default to 9:00 AM for date-only events
            dt_start = parsed_base.replace(hour=9, minute=0, second=0, microsecond=0)

        if end_raw:
            try:
                end_time = parse_single_time(end_raw)
                if end_time:
                    eh, em = end_time
                    dt_end = dt_start.replace(hour=eh, minute=em, second=0, microsecond=0)
                else:
                    dt_end = dateutil.parser.parse(end_raw, fuzzy=True, default=dt_start)
                    if dt_end.tzinfo is None:
                        dt_end = dt_end.replace(tzinfo=dt_start.tzinfo)
            except Exception:
                dt_end = dt_start + default_delta
        else:
            dt_end = dt_start + default_delta

    if dt_end <= dt_start:
        dt_end = dt_start + default_delta

    return dt_start.isoformat(), dt_end.isoformat()
