"""Tokenizer layer: raw text line -> typed record (Zone / Connection / int).

This is the *syntactic* layer. It classifies each line, parses its fields, and
builds the corresponding model object (whose ``__post_init__`` does per-field
validation). It raises plain ``ValueError`` on bad syntax; the parser wraps
those into ``MapError`` with the line number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from connection import Connection
from zone import Zone, ZoneType


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
        stripped = line.strip()
        if not stripped:
            return LineKind.BLANK
        if stripped.startswith("#"):
            return LineKind.COMMENT
        if stripped.startswith("nb_drones:"):
            return LineKind.DRONE_COUNT
        if stripped.startswith("start_hub:"):
            return LineKind.START_HUB
        if stripped.startswith("end_hub:"):
            return LineKind.END_HUB
        if stripped.startswith("hub:"):
            return LineKind.HUB
        if stripped.startswith("connection:"):
            return LineKind.CONNECTION
        return LineKind.UNKNOWN

    def parse_drone_count(self, line: str) -> int:
        """Parse a ``nb_drones: N`` line.

        Args:
            line: Raw source line.

        Returns:
            The positive drone count.

        Raises:
            ValueError: If the value is missing or not a positive integer.
        """
        value = line.split(":", 1)[1].strip()
        count = int(value)
        if count <= 0:
            raise ValueError("nb_drones must be positive")
        return count

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
        values = line.split(":", 1)[1].strip()

        # Groups: 1=name (no dash/space), 2=x, 3=y, 4=optional [meta].
        # Anchored ^...$ so trailing junk fails the match.
        pattern = r"^([^-\s]+)\s+(\S+)\s+(\S+)(?:\s+\[([^\]]+)\])?\s*$"
        matched = re.match(pattern, values)
        if not matched:
            raise ValueError(f"invalid format for zone line: {line!r}")

        name, x_str, y_str, bracket = matched.groups()
        metadata = self._parse_metadata(bracket or "")
        return Zone(
            name,
            int(x_str),
            int(y_str),
            ZoneType.from_str(metadata.get("zone", "normal")),
            metadata.get("color"),
            int(metadata.get("max_drones", "1")),
            is_start,
            is_end,
        )

    def parse_connection(self, line: str) -> Connection:
        """Parse a ``connection: a-b [max_link_capacity=N]`` line.

        Args:
            line: Raw source line.

        Returns:
            A constructed (and per-field-validated) ``Connection``.

        Raises:
            ValueError: On a malformed endpoint pair or capacity.
        """
        values = line.split(":", 1)[1].strip()
        # Groups: 1=zone_a, 2=zone_b (exactly one '-' between, no dash/space
        # in names), 3=optional [meta].
        pattern = r"^([^-\s]+)-([^-\s]+)(?:\s+\[([^\]]+)\])?\s*$"
        matched = re.match(pattern, values)
        if not matched:
            raise ValueError(f"invalid format for connection line: {line!r}")
        name_a, name_b, bracket = matched.groups()
        metadata = self._parse_metadata(bracket or "")
        cap = int(metadata.get("max_link_capacity", "1"))
        return Connection(name_a, name_b, cap)

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
        meta: dict[str, str] = {}
        allowed = {"zone", "color", "max_drones", "max_link_capacity"}

        if not bracket.strip():
            return meta

        for token in bracket.split():
            if "=" not in token:
                raise ValueError(f"metadata token missing '=': {token!r}")
            key, value = token.split("=", 1)
            if key not in allowed:
                raise ValueError(f"unknown metadata key: {key!r}")
            if key in meta:
                raise ValueError(f"duplicate metadata key: {key!r}")
            meta[key] = value
        return meta
