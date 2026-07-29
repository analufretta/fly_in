"""Custom exceptions for the drone-map parser.

A single exception type carries the source line number and a human-readable
cause so the program can stop with a clear message (subject: "line + cause").
"""

from __future__ import annotations


class MapError(Exception):
    """Raised when a map file is syntactically or structurally invalid.

    Attributes:
        line_nb: 1-based line number in the source file where the error was
            detected. ``0`` means the error is not tied to a single line
            (e.g. a whole-graph rule such as "no start zone").
        cause: Short human-readable explanation of what is wrong.
        raw: The offending raw source line, if available (for context in the
            printed message).
    """

    def __init__(self, line_nb: int, cause: str, raw_line: str = "") -> None:
        """Store the context and build the formatted error message.

        Args:
            line_nb: 1-based source line number (``0`` if not line-specific).
            cause: Human-readable reason the map is invalid.
            raw: The original source line text, optional.
        """
        self.line_nb = line_nb
        self.cause = cause
        self.raw = raw_line
        if line_nb > 0:
            msg = f"[ERROR] line {line_nb}: {cause}"
        else:
            msg = f"[ERROR] {cause}"
        if raw_line:
            msg += f" -> {raw_line.strip()}"
        super().__init__(msg)
