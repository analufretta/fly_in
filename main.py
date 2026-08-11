"""CLI entry point (Phase 2): load a map, solve one drone, print the run.

Usage:
    python main.py <map_file> [--debug]

Parses + validates the map, computes the single-drone route, and prints one
line per simulation turn to stdout. ``--debug`` dumps the parsed map summary
and adjacency to stderr. Multi-drone fleet + visualization arrive later.
"""

from __future__ import annotations

import sys

from errors import MapError, SolveError
from parser import MapParser
from pathfinder import PathFinder
from drone import Drone
from simulation import Simulation


def main(argv: list[str]) -> int:
    """Parse the map given on the command line and report success/failure.

    Args:
        argv: Full process argv (``argv[0]`` is the script name).

    Returns:
        Process exit code: ``0`` on a valid map, ``1`` on a ``MapError`` or
        bad usage.
    """
    args = argv[1:]
    debug = "--debug" in args
    paths = [a for a in args if a != "--debug"]
    if len(paths) != 1:
        print("usage: python main.py <map_file> [--debug]", file=sys.stderr)
        return 1
    try:
        drone_map = MapParser().parse(paths[0])
        route = PathFinder(drone_map).shortest_path()
        if route is None:
            raise SolveError("no path from start to end")
        sim = Simulation(drone_map, [Drone(1, route)])
        lines = sim.run()
    except (MapError, SolveError) as exc:
        print(exc, file=sys.stderr)
        return 1
    if debug:
        print(f"OK: {drone_map.nb_drones} drones, "
              f"{len(drone_map.zones)} zones, "
              f"{len(drone_map.connections)} connections", file=sys.stderr)
        for name in drone_map.zones:
            print(f"    zone {name} -> "
                  f"{drone_map.neighbors(name)}", file=sys.stderr)
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
