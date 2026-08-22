import json
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from inbox_zero.cli import app
from inbox_zero.client import GWSAuthError
from inbox_zero.models import EmailAttachment, EmailMessage, Sender

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
        assert "Start interactive review now?" in result.stdout


def test_cli_scan_launches_review_on_yes():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text="Practice on Thursday.",
            )
        ]
        instance.mark_thread_as_read.return_value = True

        # Input 'y' to launch review, then 'y' to mark thread as read in review mode
        result = runner.invoke(app, ["scan"], input="y\ny\n")
        assert result.exit_code == 0
        assert "Start interactive review now?" in result.stdout
        assert "Starting interactive triage" in result.stdout
        assert "Marked thread as read" in result.stdout


def test_cli_scan_launches_review_on_default_enter():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text="Practice on Thursday.",
            )
        ]
        instance.mark_thread_as_read.return_value = True

        # Input '\n' (enter key - default yes) to launch review, then 'y' to mark read
        result = runner.invoke(app, ["scan"], input="\ny\n")
        assert result.exit_code == 0
        assert "Start interactive review now?" in result.stdout
        assert "Starting interactive triage" in result.stdout
        assert "Marked thread as read" in result.stdout


def test_cli_scan_skips_review_on_no():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text="Practice on Thursday.",
            )
        ]

        # Input 'n' to decline launching review
        result = runner.invoke(app, ["scan"], input="n\n")
        assert result.exit_code == 0
        assert "Start interactive review now?" in result.stdout
        assert "Starting interactive triage" not in result.stdout



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


def test_cli_review_mode_reply_custom():
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
        # Input 'r' (reply), then 'c' (custom), then custom text, then 'y' (mark read)
        result = runner.invoke(app, ["review"], input="r\nc\nSounds wonderful, thank you!\ny\n")
        assert result.exit_code == 0
        instance.send_reply.assert_called_with("m1", "Sounds wonderful, thank you!")
        assert "Reply sent to thread" in result.stdout
        assert "Thread marked as read" in result.stdout


def test_cli_review_mode_reply_edit():
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
        # Input 'r' (reply), then 'e' (edit), then input modified text, then 'y' (mark read)
        result = runner.invoke(app, ["review"], input="r\ne\nThank you for letting us know!\ny\n")
        assert result.exit_code == 0
        instance.send_reply.assert_called_with("m1", "Thank you for letting us know!")
        assert "Reply sent to thread" in result.stdout


def test_cli_review_mode_reply_add_text():
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
        # Input 'r' (reply), then 'a' (add text), then extra text, then 'y' (mark read)
        result = runner.invoke(app, ["review"], input="r\na\nSee you tomorrow.\ny\n")
        assert result.exit_code == 0
        assert instance.send_reply.call_count == 1
        sent_body = instance.send_reply.call_args[0][1]
        assert "See you tomorrow." in sent_body
        assert "Reply sent to thread" in result.stdout


def test_cli_review_mode_reply_cancel():
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
        instance.mark_thread_as_read.return_value = True
        # Input 'r' (reply), then 's' (cancel reply), then 'y' (mark read)
        result = runner.invoke(app, ["review"], input="r\ns\ny\n")
        assert result.exit_code == 0
        instance.send_reply.assert_not_called()
        assert "Reply cancelled" in result.stdout
        assert "Marked thread as read" in result.stdout


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


def test_cli_review_mode_default_hides_body():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice Update",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text=(
                    "Practice is on Thursday at 5pm at Field 3. "
                    "Please bring extra water bottles for the scrimmage. "
                    "Coach Dave will lead the warm-up exercises. "
                    "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW."
                ),
            )
        ]
        instance.mark_thread_as_read.return_value = True
        result = runner.invoke(app, ["review"], input="y\n")
        assert result.exit_code == 0
        # Title and summary should appear
        assert "Soccer Practice" in result.stdout
        assert "Practice is on Thursday at 5pm" in result.stdout
        # Conversation Thread header and raw body text beyond 3 sentences should NOT appear by default
        assert "### 🧵 Conversation Thread" not in result.stdout
        assert "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW" not in result.stdout
        assert "View Full Email" in result.stdout


def test_cli_review_mode_show_body_flag():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice Update",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text=(
                    "Practice is on Thursday at 5pm at Field 3. "
                    "Please bring extra water bottles for the scrimmage. "
                    "Coach Dave will lead the warm-up exercises. "
                    "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW."
                ),
            )
        ]
        instance.mark_thread_as_read.return_value = True
        result = runner.invoke(app, ["review", "--show-body"], input="y\n")
        assert result.exit_code == 0
        assert "Conversation Thread" in result.stdout
        assert "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW" in result.stdout


