"""DroneMap model: the whole parsed map as an in-memory object graph.

Holds all zones + connections and owns the *graph-level* validation pass
(cross-record rules that a single Zone/Connection cannot check on its own).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from connection import Connection
from zone import Zone
from errors import MapError


@dataclass
class DroneMap:
    """Validated collection of zones and connections plus drone count.

    Attributes:
        nb_drones: Positive number of drones to route start -> end.
        zones: Map of zone name -> ``Zone``.
        connections: Map of ``frozenset({a, b})`` -> ``Connection`` so
            duplicates (``a-b`` == ``b-a``) collapse to one key.
        start: Name of the start zone (set once found).
        end: Name of the end zone (set once found).
    """

    nb_drones: int
    zones: dict[str, Zone] = field(default_factory=dict)
    connections: dict[frozenset[str], Connection] = field(default_factory=dict)
    start: str | None = None
    end: str | None = None

    def add_zone(self, zone: Zone, line_nb: int) -> None:
        """Register a zone, enforcing name uniqueness and single start/end.

        Args:
            zone: The already per-field-validated zone to add.
            line_nb: Source line, for error reporting.

        Raises:
            MapError: On a duplicate name, or a second start/end zone.
        """
        if zone.name in self.zones.keys():
            raise MapError(line_nb, "duplicated zone name")
        if zone.is_start:
            if self.start is not None:
                raise MapError(line_nb, "more than one start point")
            self.start = zone.name
        if zone.is_end:
            if self.end is not None:
                raise MapError(line_nb, "more than one end point")
            self.end = zone.name
        self.zones[zone.name] = zone

    def add_connection(self, conn: Connection, line_nb: int) -> None:
        """Register a connection; enforce endpoint existence and no duplicate.

        The subject requires a connection to link only *previously defined*
        zones, so endpoint existence is checked here (both zones must already
        exist) rather than in a later pass, keeping the source line for the
        error message.

        Args:
            conn: The already per-field-validated connection to add.
            line_nb: Source line, for error reporting.

        Raises:
            MapError: If an endpoint names an unknown zone, or this connection
                (order-independent) already exists.
        """
        for endpoint in conn.key:
            if endpoint not in self.zones:
                raise MapError(
                    line_nb, f"connection references unknown zone {endpoint!r}"
                )
        k = conn.key
        if k in self.connections:
            raise MapError(line_nb, "duplicated connection")
        self.connections[k] = conn

    def neighbors(self, name: str) -> list[str]:
        """Names of zones directly connected to ``name``.

        Args:
            name: A zone name present in the map.

        Returns:
            List of adjacent zone names (empty if none).
        """
        neighborhood = []
        for conn in self.connections.values():
            if name in conn.key:
                neighborhood.append(conn.other(name))
        return neighborhood

    def validate(self) -> None:
        """Run all graph-level (cross-record) validation rules.

        Called once after every line is parsed. Per-field rules already ran in
        each Zone/Connection ``__post_init__``; this pass covers what needs the
        whole graph.

        Raises:
            MapError: On the first structural violation found. ``line_nb`` is
                ``0`` because these rules concern the map as a whole, not any
                single source line.
        """
        # Endpoint existence and per-line rules were already enforced at parse
        # time (add_connection / __post_init__). Start->end reachability is a
        # solver concern, not a validity rule (see parsing-choice decision).
        if self.nb_drones < 1:
            raise MapError(0, "nb_drones must be >= 1")
        if self.start is None:
            raise MapError(0, "map has no start zone")
        if self.end is None:
            raise MapError(0, "map has no end zone")
