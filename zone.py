"""Zone model: a single hub/node in the drone map.

One ``@dataclass Zone`` plus a ``ZoneType`` enum — deliberately NOT a subclass
hierarchy (decision: single dataclass + enum keeps per-field validation in one
``__post_init__``). Movement cost and effective capacity are derived, not
stored twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ZoneType(Enum):
    """Kind of zone, which fixes traversal cost and passability."""

    NORMAL = "normal"
    PRIORITY = "priority"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"

    @classmethod
    def from_str(cls, value: str) -> "ZoneType":
        """Convert a metadata ``zone=`` string into a ``ZoneType``.

        Args:
            value: Raw type word from the map (e.g. ``"restricted"``).

        Returns:
            The matching ``ZoneType`` member.

        Raises:
            ValueError: If ``value`` is not one of the four known types.
        """
        zone_type = value.strip().lower()
        for kind in cls:
            if kind.value == zone_type:
                return kind
        raise ValueError(f"unknown zone type: {value!r}")


@dataclass
class Zone:
    """A hub the drones can occupy.

    Attributes:
        name: Unique identifier, no dashes or spaces.
        x: Integer coordinate (cosmetic — used only for visualization).
        y: Integer coordinate (cosmetic).
        zone_type: Traversal category (default ``NORMAL``).
        color: Optional single-word color tag (default ``None``).
        max_drones: Occupancy cap per turn (default ``1``); ignored/unlimited
            when ``is_start`` or ``is_end`` is set.
        is_start: True if this is the single start hub.
        is_end: True if this is the single end hub.
    """

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False

    @staticmethod
    def is_valid_name(name: str) -> bool:
        """Whether a string is a legal zone name.

        Zone owns this rule (a name is non-empty, has no ``-`` and no
        whitespace). ``Connection`` reuses it to validate endpoint names so the
        definition lives in exactly one place.

        Args:
            name: Candidate zone name.

        Returns:
            True if ``name`` is non-empty and free of dashes and whitespace.
        """
        return (
            bool(name)
            and "-" not in name
            and not any(c.isspace() for c in name)
        )

    def __post_init__(self) -> None:
        """Validate a single zone's fields (per-line rules).

        Raises:
            ValueError: On any invalid field; the parser wraps this into a
                ``MapError`` with the source line number.
        """
        if not Zone.is_valid_name(self.name):
            raise ValueError(f"invalid zone name: {self.name!r}")
        if self.max_drones < 1:
            raise ValueError(
                f"max_drones must be >= 1, got {self.max_drones}"
            )

    @property
    def turn_cost(self) -> int:
        """Turns needed to traverse this zone.

        Returns:
            ``1`` for normal/priority, ``2`` for restricted.
        """
        # PSEUDOCODE:
        # - restricted -> 2
        # - normal / priority -> 1
        # - blocked -> undefined for traversal; callers must exclude it first
        raise NotImplementedError

    @property
    def capacity(self) -> int:
        """Effective per-turn occupancy limit.

        Returns:
            A very large number (treated as unlimited) for start/end zones,
            otherwise ``max_drones``.
        """
        # PSEUDOCODE:
        # - if is_start or is_end -> return "unlimited" sentinel (large int)
        # - else -> return max_drones
        raise NotImplementedError

    @property
    def is_passable(self) -> bool:
        """Whether a drone may ever enter this zone.

        Returns:
            False for blocked zones, True otherwise.
        """
        # PSEUDOCODE: return zone_type is not BLOCKED
        raise NotImplementedError
