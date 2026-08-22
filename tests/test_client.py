import json
import subprocess
from unittest.mock import patch, MagicMock
import pytest
from inbox_zero.client import GWSClient, GWSClientError, GWSAuthError
from inbox_zero.models import EmailMessage, Sender


def test_ensure_authenticated_success():
    client = GWSClient()
    mock_status = json.dumps({"token_valid": True, "user": "user@example.com"})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_status, stderr="")
        client.ensure_authenticated()


def test_ensure_authenticated_failure_invalid_token():
    client = GWSClient()
    mock_status = json.dumps({"token_valid": False})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_status, stderr="")
        with pytest.raises(GWSAuthError):
            client.ensure_authenticated()


def test_ensure_authenticated_failure_exit_code_2():
    client = GWSClient()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="credentials missing")
        with pytest.raises(GWSAuthError):
            client.ensure_authenticated()


def test_list_unread_messages_success():
    client = GWSClient()
    mock_output = json.dumps({"messages": [{"id": "msg_123", "subject": "Test"}]})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        results = client.list_unread_messages()
        assert len(results) == 1
        assert results[0]["id"] == "msg_123"


def test_list_unread_threads_success():
    client = GWSClient()
    mock_output = json.dumps({"threads": [{"id": "t1", "snippet": "Hello"}]})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        results = client.list_unread_threads()
        assert len(results) == 1
        assert results[0]["id"] == "t1"


def test_get_thread_success():
    client = GWSClient()
    mock_thread_data = json.dumps({
        "id": "t1",
        "messages": [{"id": "m1", "labelIds": ["UNREAD"]}, {"id": "m2", "labelIds": []}],
    })
    with patch("subprocess.run") as mock_run, patch.object(client, "get_message") as mock_get_msg:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_thread_data, stderr="")
        mock_get_msg.side_effect = [
            EmailMessage(id="m1", thread_id="t1", subject="Subject", sender=Sender(email="a@b.com"), date="Fri"),
            EmailMessage(id="m2", thread_id="t1", subject="Re: Subject", sender=Sender(email="c@d.com"), date="Fri"),
        ]
        msgs = client.get_thread("t1")
        assert len(msgs) == 2
        assert msgs[0].id == "m1"
        assert msgs[0].is_unread is True
        assert msgs[1].id == "m2"
        assert msgs[1].is_unread is False


def test_mark_thread_as_read_success():
    client = GWSClient()
    mock_output = json.dumps({"id": "t1"})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        success = client.mark_thread_as_read("t1")
        assert success is True


def test_get_message_success():
    client = GWSClient()
    mock_output = json.dumps({
        "thread_id": "t1",
        "from": {"name": "Coach Mike", "email": "mike@ayso.org"},
        "subject": "Soccer Practice",
        "date": "Fri, 21 Aug 2026",
        "body_text": "Practice is at 5pm",
    })
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        msg = client.get_message("msg_123")
        assert msg.id == "msg_123"
        assert msg.subject == "Soccer Practice"
        assert msg.sender.email == "mike@ayso.org"
        assert msg.body_text == "Practice is at 5pm"


def test_mark_as_read_success():
    client = GWSClient()
    mock_output = json.dumps({"id": "msg_123", "labelIds": ["INBOX"]})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        success = client.mark_as_read("msg_123")
        assert success is True


def test_mark_multiple_as_read():
    client = GWSClient()
    with patch.object(client, "mark_as_read", side_effect=[True, False]):
        results = client.mark_multiple_as_read(["m1", "m2"])
        assert results == {"m1": True, "m2": False}


def test_send_reply_success():
    client = GWSClient()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        assert client.send_reply("msg_123", "Thanks!") is True


def test_insert_calendar_event():
    client = GWSClient()
    mock_event = {"id": "event_999", "summary": "Practice"}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_event), stderr="")
        res = client.insert_calendar_event(
            summary="Practice",
            start_time="2026-08-27T17:00:00-05:00",
            end_time="2026-08-27T18:30:00-05:00",
            location="Wood Oaks Field 3",
        )
        assert res["id"] == "event_999"


def test_client_timeout_error():
    client = GWSClient(timeout=1)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gws", timeout=1)):
        with pytest.raises(GWSClientError, match="timed out"):
            client.list_unread_messages()


def test_client_not_found_error():
    client = GWSClient()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(GWSClientError, match="not installed"):
            client.list_unread_messages()


def test_client_invalid_json_error():
    client = GWSClient()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="not-json-content", stderr="")
        with pytest.raises(GWSClientError, match="Invalid JSON"):
            client.list_unread_messages()


def test_get_message_with_attachments():
    client = GWSClient()
    mock_read_output = json.dumps({
        "thread_id": "t1",
        "from": {"name": "Teacher", "email": "teacher@school.org"},
        "subject": "School Syllabus",
        "date": "Fri, 21 Aug 2026",
        "body_text": "Please see attached syllabus.",
    })
    mock_get_output = json.dumps({
        "payload": {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "filename": "notes.txt",
                    "body": {"attachmentId": "att_1", "size": 50},
                }
            ],
        }
    })
    mock_att_output = json.dumps({
        "data": "UGxlYXNlIGJyaW5nIG5vdGVib29rcyBieSBNb25kYXkgOWFtLg", # "Please bring notebooks by Monday 9am."
    })

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=mock_read_output, stderr=""),
            MagicMock(returncode=0, stdout=mock_get_output, stderr=""),
            MagicMock(returncode=0, stdout=mock_att_output, stderr=""),
        ]
        msg = client.get_message("msg_123")
        assert len(msg.attachments) == 1
        assert msg.attachments[0].filename == "notes.txt"
        assert "notebooks" in msg.attachments[0].extracted_text


def test_get_attachment_bytes():
    client = GWSClient()
    mock_att_output = json.dumps({
        "data": "SGVsbG8",
    })
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_att_output, stderr="")
        data = client.get_attachment_bytes("msg_123", "att_999")
        assert data == b"Hello"

