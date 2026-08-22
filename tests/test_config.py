import json
import os
from pathlib import Path
import pytest
from inbox_zero.config import (
    InboxZeroConfig,
    ReviewConfig,
    find_config_file,
    load_config,
)


def test_default_config():
    cfg = InboxZeroConfig()
    assert cfg.review.show_body is False
    assert cfg.default_limit == 20
    assert cfg.default_query == "is:unread"


def test_config_from_dict_nested():
    data = {"review": {"show_body": True}, "default_limit": 10, "default_query": "label:inbox"}
    cfg = InboxZeroConfig.from_dict(data)
    assert cfg.review.show_body is True
    assert cfg.default_limit == 10
    assert cfg.default_query == "label:inbox"


def test_config_from_dict_show_email_body_alias():
    data = {"review": {"show_email_body": True}}
    cfg = InboxZeroConfig.from_dict(data)
    assert cfg.review.show_body is True


def test_config_from_dict_flat_show_body():
    data = {"show_body": True}
    cfg = InboxZeroConfig.from_dict(data)
    assert cfg.review.show_body is True


def test_config_from_dict_flat_show_email_body():
    data = {"show_email_body": True}
    cfg = InboxZeroConfig.from_dict(data)
    assert cfg.review.show_body is True


def test_find_config_file_explicit(tmp_path: Path):
    cfg_file = tmp_path / "custom.toml"
    cfg_file.write_text("[review]\nshow_body = true\n")

    found = find_config_file(cfg_file)
    assert found == cfg_file.resolve()


def test_find_config_file_explicit_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        find_config_file(tmp_path / "nonexistent.toml")


def test_find_config_file_env_var(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "env_config.toml"
    cfg_file.write_text("[review]\nshow_body = true\n")

    monkeypatch.setenv("INBOX_ZERO_CONFIG", str(cfg_file))
    found = find_config_file()
    assert found == cfg_file.resolve()


def test_load_config_toml(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[review]\nshow_body = true\ndefault_limit = 50\n")

    cfg = load_config(cfg_file)
    assert cfg.review.show_body is True
    assert cfg.default_limit == 50


def test_load_config_json(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"review": {"show_body": True}, "default_limit": 15}))

    cfg = load_config(cfg_file)
    assert cfg.review.show_body is True
    assert cfg.default_limit == 15


def test_load_config_nonexistent():
    # Calling with None when no config matches should return default
    cfg = load_config()
    assert isinstance(cfg, InboxZeroConfig)
    # The default config in repo root has show_body = false
    assert cfg.review.show_body is False
    assert cfg.agent.provider == "agy"


def test_agent_config_defaults():
    cfg = InboxZeroConfig()
    assert cfg.agent.provider == "agy"
    assert cfg.agent.command is None
    assert cfg.agent.auto_apply is False
    assert cfg.agent.system_prompt is None


def test_agent_config_from_toml(tmp_path: Path):
    toml_content = """
    [review]
    show_body = true

    [agent]
    provider = "claude"
    command = "claude -p"
    auto_apply = true
    system_prompt = "Custom agent instructions"
    """
    cfg_file = tmp_path / "agent_config.toml"
    cfg_file.write_text(toml_content)

    cfg = load_config(cfg_file)
    assert cfg.review.show_body is True
    assert cfg.agent.provider == "claude"
    assert cfg.agent.command == "claude -p"
    assert cfg.agent.auto_apply is True
    assert cfg.agent.system_prompt == "Custom agent instructions"

