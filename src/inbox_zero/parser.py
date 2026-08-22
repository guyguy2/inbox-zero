"""HTML and text cleaning utilities for email content."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup


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
