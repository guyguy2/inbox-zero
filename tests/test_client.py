import json
from unittest.mock import patch, MagicMock
import pytest
from inbox_zero.client import GWSClient, GWSClientError


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


def test_gws_error_handling():
    client = GWSClient()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="OAuth token expired")
        with pytest.raises(GWSClientError):
            client.list_unread_messages()
