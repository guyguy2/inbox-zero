from __future__ import annotations

import base64
import io
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from bs4 import BeautifulSoup
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
