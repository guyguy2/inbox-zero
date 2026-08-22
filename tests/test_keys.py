from unittest.mock import patch, MagicMock
import io
import sys
from inbox_zero.keys import get_single_key


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
