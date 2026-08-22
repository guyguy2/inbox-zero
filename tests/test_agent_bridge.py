import subprocess
from unittest.mock import MagicMock, patch
import pytest

from inbox_zero.agent_bridge import (
    AgentExecutionError,
    apply_agent_decisions,
    build_agent_prompt,
    extract_json_from_agent_output,
    get_agent_command,
    prepare_agent_triage_payload,
    run_agent,
)
from inbox_zero.models import EmailMessage, Sender


def test_prepare_agent_triage_payload():
    with patch("inbox_zero.agent_bridge.GWSClient") as mock_cls:
        instance = mock_cls.return_value
        instance.list_unread_threads.return_value = [{"id": "t1"}]
        instance.get_thread.return_value = [
            EmailMessage(
                id="m1",
                thread_id="t1",
                subject="Soccer Practice",
                sender=Sender(name="Coach", email="coach@ayso.org"),
                date="Fri, 21 Aug 2026",
                body_text="Practice on Thursday at 5pm.",
            )
        ]
        payload = prepare_agent_triage_payload()
        assert payload["total_unread"] == 1
        assert payload["total_messages"] == 1
        assert payload["items"][0]["message_id"] == "m1"
        assert payload["items"][0]["category"] == "Sports & Activities"


def test_apply_agent_decisions():
    mock_client = MagicMock()
    mock_client.send_reply.return_value = True
    mock_client.insert_calendar_event.return_value = {"id": "ev_1"}
    mock_client.mark_thread_as_read.return_value = True
    mock_client.mark_as_read.return_value = True

    decisions = {
        "replies": [{"message_id": "m1", "body": "Thanks Coach!"}],
        "calendar_events": [{"summary": "Practice", "start_time": "2026-08-27T17:00:00"}],
        "mark_as_read": ["m1"],
    }

    results = apply_agent_decisions(decisions, client=mock_client)
    assert results["replies_sent"]["m1"] is True
    assert len(results["events_created"]) == 1
    assert results["marked_read"]["m1"] is True


def test_get_agent_command():
    assert get_agent_command("agy") == ["agy", "run"]
    assert get_agent_command("claude") == ["claude", "-p"]
    assert get_agent_command("codex") == ["codex"]
    assert get_agent_command("grok") == ["grok"]
    assert get_agent_command("custom", custom_command="my-cli --flag -v") == ["my-cli", "--flag", "-v"]
    assert get_agent_command("unknown_provider") == ["unknown_provider"]


def test_extract_json_from_agent_output_pure_json():
    raw = '{"reasoning": "ok", "replies": [], "calendar_events": [], "mark_as_read": ["m1"]}'
    res = extract_json_from_agent_output(raw)
    assert res["mark_as_read"] == ["m1"]


def test_extract_json_from_agent_output_markdown_block():
    raw = """Here are the actions for the emails:
```json
{
  "reasoning": "Reviewed emails.",
  "replies": [{"message_id": "m1", "body": "Got it"}],
  "calendar_events": [],
  "mark_as_read": ["m1"]
}
```
Hope this helps!"""
    res = extract_json_from_agent_output(raw)
    assert res["reasoning"] == "Reviewed emails."
    assert len(res["replies"]) == 1
    assert res["replies"][0]["body"] == "Got it"


def test_extract_json_from_agent_output_fuzzy_braces():
    raw = """Some text before
{
  "reasoning": "Found event",
  "replies": [],
  "calendar_events": [{"summary": "Soccer", "start_time": "2026-08-27"}],
  "mark_as_read": []
}
Some text after"""
    res = extract_json_from_agent_output(raw)
    assert res["calendar_events"][0]["summary"] == "Soccer"


def test_extract_json_from_agent_output_empty_or_invalid():
    with pytest.raises(AgentExecutionError):
        extract_json_from_agent_output("")

    with pytest.raises(AgentExecutionError):
        extract_json_from_agent_output("No json here at all.")


def test_build_agent_prompt():
    payload = {"total_unread": 1, "items": []}
    prompt = build_agent_prompt(payload)
    assert "You are an intelligent email triage assistant." in prompt
    assert '"total_unread": 1' in prompt


def test_run_agent_claude():
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout='{"reasoning": "done", "replies": [], "calendar_events": [], "mark_as_read": ["t1"]}',
        )
        res = run_agent({"total_unread": 1}, provider="claude")
        assert res["mark_as_read"] == ["t1"]
        # Claude uses command line argument
        mock_sub.assert_called_once()
        args = mock_sub.call_args[0][0]
        assert args[0] == "claude"
        assert args[1] == "-p"


def test_run_agent_agy():
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout='{"reasoning": "done", "replies": [], "calendar_events": [], "mark_as_read": ["t1"]}',
        )
        res = run_agent({"total_unread": 1}, provider="agy")
        assert res["mark_as_read"] == ["t1"]
        mock_sub.assert_called_once()
        assert mock_sub.call_args[0][0] == ["agy", "run"]


def test_run_agent_binary_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(AgentExecutionError) as exc_info:
            run_agent({"total_unread": 1}, provider="nonexistent_agent")
        assert "not found in PATH" in str(exc_info.value)


def test_run_agent_process_error():
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Authentication required. Please run login.",
        )
        with pytest.raises(AgentExecutionError) as exc_info:
            run_agent({"total_unread": 1}, provider="claude")
        assert "Authentication required" in str(exc_info.value)
