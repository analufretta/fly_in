"""CLI entry point for Phase 1: load and validate a map file.

Usage:
    python main.py <map_file> [--debug]

Phase 1 scope only parses + validates and reports the result. Simulation and
visualization arrive in later phases.
"""

from __future__ import annotations

import sys

from errors import MapError
from parser import MapParser


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
    except MapError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"OK: {drone_map.nb_drones} drones, "
          f"{len(drone_map.zones)} zones, "
          f"{len(drone_map.connections)} connections")
    if debug:
        for name in drone_map.zones:
            print(f"    zone {name} -> {drone_map.neighbors(name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
