"""DroneMap model: the whole parsed map as an in-memory object graph.

Holds all zones + connections and owns the *graph-level* validation pass
(cross-record rules that a single Zone/Connection cannot check on its own).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from connection import Connection
from zone import Zone


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

    def add_zone(self, zone: Zone, line_no: int) -> None:
        """Register a zone, enforcing name uniqueness and single start/end.

        Args:
            zone: The already per-field-validated zone to add.
            line_no: Source line, for error reporting.

        Raises:
            MapError: On a duplicate name, or a second start/end zone.
        """
        # PSEUDOCODE:
        # - if zone.name already in self.zones -> MapError(line_no, "duplicate zone name")
        # - if zone.is_start:
        #       if self.start is not None -> MapError(line_no, "more than one start")
        #       set self.start = zone.name
        # - if zone.is_end: same guard for self.end
        # - store zones[zone.name] = zone
        raise NotImplementedError

    def add_connection(self, conn: Connection, line_no: int) -> None:
        """Register a connection, enforcing no-duplicate rule.

        Args:
            conn: The already per-field-validated connection to add.
            line_no: Source line, for error reporting.

        Raises:
            MapError: If this connection (order-independent) already exists.
        """
        # PSEUDOCODE:
        # - k = conn.key
        # - if k in self.connections -> MapError(line_no, "duplicate connection")
        # - store connections[k] = conn
        # NOTE: endpoint-exists is deferred to validate() so connections may be
        #       declared in any order relative to... (they must follow zones per
        #       subject, but we still verify in the graph pass).
        raise NotImplementedError

    def neighbors(self, name: str) -> list[str]:
        """Names of zones directly connected to ``name``.

        Args:
            name: A zone name present in the map.

        Returns:
            List of adjacent zone names (empty if none).
        """
        # PSEUDOCODE:
        # - for each connection whose key contains name, collect conn.other(name)
        # - return the collected list
        raise NotImplementedError

    def validate(self) -> None:
        """Run all graph-level (cross-record) validation rules.

        Called once after every line is parsed. Per-field rules already ran in
        each Zone/Connection ``__post_init__``; this pass covers what needs the
        whole graph.

        Raises:
            MapError: On the first structural violation found.
        """
        # PSEUDOCODE (structural rules, order = cheapest/most-fundamental first):
        # - nb_drones present and >= 1
        # - exactly one start zone exists (self.start is not None)
        # - exactly one end zone exists (self.end is not None)
        # - every connection endpoint names a zone that exists in self.zones
        #     -> else MapError(line_no=0, "connection references unknown zone X")
        # - (reachability start->end is NOT checked here; that is a runtime
        #    pathfinding concern, per the parsing-choice decision)
        raise NotImplementedError
