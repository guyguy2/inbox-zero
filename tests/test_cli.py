import json
from unittest.mock import patch, MagicMock
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


def test_cli_mark_read_subcommand():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.mark_as_read.return_value = True
        result = runner.invoke(app, ["mark-read", "msg_123", "msg_456"])
        assert result.exit_code == 0
        assert "Marked msg_123 as read" in result.stdout
        assert "Marked msg_456 as read" in result.stdout


def test_cli_review_mode_mark_read():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_messages.return_value = [{"id": "m1"}]
        instance.get_message.return_value = EmailMessage(
            id="m1",
            thread_id="t1",
            subject="Ben's First Day",
            sender=Sender(name="Roshani Patel", email="patel.r@nb27.org"),
            date="Fri, 21 Aug 2026",
            body_text="Ben had a wonderful day in math today.",
        )
        instance.mark_as_read.return_value = True
        # Provide input 'y' to mark as read
        result = runner.invoke(app, ["review"], input="y\n")
        assert result.exit_code == 0
        assert "Marked as read" in result.stdout


def test_cli_review_mode_quit():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_messages.return_value = [{"id": "m1"}]
        instance.get_message.return_value = EmailMessage(
            id="m1",
            thread_id="t1",
            subject="Newsletter",
            sender=Sender(name="School", email="noreply@nb27.org"),
            date="Fri, 21 Aug 2026",
            body_text="Weekly updates.",
        )
        # Provide input 'q' to quit
        result = runner.invoke(app, ["review"], input="q\n")
        assert result.exit_code == 0
        assert "Triage stopped by user" in result.stdout