def test_cli_review_mode_config_file(tmp_path):
    cfg_file = tmp_path / "custom_config.toml"
    cfg_file.write_text("[review]\nshow_body = true\n")

    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice Update",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text=(
                    "Practice is on Thursday at 5pm at Field 3. "
                    "Please bring extra water bottles for the scrimmage. "
                    "Coach Dave will lead the warm-up exercises. "
                    "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW."
                ),
            )
        ]
        instance.mark_thread_as_read.return_value = True
        result = runner.invoke(app, ["review", "--config", str(cfg_file)], input="y\n")
        assert result.exit_code == 0
        assert "Conversation Thread" in result.stdout
        assert "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW" in result.stdout


def test_cli_review_mode_override_config_no_show_body(tmp_path):
    cfg_file = tmp_path / "custom_config.toml"
    cfg_file.write_text("[review]\nshow_body = true\n")

    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice Update",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text=(
                    "Practice is on Thursday at 5pm at Field 3. "
                    "Please bring extra water bottles for the scrimmage. "
                    "Coach Dave will lead the warm-up exercises. "
                    "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW."
                ),
            )
        ]
        instance.mark_thread_as_read.return_value = True
        result = runner.invoke(app, ["review", "--config", str(cfg_file), "--no-show-body"], input="y\n")
        assert result.exit_code == 0
        assert "Conversation Thread" not in result.stdout
        assert "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW" not in result.stdout


def test_cli_review_mode_interactive_view():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice Update",
                sender=Sender(name="Coach Dave", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text=(
                    "Practice is on Thursday at 5pm at Field 3. "
                    "Please bring extra water bottles for the scrimmage. "
                    "Coach Dave will lead the warm-up exercises. "
                    "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW."
                ),
            )
        ]
        instance.mark_thread_as_read.return_value = True
        # User presses 'v' to view, then 'y' to mark as read
        result = runner.invoke(app, ["review"], input="v\ny\n")
        assert result.exit_code == 0
        assert "RAW_DETAILED_BODY_PARAGRAPH_ONLY_IN_THREAD_VIEW" in result.stdout
        assert "Marked thread as read" in result.stdout


def test_cli_agent_dry_run():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice",
                sender=Sender(name="Coach", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text="Practice on Thursday.",
            )
        ]
        result = runner.invoke(app, ["agent", "--dry-run"])
        assert result.exit_code == 0
        assert "You are an intelligent email triage assistant" in result.stdout
        assert '"total_unread": 1' in result.stdout


def test_cli_agent_empty_inbox():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = []
        instance.list_unread_messages.return_value = []
        result = runner.invoke(app, ["agent"])
        assert result.exit_code == 0
        assert "Inbox Zero" in result.stdout


def test_cli_agent_confirm_and_apply():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls, \
         patch("inbox_zero.cli.run_agent") as mock_run_agent:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Math HW",
                sender=Sender(name="Teacher", email="teacher@school.org"),
                date="Fri, 21 Aug 2026",
                body_text="Homework is due.",
            )
        ]
        mock_run_agent.return_value = {
            "reasoning": "Teacher message acknowledged.",
            "replies": [{"message_id": "m1", "body": "Thank you!"}],
            "calendar_events": [{"summary": "HW Due", "start_time": "2026-08-25"}],
            "mark_as_read": ["t1"],
        }
        instance.send_reply.return_value = True
        instance.insert_calendar_event.return_value = {"id": "ev_1"}
        instance.mark_thread_as_read.return_value = True

        result = runner.invoke(app, ["agent", "--provider", "claude"], input="y\n")
        assert result.exit_code == 0
        assert "AI Agent Proposed Decisions" in result.stdout
        assert "Teacher message acknowledged" in result.stdout
        assert "Replies Sent: 1" in result.stdout
        assert "Calendar Events Added: 1" in result.stdout
        assert "Marked as Read: 1" in result.stdout


def test_cli_agent_auto_apply_yes():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls, \
         patch("inbox_zero.cli.run_agent") as mock_run_agent:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Math HW",
                sender=Sender(name="Teacher", email="teacher@school.org"),
                date="Fri, 21 Aug 2026",
                body_text="Homework is due.",
            )
        ]
        mock_run_agent.return_value = {
            "reasoning": "Quick reply",
            "replies": [{"message_id": "m1", "body": "Thank you!"}],
            "calendar_events": [],
            "mark_as_read": ["m1"],
        }
        instance.send_reply.return_value = True
        instance.mark_thread_as_read.return_value = True

        # Note no input supplied because --yes auto applies
        result = runner.invoke(app, ["agent", "--yes", "--provider", "codex"])
        assert result.exit_code == 0
        assert "Execution Complete" in result.stdout
        assert "Replies Sent: 1" in result.stdout


