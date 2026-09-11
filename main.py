"""CLI entry point: load a map, schedule the fleet, record the run.

Usage:
    python main.py <map_file>

Parses + validates the map, schedules all drones start -> end (min-cost
max-flow + water-filling), writes one line per simulation turn to
``result_<map_name>.txt``, and renders an HTML visualization. The blue
header, white run summary, and colored status go to stderr.
"""

from __future__ import annotations

import os
import sys

from errors import MapError, SolveError
from parser import MapParser
from scheduler import Scheduler
from simulation import Simulation
from visualizer import Visualizer

_RESET = "\033[0m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"


def _paint(text: str, code: str) -> str:
    """Wrap ``text`` in an ANSI ``code`` only when stderr is a terminal.

    Args:
        text: The message to color.
        code: The ANSI escape sequence to prepend.

    Returns:
        The colored string on a TTY, otherwise ``text`` unchanged.
    """
    return f"{code}{text}{_RESET}" if sys.stderr.isatty() else text


def ok(text: str) -> str:
    """Return a green ``✅``-prefixed status message."""
    return _paint(f"✅ {text}", _GREEN)


def err(text: str) -> str:
    """Return a red ``❌``-prefixed error message."""
    return _paint(f"❌ {text}", _RED)


def main(argv: list[str]) -> int:
    """Parse the map given on the command line and record the run.

    Args:
        argv: Full process argv (``argv[0]`` is the script name).

    Returns:
        Process exit code: ``0`` on success, ``1`` on a ``MapError``,
        ``SolveError``, bad usage, or an output-file write failure.
    """
    args = argv[1:]
    paths = [a for a in args if a != "--debug"]
    print((_paint("\nRUNNING FLY_IN...\n", _YELLOW)), file=sys.stderr)
    if len(paths) != 1:
        print(err("usage: python main.py <map_file>"),
              file=sys.stderr)
        return 1
    base = os.path.splitext(os.path.basename(paths[0]))[0]
    resultfile = f"result_{base}.txt"
    htmlfile = f"{base}.html"
    try:
        drone_map = MapParser().parse(paths[0])
        drones_path = Scheduler(drone_map).solve()
        lines = Simulation(drone_map, drones_path).run()
        Visualizer(drone_map, lines).render(htmlfile)
        with open(resultfile, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except (MapError, SolveError) as exc:
        print(err(str(exc)), file=sys.stderr)
        return 1
    except OSError as exc:
        print(err(f"cannot write output file: {exc}"), file=sys.stderr)
        return 1
    print(
        f"drones: {drone_map.nb_drones}   "
        f"zones: {len(drone_map.zones)}   "
        f"links: {len(drone_map.connections)}   "
        f"turns: {len(lines)}\n",
        file=sys.stderr
        )
    print(ok(f"wrote {resultfile}"), file=sys.stderr)
    print(ok(f"wrote {htmlfile}"), file=sys.stderr)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
