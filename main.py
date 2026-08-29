"""CLI entry point: load a map, schedule the fleet, print the run.

Usage:
    python main.py <map_file> [--debug]

Parses + validates the map, schedules all drones start -> end (min-cost
max-flow + water-filling), and prints one line per simulation turn to stdout.
``--debug`` dumps the parsed map summary and adjacency to stderr.
"""

from __future__ import annotations

import os
import sys

from errors import MapError, SolveError
from parser import MapParser
from scheduler import Scheduler
from simulation import Simulation
from visualizer import Visualizer


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
        drones_path = Scheduler(drone_map).solve()
        sim = Simulation(drone_map, drones_path)
        lines = sim.run()
        outfile = os.path.splitext(os.path.basename(paths[0]))[0] + ".html"
        Visualizer(drone_map, lines).render(outfile)
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
    print(f"wrote {outfile}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
