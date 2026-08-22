"""Configuration management for inbox-zero."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import tomllib

from pydantic import BaseModel, Field


DEFAULT_CONFIG_FILENAMES = [
    "config.toml",
    "inbox-zero.toml",
    ".inbox-zero.toml",
    "inbox_zero.toml",
    ".inbox_zero.toml",
    "config.json",
    ".inbox-zero.json",
]


class ReviewConfig(BaseModel):
    """Configuration options for interactive review mode."""

    show_body: bool = Field(
        default=False,
        description="Whether to display the full conversation thread / email body in review mode.",
    )


class AgentConfig(BaseModel):
    """Configuration options for pluggable AI agents."""

    provider: str = Field(
        default="agy",
        description="Agent provider or runner: 'agy' (default), 'claude', 'codex', 'grok', 'custom'.",
    )
    command: str | None = Field(
        default=None,
        description="Optional custom CLI command to execute the agent using local subscription login (e.g. 'claude -p', 'codex', 'grok', etc.).",
    )
    auto_apply: bool = Field(
        default=False,
        description="Whether to automatically apply decisions without interactive confirmation.",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional custom prompt / instructions for the agent.",
    )


class InboxZeroConfig(BaseModel):
    """Main inbox-zero configuration."""

    review: ReviewConfig = Field(default_factory=ReviewConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    default_limit: int = Field(default=20, description="Default maximum unread threads to scan/review.")
    default_query: str = Field(default="is:unread", description="Default Gmail search query.")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InboxZeroConfig:
        """Create config from dictionary supporting nested or flat structures."""
        review_raw = data.get("review")
        review_dict = dict(review_raw) if isinstance(review_raw, dict) else {}

        # Allow top-level or alternate key names for convenience
        if "show_body" in review_dict:
            show_body = bool(review_dict["show_body"])
        elif "show_email_body" in review_dict:
            show_body = bool(review_dict["show_email_body"])
        elif "show_body" in data:
            show_body = bool(data["show_body"])
        elif "show_email_body" in data:
            show_body = bool(data["show_email_body"])
        else:
            show_body = False

        review_config = ReviewConfig(show_body=show_body)

        agent_raw = data.get("agent")
        agent_dict = dict(agent_raw) if isinstance(agent_raw, dict) else {}

        provider = str(agent_dict.get("provider", data.get("agent_provider", data.get("provider", "agy"))))
        command = agent_dict.get("command", data.get("agent_command", data.get("command", None)))
        auto_apply = bool(agent_dict.get("auto_apply", data.get("agent_auto_apply", False)))
        system_prompt = agent_dict.get("system_prompt", data.get("agent_system_prompt", None))

        agent_config = AgentConfig(
            provider=provider,
            command=str(command) if command is not None else None,
            auto_apply=auto_apply,
            system_prompt=str(system_prompt) if system_prompt is not None else None,
        )

        limit_val = data.get("default_limit", review_dict.get("default_limit", 20))
        query_val = data.get("default_query", review_dict.get("default_query", "is:unread"))

        return cls(
            review=review_config,
            agent=agent_config,
            default_limit=int(limit_val),
            default_query=str(query_val),
        )


def find_config_file(custom_path: Path | str | None = None) -> Path | None:
    """Find configuration file path from explicit argument, environment, cwd, or home dir."""
    if custom_path is not None:
        p = Path(custom_path).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Config file not found: {custom_path}")
        return p

    env_path = os.environ.get("INBOX_ZERO_CONFIG")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_file():
            return p

    cwd = Path.cwd().resolve()
    for fname in DEFAULT_CONFIG_FILENAMES:
        candidate = cwd / fname
        if candidate.is_file():
            return candidate

    home_config_dir = Path.home() / ".config" / "inbox-zero"
    for fname in ("config.toml", "config.json"):
        candidate = home_config_dir / fname
        if candidate.is_file():
            return candidate

    for fname in (".inbox-zero.toml", ".inbox_zero.toml", ".inbox-zero.json"):
        candidate = Path.home() / fname
        if candidate.is_file():
            return candidate

    return None


def load_config(custom_path: Path | str | None = None) -> InboxZeroConfig:
    """Load configuration from file or return default configuration."""
    config_file = find_config_file(custom_path)
    if not config_file:
        return InboxZeroConfig()

    try:
        content = config_file.read_text(encoding="utf-8")
        if config_file.suffix.lower() == ".json":
            data = json.loads(content)
        else:
            data = tomllib.loads(content)
        return InboxZeroConfig.from_dict(data)
    except Exception as e:
        if custom_path is not None:
            raise ValueError(f"Failed to parse config file {config_file}: {e}") from e
        # If auto-discovered config is corrupted, fall back to defaults
        return InboxZeroConfig()
