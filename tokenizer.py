"""Tokenizer layer: raw text line -> typed record (Zone / Connection / int).

This is the *syntactic* layer. It classifies each line, parses its fields, and
builds the corresponding model object (whose ``__post_init__`` does per-field
validation). It raises plain ``ValueError`` on bad syntax; the parser wraps
those into ``MapError`` with the line number.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from connection import Connection
from zone import Zone


class LineKind(Enum):
    """Classification of a single source line."""

    BLANK = auto()
    COMMENT = auto()
    DRONE_COUNT = auto()
    START_HUB = auto()
    END_HUB = auto()
    HUB = auto()
    CONNECTION = auto()
    UNKNOWN = auto()


@dataclass
class Tokenizer:
    """Stateless helper that turns one line into a typed record."""

    def classify(self, line: str) -> LineKind:
        """Determine what kind of content a raw line holds.

        Args:
            line: Raw source line (untrimmed).

        Returns:
            The matching ``LineKind``; ``UNKNOWN`` for anything unrecognized.
        """
        # PSEUDOCODE:
        # - stripped = line.strip()
        # - "" -> BLANK
        # - startswith "#" -> COMMENT
        # - startswith "nb_drones:" -> DRONE_COUNT
        # - startswith "start_hub:" -> START_HUB
        # - startswith "end_hub:" -> END_HUB
        # - startswith "hub:" -> HUB
        # - startswith "connection:" -> CONNECTION
        # - else -> UNKNOWN
        raise NotImplementedError

    def parse_drone_count(self, line: str) -> int:
        """Parse a ``nb_drones: N`` line.

        Args:
            line: Raw source line.

        Returns:
            The positive drone count.

        Raises:
            ValueError: If the value is missing or not a positive integer.
        """
        # PSEUDOCODE:
        # - split on ':' once, take the right side, strip
        # - int() it (ValueError bubbles if non-numeric)
        # - require > 0 else raise ValueError("nb_drones must be positive")
        raise NotImplementedError

    def parse_zone(self, line: str, is_start: bool, is_end: bool) -> Zone:
        """Parse a hub line into a ``Zone``.

        Handles ``start_hub:``, ``end_hub:`` and ``hub:`` — the caller sets the
        ``is_start`` / ``is_end`` flags based on the line prefix.

        Args:
            line: Raw source line.
            is_start: True when parsing a ``start_hub:`` line.
            is_end: True when parsing an ``end_hub:`` line.

        Returns:
            A constructed (and per-field-validated) ``Zone``.

        Raises:
            ValueError: On malformed name/coordinates/metadata.
        """
        # PSEUDOCODE:
        # - drop the prefix up to and including ':'
        # - split remainder; separate the optional "[...]" metadata block from
        #   the "name x y" head (metadata is whatever is inside brackets)
        # - head tokens -> name, x, y  (require exactly 3; int() the coords)
        # - meta = self._parse_metadata(bracket_text)
        # - zone_type = ZoneType.from_str(meta.get("zone", "normal"))
        # - color = meta.get("color")  (None if absent)
        # - max_drones = int(meta.get("max_drones", "1"))
        # - build and return Zone(name, x, y, zone_type, color, max_drones,
        #                          is_start, is_end)
        raise NotImplementedError

    def parse_connection(self, line: str) -> Connection:
        """Parse a ``connection: a-b [max_link_capacity=N]`` line.

        Args:
            line: Raw source line.

        Returns:
            A constructed (and per-field-validated) ``Connection``.

        Raises:
            ValueError: On a malformed endpoint pair or capacity.
        """
        # PSEUDOCODE:
        # - drop prefix up to ':'
        # - separate optional "[...]" metadata from the "a-b" head
        # - split head on '-' -> exactly two names (reject 0 or >1 dash)
        # - meta = self._parse_metadata(bracket_text)
        # - cap = int(meta.get("max_link_capacity", "1"))
        # - return Connection(name1, name2, cap)
        raise NotImplementedError

    def _parse_metadata(self, bracket: str) -> dict[str, str]:
        """Parse the optional ``[key=value ...]`` block, order-independent.

        Args:
            bracket: The text inside the brackets (may be empty string).

        Returns:
            Dict of key -> value (empty dict when no metadata present).

        Raises:
            ValueError: On a malformed token (missing '=', unknown key, or a
                duplicate key).
        """
        # PSEUDOCODE:
        # - if bracket is empty/whitespace -> return {}
        # - split on whitespace into tokens
        # - for each token: split once on '=' -> (key, value); no '=' is an error
        # - reject unknown keys (allowed: zone, color, max_drones,
        #   max_link_capacity) and duplicate keys within one block
        # - return the accumulated dict
        raise NotImplementedError
