"""Drone entity: one drone playing back an assigned route (Phase 2).

SCAFFOLD ONLY — signatures + pseudocode. Bodies not implemented yet.

A ``Drone`` owns its route (a zone-name sequence from the pathfinder) and its
own turn-by-turn cursor state, and advances itself one turn at a time. Keeping
the per-turn state on the drone (not the simulation) is deliberate so Phase 3
can drive a whole fleet with the same ``step`` contract.

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
    """

    def __init__(self, drone_id: int, path: list[str]) -> None:
        """Create a drone parked at the start of ``path``.

        Args:
            drone_id: Unique 1-based id.
            path: Route from start to end (inclusive), from the pathfinder.
        """
        # self.id = drone_id
        # self.path = path
        # cursor state:
        #   self._pos = 0            index in path of current confirmed zone
        #   self._in_flight = False  True while crossing to a restricted zone
        #   self._fly_dest = None    path index being flown toward, if in flight
        #   self._delivered = False  True once the end zone is reached
        raise NotImplementedError

    @property
    def is_delivered(self) -> bool:
        """Whether this drone has reached the end zone.

        Returns:
            True once delivered (drops out of the simulation).
        """
        # return self._delivered
        raise NotImplementedError

    def step(self, drone_map: DroneMap) -> str | None:
        """Advance the drone by exactly one turn and report its move.

        Args:
            drone_map: The map, for looking up destination zone turn costs.

        Returns:
            The move token for this turn (``D<id>-<zone>`` normally, or
            ``D<id>-<src>-<dst>`` while in flight to a restricted zone), or
            ``None`` if the drone is already delivered / does not move.
        """
        # if self._delivered: return None
        #
        # if self._in_flight:                       # arriving from a link
        #     self._pos = self._fly_dest
        #     self._in_flight = False; self._fly_dest = None
        #     dest = self.path[self._pos]
        #     if dest == end: self._delivered = True
        #     return f"D{id}-{dest}"
        #
        # nxt = self._pos + 1
        # if nxt >= len(self.path):                 # nothing left to do
        #     self._delivered = True; return None
        #
        # dest_name = self.path[nxt]
        # dest_zone = drone_map.zones[dest_name]
        # if dest_zone.turn_cost == 2:              # restricted -> go in flight
        #     self._in_flight = True; self._fly_dest = nxt
        #     src = self.path[self._pos]
        #     return f"D{id}-{src}-{dest_name}"     # connection token
        # else:                                     # normal/priority 1-turn hop
        #     self._pos = nxt
        #     if dest_name == end: self._delivered = True
        #     return f"D{id}-{dest_name}"
        raise NotImplementedError
