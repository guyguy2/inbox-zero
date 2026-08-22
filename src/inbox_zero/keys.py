"""Terminal single-keypress input handler for interactive email triage."""

from __future__ import annotations

import os
import sys
from typing import Optional


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

    # POSIX (macOS & Linux) single-key input
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt
        if ch == " ":
            return "space"
        if ch == "\x1b":
            # Check for following ANSI escape sequence (arrow keys, etc.)
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
            if rlist:
                ch2 = sys.stdin.read(1)
                if ch2 in ("[", "O"):
                    ch3 = sys.stdin.read(1)
                    if ch3 == "A":
                        return "up"
                    elif ch3 == "B":
                        return "down"
                    elif ch3 == "C":
                        return "right"
                    elif ch3 == "D":
                        return "left"
                    elif ch3 in ("1", "2", "3", "4", "5", "6"):
                        # Consume trailing '~'
                        _ = sys.stdin.read(1)
                        return "esc"
                return "esc"
            return "esc"
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