def test_cli_agent_error_handling():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls, \
         patch("inbox_zero.cli.run_agent") as mock_run_agent:
        from inbox_zero.agent_bridge import AgentExecutionError
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Math HW",
                sender=Sender(name="Teacher", email="teacher@school.org"),
                date="Fri, 21 Aug 2026",
                body_text="Homework is due.",
            )
        ]
        mock_run_agent.side_effect = AgentExecutionError("CLI not found")

        result = runner.invoke(app, ["agent"])
        assert result.exit_code == 1
        assert "Agent execution failed" in result.stdout


def test_cli_no_args_shows_help():
    result = runner.invoke(app, [])
    # Typer with no_args_is_help=True prints help and exits with 0 or 2
    assert "Usage: inbox-zero" in result.stdout or "Usage:" in result.stdout
    assert "Commands" in result.stdout or "Options" in result.stdout
    assert "scan" in result.stdout
    assert "review" in result.stdout
    assert "agent" in result.stdout


def test_cli_review_mode_enter_key_marks_read():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Quick Note",
                sender=Sender(name="Alice", email="alice@example.com"),
                date="Fri, 21 Aug 2026",
                body_text="Hello world",
            )
        ]
        instance.mark_thread_as_read.return_value = True
        # Press Enter directly (\n)
        result = runner.invoke(app, ["review"], input="\n")
        assert result.exit_code == 0
        assert "Marked thread as read" in result.stdout


def test_cli_review_mode_skip_shortcut():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Quick Note",
                sender=Sender(name="Alice", email="alice@example.com"),
                date="Fri, 21 Aug 2026",
                body_text="Hello world",
            )
        ]
        # Press 's' (skip / keep unread)
        result = runner.invoke(app, ["review"], input="s\n")
        assert result.exit_code == 0
        assert "Kept thread unread" in result.stdout
        instance.mark_thread_as_read.assert_not_called()


def test_cli_review_mode_help_shortcut():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Quick Note",
                sender=Sender(name="Alice", email="alice@example.com"),
                date="Fri, 21 Aug 2026",
                body_text="Hello world",
            )
        ]
        instance.mark_thread_as_read.return_value = True
        # Press '?' for help, then '\n' (enter) to mark read
        result = runner.invoke(app, ["review"], input="?\n\n")
        assert result.exit_code == 0
        assert "Keyboard Shortcuts" in result.stdout
        assert "Marked thread as read" in result.stdout


def test_cli_review_mode_previous_navigation():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}, {"id": "t2"}]
        instance.get_thread.side_effect = [
            [
                EmailMessage(
                    id="m1",
                    thread_id="t1",
                    subject="Email 1",
                    sender=Sender(name="User 1", email="user1@example.com"),
                    date="Fri, 21 Aug 2026",
                    body_text="First message",
                )
            ],
            [
                EmailMessage(
                    id="m2",
                    thread_id="t2",
                    subject="Email 2",
                    sender=Sender(name="User 2", email="user2@example.com"),
                    date="Fri, 21 Aug 2026",
                    body_text="Second message",
                )
            ],
            [
                EmailMessage(
                    id="m1",
                    thread_id="t1",
                    subject="Email 1",
                    sender=Sender(name="User 1", email="user1@example.com"),
                    date="Fri, 21 Aug 2026",
                    body_text="First message",
                )
            ],
        ]
        instance.mark_thread_as_read.return_value = True
        # Email 1: skip (s) -> moves to Email 2
        # Email 2: go back (p) -> moves back to Email 1
        # Email 1: mark read (\n) -> moves to Email 2
        # Email 2: mark read (\n) -> finishes
        result = runner.invoke(app, ["review"], input="s\np\n\n\n")
        assert result.exit_code == 0
        assert "Email 1" in result.stdout
        assert "Email 2" in result.stdout


def test_cli_scan_chunking_over_ten():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        threads = [{"id": f"t{i}"} for i in range(1, 16)]
        instance.list_unread_threads.return_value = threads

        def make_thread(tid):
            return [
                EmailMessage(
                    id=f"m_{tid}",
                    thread_id=tid,
                    subject=f"Subject {tid}",
                    sender=Sender(name="Teacher", email="teacher@school.org"),
                    date="Fri, 21 Aug 2026",
                    body_text=f"Body for {tid}",
                )
            ]

        instance.get_thread.side_effect = make_thread

        result = runner.invoke(app, ["scan"], input="\n")
        assert result.exit_code == 0
        assert "Page 1/2" in result.stdout
        assert "Items 1–10 of 15" in result.stdout
        assert "Page 2/2" in result.stdout
        assert "Items 11–15 of 15" in result.stdout


