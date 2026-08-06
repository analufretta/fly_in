"""Shortest-path solver over the zone graph (Phase 2, single drone).

SCAFFOLD ONLY — signatures + pseudocode. Bodies not implemented yet.

Plan: a hand-rolled Dijkstra (no graph libraries) that finds the minimum-turn
route from the map's start zone to its end zone for one drone.

Cost model: a path's cost is the sum of the ``turn_cost`` of each zone
*entered* (start is free). normal/priority = 1 turn, restricted = 2. Blocked
zones are never entered. Priority zones are preferred without changing the turn
count via a lexicographic key ``(total_turns, non_priority_entered)`` — among
equally fast routes, the one crossing the most priority zones wins.

Phase 3's flow solver will reuse this graph adjacency + relaxation shape.
"""

from __future__ import annotations

from drone_map import DroneMap
from zone import Zone


class Pathfinder:
    """Finds the fewest-turn route for a single drone across a ``DroneMap``."""

    def __init__(self, drone_map: DroneMap) -> None:
        """Bind the solver to a validated map.

        Args:
            drone_map: A parsed and validated map. ``start`` and ``end`` are
                assumed non-``None`` (guaranteed by ``DroneMap.validate``).
        """
        # store drone_map on self
        raise NotImplementedError

    def _enter_cost(self, zone: Zone) -> tuple[int, int]:
        """Lexicographic cost of *entering* ``zone``.

        Args:
            zone: The destination zone being stepped into.

        Returns:
            ``(turn_cost, priority_penalty)`` where ``priority_penalty`` is
            ``0`` for priority zones and ``1`` otherwise, so ties on turn count
            resolve toward priority zones.
        """
        # penalty = 0 if zone is PRIORITY else 1
        # return (zone.turn_cost, penalty)
        raise NotImplementedError

    def shortest_path(self) -> list[str] | None:
        """Compute the minimum-turn route from start to end.

        Returns:
            The zone-name sequence ``[start, ..., end]`` (both endpoints
            included) on success, or ``None`` if the end is unreachable.
        """
        # start, end = self._map.start, self._map.end
        # best: dict[name -> (turns, penalty)]  = {start: (0, 0)}
        # prev: dict[name -> predecessor name]  = {}
        # heap of (turns, penalty, name), seeded with (0, 0, start)
        #
        # while heap:
        #   pop (turns, penalty, name) with smallest key
        #   skip if it's a stale entry (worse than best[name])
        #   stop early if name == end
        #   for each neighbor nbr of name:
        #       zone = map.zones[nbr]
        #       skip if not zone.is_passable   (blocked)
        #       cand = elementwise add of (turns, penalty) and _enter_cost(zone)
        #       if cand < best.get(nbr):  relax -> best[nbr]=cand, prev[nbr]=name,
        #                                 push onto heap
        #
        # if end not reached: return None
        # else: return self._reconstruct(prev, start, end)
        raise NotImplementedError

    def _reconstruct(
        self, prev: dict[str, str], start: str, end: str
    ) -> list[str]:
        """Rebuild the start->end zone sequence from the predecessor map.

        Args:
            prev: Predecessor of each settled zone.
            start: Start zone name.
            end: End zone name.

        Returns:
            Ordered zone names from ``start`` to ``end`` inclusive.
        """
        # walk backwards from end via prev until start, collecting names
        # reverse and return
        raise NotImplementedError
