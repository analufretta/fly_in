"""Drone entity: one drone playing back an assigned route.

A ``Drone`` owns its route (a zone-name sequence from the scheduler) and its
own turn-by-turn cursor state, and advances itself one turn at a time. Keeping
the per-turn state on the drone (not the simulation) is deliberate so the
simulation can drive a whole fleet with the same ``fly`` contract. Each drone
also carries a ``release_turn`` so the scheduler can stagger a lane's drones.

Restricted-zone transit (the one subtle case): entering a restricted zone
costs 2 turns. Turn 1 the drone is *on the connection* (in flight) and reports
``D<id>-<src>-<dst>``; turn 2 it arrives and reports ``D<id>-<dst>``. It is
never "in" the zone on the in-flight turn (matters for capacity accounting).
"""

from __future__ import annotations

from drone_map import DroneMap


class Drone:
    """A single drone advancing along a precomputed zone route.

    Attributes:
        id: Unique 1-based identifier used in output tokens (``D<id>-...``).
        path: Zone-name sequence ``[start, ..., end]`` this drone follows.
        release_turn: Turn (0-based) the drone may first leave the start; it
            emits nothing while waiting. Lets the scheduler stagger drones on a
            shared lane so downstream capacities hold by construction.
    """

    def __init__(
        self, drone_id: int, path: list[str], release_turn: int = 0
    ) -> None:
        """Create a drone parked at the start of ``path``.

        Args:
            drone_id: Unique 1-based id.
            path: Route from start to end (inclusive), from the scheduler.
            release_turn: Turns to wait at the start before moving (default 0,
                which preserves single-drone behaviour).
        """
        self.id: int = drone_id
        self.path: list[str] = path
        self.release_turn: int = release_turn
        self._wait: int = release_turn
        self._pos: int = 0
        self._in_flight: bool = False
        self._in_flight_dest: int | None = None
        self._delivered: bool = False

    @property
    def is_delivered(self) -> bool:
        """Whether this drone has reached the end zone.

        Returns:
            True once delivered (drops out of the simulation).
        """
        return self._delivered

    def fly(self, drone_map: DroneMap) -> str | None:
        """Advance the drone by exactly one turn and report its move.

        Args:
            drone_map: The map, for looking up destination zone turn costs.

        Returns:
            The move token for this turn (``D<id>-<zone>`` normally, or
            ``D<id>-<src>-<dst>`` while in flight to a restricted zone), or
            ``None`` if the drone is already delivered / does not move.
        """
        if self._delivered:
            return None
        if self._wait > 0:
            self._wait -= 1
            return None
        if self._in_flight:
            assert self._in_flight_dest is not None
            self._pos = self._in_flight_dest
            self._in_flight = False
            self._in_flight_dest = None
            dest_name = self.path[self._pos]
            if drone_map.zones[dest_name].is_end:
                self._delivered = True
            return f"D{self.id}-{dest_name}"

        nxt = self._pos + 1
        if nxt >= len(self.path):
            self._delivered = True
            return None

        dest_name = self.path[nxt]
        dest_zone = drone_map.zones[dest_name]
        if dest_zone.turn_cost == 2:
            self._in_flight = True
            self._in_flight_dest = nxt
            src = self.path[self._pos]
            return f"D{self.id}-{src}-{dest_name}"
        else:
            self._pos = nxt
            if dest_zone.is_end:
                self._delivered = True
            return f"D{self.id}-{dest_name}"
