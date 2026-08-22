"""inbox-zero: Intelligent Email Triage and Calendar Scheduling via Google Workspace CLI."""

from inbox_zero.client import GWSClient, GWSClientError, GWSAuthError
from inbox_zero.models import EmailMessage, TriageItem, TriageBatch, CalendarEventSuggestion
from inbox_zero.config import InboxZeroConfig, ReviewConfig, AgentConfig, load_config, find_config_file
from inbox_zero.analyzer import analyze_email, analyze_thread
from inbox_zero.agent_bridge import (
    prepare_agent_triage_payload,
    apply_agent_decisions,
    run_agent,
    extract_json_from_agent_output,
    get_agent_command,
    build_agent_prompt,
    AgentExecutionError,
)
from inbox_zero.cli import main, app

__version__ = "0.1.0"
__all__ = [
    "GWSClient",
    "GWSClientError",
    "GWSAuthError",
    "EmailMessage",
    "TriageItem",
    "TriageBatch",
    "CalendarEventSuggestion",
    "InboxZeroConfig",
    "ReviewConfig",
    "AgentConfig",
    "load_config",
    "find_config_file",
    "analyze_email",
    "analyze_thread",
    "prepare_agent_triage_payload",
    "apply_agent_decisions",
    "run_agent",
    "extract_json_from_agent_output",
    "get_agent_command",
    "build_agent_prompt",
    "AgentExecutionError",
    "main",
    "app",
]
