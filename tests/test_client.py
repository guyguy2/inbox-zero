import json
from unittest.mock import patch, MagicMock
import pytest
from inbox_zero.client import GWSClient, GWSClientError, GWSAuthError


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


def test_mark_as_read_success():
    client = GWSClient()
    mock_output = json.dumps({"id": "msg_123", "labelIds": ["INBOX"]})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        success = client.mark_as_read("msg_123")
        assert success is True


def test_send_reply_success():
    client = GWSClient()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        assert client.send_reply("msg_123", "Thanks!") is True
