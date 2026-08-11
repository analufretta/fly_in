"""Turn-by-turn simulation loop (Phase 2, single drone).

The ``Simulation`` drives a set of drones one turn at a time: each turn it asks
every not-yet-delivered drone to ``step`` and collects their move tokens into a
single space-separated output line. It stops when all drones are delivered.

Phase 2 runs exactly one drone, but the loop is written fleet-shaped so Phase 3
reuses it unchanged once a scheduler assigns routes to many drones.
"""

from __future__ import annotations

from drone import Drone
from drone_map import DroneMap
from errors import SolveError


class Simulation:
    """Plays drones along their routes and emits one output line per turn."""

    def __init__(self, drone_map: DroneMap, drones: list[Drone]) -> None:
        """Bind the loop to a map and the drones to route.

        Args:
            drone_map: The validated map the drones move across.
            drones: Drones to deliver, each carrying its own route.
        """
        self._map: DroneMap = drone_map
        self._drones: list[Drone] = drones

    def run(self) -> list[str]:
        """Run the simulation to completion.

        Returns:
            One string per simulation turn: the space-separated move tokens of
            every drone that moved that turn (drones that didn't move are
            omitted). Empty list only if there was nothing to do.

        Raises:
            SolveError: If a turn produces zero moves while drones remain
                undelivered (a stuck schedule — should be impossible for a
                single drone on a valid path; a safety guard).
        """
        lines: list[str] = []
        while not all(d.is_delivered for d in self._drones):
            line = []
            for d in self._drones:
                if (turn := d.step(self._map)) is not None:
                    line.append(turn)
            if line:
                lines.append(" ".join(line))
            else:
                raise SolveError("simulation stalled: no drone can move")
        return lines
