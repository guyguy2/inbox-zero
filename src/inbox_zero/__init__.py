"""inbox-zero: Intelligent Email Triage and Calendar Scheduling via Google Workspace CLI."""

from inbox_zero.client import GWSClient, GWSClientError
from inbox_zero.models import EmailMessage, TriageItem, TriageBatch, CalendarEventSuggestion
from inbox_zero.analyzer import analyze_email
from inbox_zero.cli import main, app

__version__ = "0.1.0"
__all__ = [
    "GWSClient",
    "GWSClientError",
    "EmailMessage",
    "TriageItem",
    "TriageBatch",
    "CalendarEventSuggestion",
    "analyze_email",
    "main",
    "app",
]
