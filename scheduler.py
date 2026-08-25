"""Fleet scheduler: turn a flow into a per-drone dispatch (Phase 3).

Bridges ``MinCostMaxFlow`` and the ``Simulation``. ``solve`` grows the flow to
``min(maxflow, nb_drones)`` lanes, decomposes it, water-fills the drones across
those lanes, and returns one ``Drone`` per drone carrying its lane route and a
release turn (when it may leave the start).

Water-filling (``_assign``): drones on one lane leave one turn apart, so a lane
of turn-length ``L`` already carrying ``count`` drones would land the next one
at turn ``count + L``. Each drone is placed on the lane minimizing that value,
and its release turn is that lane's ``count`` before placement. Greedily
minimizing each drone's landing turn minimizes the last landing (the makespan).

Why capacity is never violated at run time: the lanes come out of a feasible
flow, so node/link caps already hold for one drone per lane per turn.
Staggering each successive drone on a lane by one turn keeps every downstream
cap satisfied, so the dispatch is feasible *by construction* — no reservation
table, no conflict resolution, no deadlock (the flow is acyclic source->sink).
"""

from __future__ import annotations

from drone import Drone
from drone_map import DroneMap
from mcmf import MinCostMaxFlow
from errors import SolveError


class Scheduler:
    """Turns a ``DroneMap`` into a makespan-minimizing fleet dispatch.

    Attributes:
        _map: The validated map to route the fleet across.
        _nb_drones: Drones that must reach the end (``drone_map.nb_drones``).
    """

    def __init__(self, drone_map: DroneMap) -> None:
        """Bind the scheduler to a validated map.

        Args:
            drone_map: Parsed, validated map with non-``None`` start and end
                and a positive ``nb_drones``.
        """
        assert drone_map.start is not None and drone_map.end is not None
        self._map = drone_map
        self._nb_drones = drone_map.nb_drones

    def solve(self) -> list[Drone]:
        """Compute the best dispatch: which lane and release turn per drone.

        Returns:
            One ``Drone`` per drone to route, each carrying its lane route and
            release turn, ordered by id. Ready to feed straight into
            ``Simulation``.

        Raises:
            SolveError: If the end is unreachable (max flow is 0), so no drone
                can ever be delivered.
        """
        mcmf = MinCostMaxFlow(self._map)
        flow = mcmf.run_to(self._nb_drones)
        if flow == 0:
            raise SolveError("no path from start to end (max flow is 0)")
        lanes = mcmf.decompose()
        assignments = self._assign(lanes)
        return [
            Drone(i, lane, release_turn)
            for i, (lane, release_turn) in enumerate(assignments, start=1)]

    def _assign(self, lanes: list[list[str]]) -> list[tuple[list[str], int]]:
        """Water-fill the fleet across ``lanes`` to minimize makespan.

        Args:
            lanes: Candidate lane routes (each ``[start, ..., end]``).

        Returns:
            Per drone, a ``(lane_route, release_turn)`` pair. The k-th drone
            placed on a lane gets release turn = that lane's running count
            before placement, so drones on one lane leave one turn apart.
        """
        lengths = [self._lane_length(lane) for lane in lanes]
        count = [0] * len(lengths)
        assignments: list[tuple[list[str], int]] = []

        for _ in range(self._nb_drones):
            best = min(
                range(len(lengths)),
                key=lambda lane: count[lane] + lengths[lane]
            )
            assignments.append((lanes[best], count[best]))
            count[best] += 1
        return assignments

    def _lane_length(self, lane: list[str]) -> int:
        """Turns one drone alone needs to fly a lane (restricted counts 2).

        Args:
            lane: A zone-name sequence ``[start, ..., end]`` from decompose.

        Returns:
            Sum of ``turn_cost`` of every zone entered (the start is free).
        """
        return sum(self._map.zones[zone].turn_cost for zone in lane[1:])
