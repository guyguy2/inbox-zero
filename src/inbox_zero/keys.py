"""Terminal single-keypress input handler for interactive email triage."""

from __future__ import annotations

import os
import sys
from typing import Optional


def parse_raw_key_bytes(raw_bytes: bytes) -> str:
    """Parse raw bytes from terminal into a normalized action key string."""
    if not raw_bytes:
        return "q"

    if raw_bytes in (b"\r", b"\n", b"\r\n"):
        return "enter"
    if raw_bytes == b"\x03":  # Ctrl+C
        raise KeyboardInterrupt
    if raw_bytes == b" ":
        return "space"

    # ANSI escape sequences (Arrow keys, Home, End, Page Up/Down, Esc)
    if raw_bytes.startswith(b"\x1b"):
        if (raw_bytes.startswith(b"\x1b[") or raw_bytes.startswith(b"\x1bO")) and raw_bytes.endswith(b"A"):
            return "up"
        if (raw_bytes.startswith(b"\x1b[") or raw_bytes.startswith(b"\x1bO")) and raw_bytes.endswith(b"B"):
            return "down"
        if (raw_bytes.startswith(b"\x1b[") or raw_bytes.startswith(b"\x1bO")) and raw_bytes.endswith(b"C"):
            return "right"
        if (raw_bytes.startswith(b"\x1b[") or raw_bytes.startswith(b"\x1bO")) and raw_bytes.endswith(b"D"):
            return "left"
        if raw_bytes in (b"\x1b[5~", b"\x1b[H"):
            return "up"
        if raw_bytes in (b"\x1b[6~", b"\x1b[F"):
            return "down"
        if raw_bytes == b"\x1b":
            return "esc"
        return "esc"

    try:
        char = raw_bytes.decode("utf-8", errors="ignore").lower().strip()
        return char if char else "enter"
    except Exception:
        return ""


def get_single_key(prompt: Optional[str] = None) -> str:
    """Read a single keypress or key sequence from terminal.

    Returns normalized string representations:
      - 'enter' for Return / Enter (\\r, \\n)
      - 'right' for Right Arrow (\\x1b[C)
      - 'left' for Left Arrow (\\x1b[D)
      - 'up' for Up Arrow (\\x1b[A)
      - 'down' for Down Arrow (\\x1b[B)
      - 'esc' for Escape key (\\x1b)
      - 'space' for Spacebar (' ')
      - 'q', 'r', 'c', 'v', 'y', 'n', 's', 'd', 'e', '1', '2', etc. for normal characters
    """
    if prompt:
        sys.stdout.write(prompt)
        sys.stdout.flush()

    # Non-TTY fallback (e.g., automated test runners, piped input)
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            return "q"
        clean = line.strip().lower()
        if not clean:
            return "enter"
        if clean in ("y", "yes", "d", "read"):
            return "enter"
        if clean in ("n", "no", "s", "skip"):
            return "left"
        if clean in ("right", "->"):
            return "right"
        if clean in ("left", "<-"):
            return "left"
        if clean in ("up", "^"):
            return "up"
        if clean in ("down", "v"):
            return "down" if clean == "down" else "v"
        return clean

    # Windows OS single-key input
    if os.name == "nt":
        try:
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                mapping = {
                    b"H": "up",
                    b"P": "down",
                    b"M": "right",
                    b"K": "left",
                }
                return mapping.get(ch2, "special")
            if ch in (b"\r", b"\n"):
                return "enter"
            if ch == b"\x1b":
                return "esc"
            if ch == b"\x03":  # Ctrl+C
                raise KeyboardInterrupt
            if ch == b" ":
                return "space"
            return ch.decode("utf-8", errors="ignore").lower()
        except ImportError:
            pass

    # POSIX (macOS & Linux) single-key input using direct OS-level non-buffered reads
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        # Direct os.read to bypass Python's TextIOWrapper/BufferedReader
        raw_bytes = os.read(fd, 32)
        if not raw_bytes:
            return "q"

        # If a lone escape byte arrived, check if remaining ANSI sequence arrives within 50ms
        if raw_bytes == b"\x1b":
            rlist, _, _ = select.select([fd], [], [], 0.05)
            if rlist:
                more_bytes = os.read(fd, 31)
                raw_bytes += more_bytes

        return parse_raw_key_bytes(raw_bytes)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
