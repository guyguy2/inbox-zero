from unittest.mock import patch, MagicMock
from inbox_zero.agent_bridge import prepare_agent_triage_payload, apply_agent_decisions
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
