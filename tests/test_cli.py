from unittest.mock import patch, MagicMock
import json
from typer.testing import CliRunner
from inbox_zero.cli import app
from inbox_zero.client import GWSAuthError
from inbox_zero.models import EmailMessage, Sender

runner = CliRunner()


def test_cli_scan_auth_failure():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.ensure_authenticated.side_effect = GWSAuthError()
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 2
        assert "gws auth login" in result.stdout


def test_cli_scan_empty():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_messages.return_value = []
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Inbox Zero" in result.stdout


def test_cli_scan_with_messages():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_messages.return_value = [{"id": "m1"}]
        instance.get_message.return_value = EmailMessage(
            id="m1",
            thread_id="t1",
            subject="AYSO Soccer Practice",
            sender=Sender(name="Coach", email="coach@ayso.org"),
            date="Fri, 21 Aug 2026",
            body_text="Practice on Thursday, Aug 27 at 5:00 PM.",
        )
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Unread Emails Triage" in result.stdout
        assert "AYSO Soccer Practice" in result.stdout


def test_cli_scan_json():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_messages.return_value = [{"id": "m1"}]
        instance.get_message.return_value = EmailMessage(
            id="m1",
            thread_id="t1",
            subject="Math Homework",
            sender=Sender(name="Teacher", email="teacher@school.org"),
            date="Fri, 21 Aug 2026",
            body_text="Please submit math homework.",
        )
        result = runner.invoke(app, ["scan", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_unread"] == 1
        assert data["items"][0]["message_id"] == "m1"
