"""Shortest-path solver over the zone graph (Phase 2, single drone).

A hand-rolled Dijkstra (no graph libraries) that finds the minimum-turn route
from the map's start zone to its end zone for one drone.

Cost model: a path's cost is the sum of the ``turn_cost`` of each zone
*entered* (start is free). normal/priority = 1 turn, restricted = 2. Blocked
zones are never entered. Priority zones are preferred without changing the turn
count via a lexicographic key ``(total_turns, non_priority_entered)`` — among
equally fast routes, the one crossing the most priority zones wins.

Phase 3's flow solver will reuse this graph adjacency + relaxation shape.
"""

from __future__ import annotations

import heapq

from drone_map import DroneMap
from zone import Zone, ZoneType


class PathFinder:
    """Finds the fewest-turn route for a single drone across a ``DroneMap``."""

    def __init__(self, drone_map: DroneMap) -> None:
        """Bind the solver to a validated map.

        Args:
            drone_map: A parsed and validated map. ``start`` and ``end`` are
                assumed non-``None`` (guaranteed by ``DroneMap.validate``).
        """
        self._map = drone_map

    def _enter_cost(self, zone: Zone) -> tuple[int, int]:
        """Lexicographic cost of *entering* ``zone``.

        Args:
            zone: The destination zone being stepped into.

        Returns:
            ``(turn_cost, priority_penalty)`` where ``priority_penalty`` is
            ``0`` for priority zones and ``1`` otherwise, so ties on turn count
            resolve toward priority zones.
        """
        penalty = 0 if zone.zone_type is ZoneType.PRIORITY else 1
        return (zone.turn_cost, penalty)

    def shortest_path(self) -> list[str] | None:
        """Compute the minimum-turn route from start to end.

        Returns:
            The zone-name sequence ``[start, ..., end]`` (both endpoints
            included) on success, or ``None`` if the end is unreachable.
        """
        start, end = self._map.start, self._map.end

        assert start is not None and end is not None  # ensured by validate()

        best: dict[str, tuple[int, int]] = {start: (0, 0)}
        prev: dict[str, str] = {}
        explored: list[tuple[int, int, str]] = [(0, 0, start)]

        while explored:
            turns, penalty, name = heapq.heappop(explored)
            if (turns, penalty) > best[name]:
                continue
            if name == end:
                break
            for neighbor in self._map.neighbors(name):
                zone = self._map.zones[neighbor]
                if not zone.is_passable:
                    continue
                next_turns, next_penalty = self._enter_cost(zone)
                candidate = (turns + next_turns, penalty + next_penalty)
                if neighbor not in best or candidate < best[neighbor]:
                    best[neighbor] = candidate
                    prev[neighbor] = name
                    heapq.heappush(explored, (*candidate, neighbor))
        if end not in best:
            return None
        return self._reconstruct(prev, start, end)

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
        path = [end]
        zone = end
        while zone != start:
            zone = prev[zone]
            path.append(zone)
        path.reverse()
        return path
