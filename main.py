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
    # PSEUDOCODE:
    # - require exactly one path arg (plus optional --debug); else print usage,
    #   return 1
    # - try:
    #       drone_map = MapParser().parse(path)
    #   except MapError as exc:
    #       print(exc) to stderr; return 1
    # - print a short "OK" summary (zone count, connection count, nb_drones)
    # - if --debug: dump the parsed zones/connections
    # - return 0
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
