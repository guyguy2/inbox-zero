from inbox_zero.parser import (
    clean_html_to_text,
    extract_clean_email_body,
    parse_email_date,
    truncate_preview,
)
from inbox_zero.models import Sender


def test_clean_html():
    raw_html = """
    <html>
      <head><style>.test { color: red; }</style></head>
      <body>
        <h1>School Notice</h1>
        <p>Dear Parents,</p>
        <p>Back to school night is on <b>Thursday, August 28</b>.<br>Please bring pencils.</p>
        <script>alert("hack");</script>
      </body>
    </html>
    """
    text = clean_html_to_text(raw_html)
    assert "School Notice" in text
    assert "Dear Parents" in text
    assert "Thursday, August 28" in text
    assert "Please bring pencils" in text
    assert "alert" not in text
    assert ".test" not in text


def test_extract_clean_email_body_fallback():
    body_text = "<!--placeholder-->"
    body_html = "<p>Real newsletter content here</p>"
    result = extract_clean_email_body(body_text, body_html)
    assert "Real newsletter content here" in result


def test_sender_parsing():
    s1 = Sender.from_gws({"name": "Alice Smith", "email": "alice@example.com"})
    assert s1.name == "Alice Smith"
    assert s1.email == "alice@example.com"

    s2 = Sender.from_gws('"Bob Jones" <bob@example.com>')
    assert s2.name == "Bob Jones"
    assert s2.email == "bob@example.com"

    s3 = Sender.from_gws("carol@example.com")
    assert s3.email == "carol@example.com"


def test_truncate_preview():
    text = "This is a long line of text " * 20
    preview = truncate_preview(text, 50)
    assert len(preview) <= 53
    assert preview.endswith("...")


def test_parse_email_date():
    # RFC 2822 format
    dt1 = parse_email_date("Fri, 21 Aug 2026 12:48:42 -0500")
    dt2 = parse_email_date("Fri, 21 Aug 2026 20:25:17 +0000")
    assert dt1 < dt2

    # ISO format
    dt3 = parse_email_date("2026-08-22T10:00:00Z")
    assert dt2 < dt3

    # Empty / Invalid fallback
    dt_empty = parse_email_date("")
    dt_none = parse_email_date(None)
    dt_invalid = parse_email_date("not-a-date")
    assert dt_empty == dt_none == dt_invalid

