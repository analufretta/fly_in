"""Connection model: an undirected edge between two zones."""

from __future__ import annotations

from dataclasses import dataclass

from zone import Zone


@dataclass
class Connection:
    """A bidirectional link between two zones.

    Identity is order-independent: ``a-b`` and ``b-a`` are the same connection.

    Attributes:
        zone_a: Name of one endpoint.
        zone_b: Name of the other endpoint.
        max_link_capacity: Max drones crossing this link per turn (default 1).
    """

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    def __post_init__(self) -> None:
        """Validate a single connection's fields (per-line rules).

        Endpoint *shape* is delegated to ``Zone.is_valid_name`` so the name
        rule has one owner. Endpoint *existence* is a graph rule, checked later
        in ``DroneMap.validate``.

        Raises:
            ValueError: On invalid fields; wrapped into ``MapError`` upstream.
        """
        for endpoint in (self.zone_a, self.zone_b):
            if not Zone.is_valid_name(endpoint):
                raise ValueError(f"invalid connection endpoint: {endpoint!r}")
        if self.zone_a == self.zone_b:
            raise ValueError(f"self-loop connection: {self.zone_a!r}")
        if self.max_link_capacity < 1:
            raise ValueError("connection capacity must be a positive integer")

    @property
    def key(self) -> frozenset[str]:
        """Order-independent identity used to detect duplicates.

        Returns:
            ``frozenset({zone_a, zone_b})`` so ``a-b`` == ``b-a``.
        """
        return frozenset({self.zone_a, self.zone_b})

    def other(self, name: str) -> str:
        """Return the endpoint opposite ``name``.

        Args:
            name: One endpoint of this connection.

        Returns:
            The other endpoint's name.

        Raises:
            ValueError: If ``name`` is not an endpoint of this connection.
        """
        if name == self.zone_a:
            return self.zone_b
        elif name == self.zone_b:
            return self.zone_a
        else:
            raise ValueError(f"{name!r} is not in this connection")
