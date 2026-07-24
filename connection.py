"""Connection model: an undirected edge between two zones."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Connection:
    """A bidirectional link between two zones.

    Identity is order-independent: ``a-b`` and ``b-a`` are the same connection.

    Attributes:
        zone_a: Name of one endpoint.
        zone_b: Name of the other endpoint.
        max_link_capacity: Max drones traversing this link per turn (default 1).
    """

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    def __post_init__(self) -> None:
        """Validate a single connection's fields (per-line rules).

        Raises:
            ValueError: On invalid fields; wrapped into ``MapError`` upstream.
        """
        # PSEUDOCODE (per-field only):
        # - zone_a and zone_b non-empty
        # - self-loop check: zone_a != zone_b (a connection to itself is invalid)
        # - max_link_capacity: integer >= 1
        # (endpoint-EXISTS is a graph rule -> DroneMap.validate, not here)
        raise NotImplementedError

    @property
    def key(self) -> frozenset[str]:
        """Order-independent identity used to detect duplicates.

        Returns:
            ``frozenset({zone_a, zone_b})`` so ``a-b`` == ``b-a``.
        """
        # PSEUDOCODE: return frozenset({zone_a, zone_b})
        raise NotImplementedError

    def other(self, name: str) -> str:
        """Return the endpoint opposite ``name``.

        Args:
            name: One endpoint of this connection.

        Returns:
            The other endpoint's name.

        Raises:
            ValueError: If ``name`` is not an endpoint of this connection.
        """
        # PSEUDOCODE:
        # - if name == zone_a -> return zone_b
        # - if name == zone_b -> return zone_a
        # - else raise ValueError (name not on this connection)
        raise NotImplementedError
