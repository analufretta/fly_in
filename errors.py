"""Custom exceptions for the drone-map parser.

A single exception type carries the source line number and a human-readable
cause so the program can stop with a clear message (subject: "line + cause").
"""

from __future__ import annotations


class MapError(Exception):
    """Raised when a map file is syntactically or structurally invalid.

    Attributes:
        line_no: 1-based line number in the source file where the error was
            detected. ``0`` means the error is not tied to a single line
            (e.g. a whole-graph rule such as "no start zone").
        cause: Short human-readable explanation of what is wrong.
        raw: The offending raw source line, if available (for context in the
            printed message).
    """

    def __init__(self, line_no: int, cause: str, raw: str = "") -> None:
        """Store the context and build the formatted error message.

        Args:
            line_no: 1-based source line number (``0`` if not line-specific).
            cause: Human-readable reason the map is invalid.
            raw: The original source line text, optional.
        """
        # PSEUDOCODE:
        # - keep line_no, cause, raw on self so callers can inspect them
        # - compose message:
        #     if line_no > 0:  "map error on line {line_no}: {cause}"
        #     else:            "map error: {cause}"
        #   append "  ->  {raw.strip()}" when raw is non-empty
        # - call super().__init__(message)
        raise NotImplementedError
