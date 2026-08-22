from unittest.mock import patch, MagicMock
import io
import sys
import pytest
from inbox_zero.keys import get_single_key, parse_raw_key_bytes


def test_parse_raw_key_bytes_arrows():
    # Standard ANSI arrow keys
    assert parse_raw_key_bytes(b"\x1b[A") == "up"
    assert parse_raw_key_bytes(b"\x1b[B") == "down"
    assert parse_raw_key_bytes(b"\x1b[C") == "right"
    assert parse_raw_key_bytes(b"\x1b[D") == "left"

    # Application / SS3 mode arrow keys (macOS Terminal / xterm / iTerm2)
    assert parse_raw_key_bytes(b"\x1bOA") == "up"
    assert parse_raw_key_bytes(b"\x1bOB") == "down"
    assert parse_raw_key_bytes(b"\x1bOC") == "right"
    assert parse_raw_key_bytes(b"\x1bOD") == "left"

    # Modified / Ctrl / Shift arrows
    assert parse_raw_key_bytes(b"\x1b[1;5A") == "up"
    assert parse_raw_key_bytes(b"\x1b[1;5B") == "down"
    assert parse_raw_key_bytes(b"\x1b[1;5C") == "right"
    assert parse_raw_key_bytes(b"\x1b[1;5D") == "left"


def test_parse_raw_key_bytes_special_and_letters():
    assert parse_raw_key_bytes(b"\x1b") == "esc"
    assert parse_raw_key_bytes(b"\r") == "enter"
    assert parse_raw_key_bytes(b"\n") == "enter"
    assert parse_raw_key_bytes(b" ") == "space"
    assert parse_raw_key_bytes(b"r") == "r"
    assert parse_raw_key_bytes(b"R") == "r"
    assert parse_raw_key_bytes(b"c") == "c"
    assert parse_raw_key_bytes(b"v") == "v"
    assert parse_raw_key_bytes(b"q") == "q"
    assert parse_raw_key_bytes(b"1") == "1"
    assert parse_raw_key_bytes(b"") == "q"

    with pytest.raises(KeyboardInterrupt):
        parse_raw_key_bytes(b"\x03")


def test_get_single_key_non_tty_enter():
    with patch("sys.stdin", io.StringIO("\n")):
        key = get_single_key()
        assert key == "enter"


def test_get_single_key_non_tty_aliases():
    with patch("sys.stdin", io.StringIO("y\n")):
        assert get_single_key() == "enter"

    with patch("sys.stdin", io.StringIO("d\n")):
        assert get_single_key() == "enter"

    with patch("sys.stdin", io.StringIO("s\n")):
        assert get_single_key() == "left"

    with patch("sys.stdin", io.StringIO("n\n")):
        assert get_single_key() == "left"

    with patch("sys.stdin", io.StringIO("right\n")):
        assert get_single_key() == "right"

    with patch("sys.stdin", io.StringIO("left\n")):
        assert get_single_key() == "left"

    with patch("sys.stdin", io.StringIO("up\n")):
        assert get_single_key() == "up"

    with patch("sys.stdin", io.StringIO("down\n")):
        assert get_single_key() == "down"

    with patch("sys.stdin", io.StringIO("r\n")):
        assert get_single_key() == "r"

    with patch("sys.stdin", io.StringIO("c\n")):
        assert get_single_key() == "c"

    with patch("sys.stdin", io.StringIO("q\n")):
        assert get_single_key() == "q"


def test_get_single_key_non_tty_empty_eof():
    with patch("sys.stdin", io.StringIO("")):
        assert get_single_key() == "q"


def test_get_single_key_with_prompt(capsys):
    with patch("sys.stdin", io.StringIO("r\n")):
        key = get_single_key(prompt="Choose: ")
        assert key == "r"
        captured = capsys.readouterr()
        assert "Choose: " in captured.out