def test_cli_review_chunking_over_ten():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        threads = [{"id": f"t{i}"} for i in range(1, 13)]
        instance.list_unread_threads.return_value = threads

        def make_thread(tid):
            return [
                EmailMessage(
                    id=f"m_{tid}",
                    thread_id=tid,
                    subject=f"Subject {tid}",
                    sender=Sender(name="Sender", email="sender@example.com"),
                    date="Fri, 21 Aug 2026",
                    body_text=f"Body {tid}",
                )
            ]

        instance.get_thread.side_effect = lambda tid: make_thread(tid)
        instance.mark_thread_as_read.return_value = True

        # Provide 10 'y' (for batch 1), then 'y' (to advance past batch milestone), then 2 'y' (batch 2)
        simulated_inputs = "y\n" * 13
        result = runner.invoke(app, ["review"], input=simulated_inputs)
        assert result.exit_code == 0
        assert "Batch 1 of 2 Complete" in result.stdout
        assert "Batch 1/2" in result.stdout
        assert "Batch 2/2" in result.stdout
        assert "All 12 unread email threads reviewed" in result.stdout


def test_cli_scan_date_descending_order():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]
        instance.get_thread.side_effect = [
            [
                EmailMessage(
                    id="m1",
                    thread_id="t1",
                    subject="Oldest Thread",
                    sender=Sender(name="Alice", email="alice@example.com"),
                    date="Wed, 19 Aug 2026 10:00:00 -0500",
                    body_text="Oldest email",
                )
            ],
            [
                EmailMessage(
                    id="m2",
                    thread_id="t2",
                    subject="Newest Thread",
                    sender=Sender(name="Bob", email="bob@example.com"),
                    date="Sat, 22 Aug 2026 10:00:00 -0500",
                    body_text="Newest email",
                )
            ],
            [
                EmailMessage(
                    id="m3",
                    thread_id="t3",
                    subject="Middle Thread",
                    sender=Sender(name="Charlie", email="charlie@example.com"),
                    date="Thu, 20 Aug 2026 10:00:00 -0500",
                    body_text="Middle email",
                )
            ],
        ]

        result = runner.invoke(app, ["scan", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Should be ordered newest (t2) -> middle (t3) -> oldest (t1)
        assert [it["thread_id"] for it in data["items"]] == ["t2", "t3", "t1"]


def test_cli_review_date_descending_order():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]
        instance.get_thread.side_effect = [
            [
                EmailMessage(
                    id="m1",
                    thread_id="t1",
                    subject="Oldest Thread",
                    sender=Sender(name="Alice", email="alice@example.com"),
                    date="Wed, 19 Aug 2026 10:00:00 -0500",
                    body_text="Oldest email",
                )
            ],
            [
                EmailMessage(
                    id="m2",
                    thread_id="t2",
                    subject="Newest Thread",
                    sender=Sender(name="Bob", email="bob@example.com"),
                    date="Sat, 22 Aug 2026 10:00:00 -0500",
                    body_text="Newest email",
                )
            ],
            [
                EmailMessage(
                    id="m3",
                    thread_id="t3",
                    subject="Middle Thread",
                    sender=Sender(name="Charlie", email="charlie@example.com"),
                    date="Thu, 20 Aug 2026 10:00:00 -0500",
                    body_text="Middle email",
                )
            ],
        ]
        instance.mark_thread_as_read.return_value = True

        # Input 3 'y' to mark each as read
        result = runner.invoke(app, ["review"], input="y\ny\ny\n")
        assert result.exit_code == 0
        # Check order of appearance in stdout: Newest Thread -> Middle Thread -> Oldest Thread
        pos_newest = result.stdout.find("Newest Thread")
        pos_middle = result.stdout.find("Middle Thread")
        pos_oldest = result.stdout.find("Oldest Thread")
        assert pos_newest != -1 and pos_middle != -1 and pos_oldest != -1
        assert pos_newest < pos_middle < pos_oldest


def test_cli_scan_and_review_with_attachments():
    with patch("inbox_zero.cli.GWSClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        att = EmailAttachment(
            filename="syllabus.pdf",
            mime_type="application/pdf",
            size_bytes=102400,
            extracted_text="Math 101 Syllabus. Midterm Exam on Friday, October 16.",
        )
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Course Syllabus",
                sender=Sender(name="Professor", email="prof@university.edu"),
                date="Fri, 21 Aug 2026 12:00:00 -0500",
                body_text="Please find the syllabus attached.",
                attachments=[att],
            )
        ]
        instance.mark_thread_as_read.return_value = True

        # Test scan output contains attachment
        result_scan = runner.invoke(app, ["scan"], input="n\n")
        assert result_scan.exit_code == 0
        assert "syllabus.pdf" in result_scan.stdout

        # Test review output contains attachment preview and extracted action/date
        result_review = runner.invoke(app, ["review"], input="y\n")
        assert result_review.exit_code == 0
        assert "syllabus.pdf" in result_review.stdout
        assert "Attachments" in result_review.stdout







