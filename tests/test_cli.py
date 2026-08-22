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
        instance.list_unread_threads.return_value = []
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Inbox Zero" in result.stdout


def test_cli_scan_with_thread_messages():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Liam and Ben's start to the year",
                sender=Sender(name="Stefani Wiemann", email="wiemann.s@nb27.org"),
                date="Fri, 21 Aug 2026 12:48:42 -0500",
                body_text="Good morning! Great having Liam and Ben in class.",
            ),
            EmailMessage(
                id="m2",
                thread_id="t1",
                subject="Re: Liam and Ben's start to the year",
                sender=Sender(name="Hanni", email="hanni1976.hf@gmail.com"),
                date="Fri, 21 Aug 2026 20:25:17 +0000",
                body_text="Thank you for your email!",
            ),
        ]
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Unread Emails Triage" in result.stdout
        assert "1 threads / 2 messages" in result.stdout
        assert "Liam and Ben" in result.stdout
        assert "Stefani Wiemann" in result.stdout


def test_cli_scan_json():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Math Homework",
                sender=Sender(name="Teacher", email="teacher@school.org"),
                date="Fri, 21 Aug 2026",
                body_text="Please submit math homework.",
            )
        ]
        result = runner.invoke(app, ["scan", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_unread"] == 1
        assert data["total_messages"] == 1
        assert data["items"][0]["message_id"] == "m1"
        assert data["items"][0]["thread_id"] == "t1"


def test_cli_mark_read_subcommand():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.mark_thread_as_read.return_value = True
        instance.mark_as_read.return_value = True
        result = runner.invoke(app, ["mark-read", "thread_123", "msg_456"])
        assert result.exit_code == 0
        assert "Marked thread_123 as read" in result.stdout
        assert "Marked msg_456 as read" in result.stdout


def test_cli_review_mode_mark_read():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Ben's First Day",
                sender=Sender(name="Roshani Patel", email="patel.r@nb27.org"),
                date="Fri, 21 Aug 2026",
                body_text="Ben had a wonderful day in math today.",
            )
        ]
        instance.mark_thread_as_read.return_value = True
        # Provide input 'y' to mark as read
        result = runner.invoke(app, ["review"], input="y\n")
        assert result.exit_code == 0
        assert "Marked thread as read" in result.stdout


def test_cli_review_mode_quit():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Newsletter",
                sender=Sender(name="School", email="noreply@nb27.org"),
                date="Fri, 21 Aug 2026",
                body_text="Weekly updates.",
            )
        ]
        # Provide input 'q' to quit
        result = runner.invoke(app, ["review"], input="q\n")
        assert result.exit_code == 0
        assert "Triage stopped by user" in result.stdout


def test_cli_review_mode_reply():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Ben's First Day",
                sender=Sender(name="Roshani Patel", email="patel.r@nb27.org"),
                date="Fri, 21 Aug 2026",
                body_text="Ben had a great day!",
            )
        ]
        instance.send_reply.return_value = True
        instance.mark_thread_as_read.return_value = True
        # Input 'r' (reply), then '1' (suggested reply 1), then 'y' (confirm mark as read)
        result = runner.invoke(app, ["review"], input="r\n1\ny\n")
        assert result.exit_code == 0
        assert "Reply sent to thread" in result.stdout
        assert "Thread marked as read" in result.stdout


def test_cli_review_mode_calendar():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Back to school",
                sender=Sender(name="School", email="teacher@nb27.org"),
                date="Fri, 21 Aug 2026",
                body_text="Back to school night is Wednesday, Sept. 9 at 9:30am.",
            )
        ]
        instance.insert_calendar_event.return_value = {"id": "ev1"}
        instance.mark_thread_as_read.return_value = True
        # Input 'c' (calendar), then 'y' (confirm event), then 'y' (confirm mark as read)
        result = runner.invoke(app, ["review"], input="c\ny\ny\n")
        assert result.exit_code == 0
        assert "Added to Google Calendar" in result.stdout
        assert "Thread marked as read" in result.stdout
