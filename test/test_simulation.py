"""Unit tests for the Simulation turn loop.

Simulation drives a fleet: each turn it asks every undelivered drone to
``fly`` and joins the non-None tokens into one output line. Under test: line
composition (only movers appear, space-separated), delivered drop-out,
termination, the stall guard, and the empty-fleet case.
"""

from __future__ import annotations

from typing import Callable

import pytest

from drone import Drone
from drone_map import DroneMap
from errors import SolveError
from simulation import Simulation

LINE_MAP = """\
nb_drones: 1
start_hub: s 0 0
hub: a 1 0
end_hub: e 2 0
connection: s-a
connection: a-e
"""


def test_run_returns_one_string_per_turn(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """run() yields exactly as many lines as turns taken."""
    dm = parse_map(LINE_MAP)
    lines = Simulation(dm, [Drone(1, ["s", "a", "e"])]).run()
    assert lines == ["D1-a", "D1-e"]


def test_line_lists_only_moved_drones(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """A turn line = space-joined tokens of drones that moved that turn."""
    dm = parse_map(LINE_MAP)
    drones = [Drone(1, ["s", "a", "e"]), Drone(2, ["s", "a", "e"])]
    lines = Simulation(dm, drones).run()
    assert lines[0] == "D1-a D2-a"
    assert lines[1] == "D1-e D2-e"


def test_delivered_drones_drop_out(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Once delivered, a drone contributes no token to later lines."""
    dm = parse_map(LINE_MAP)
    drones = [
        Drone(1, ["s", "a", "e"]),
        Drone(2, ["s", "a", "e"], release_turn=2),
    ]
    lines = Simulation(dm, drones).run()
    assert "D1-a" in lines[0]
    assert any(line == "D2-a" for line in lines)  # a line with only D2
    assert all("D1" not in line for line in lines[2:])


def test_single_drone_linear_sequence(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """One drone on a linear map yields the straightforward tokens."""
    dm = parse_map(LINE_MAP)
    lines = Simulation(dm, [Drone(1, ["s", "a", "e"])]).run()
    assert lines == ["D1-a", "D1-e"]
    assert lines[-1] == "D1-e"  # no trailing empty line


def test_stall_raises_solve_error(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """A turn with zero moves while a drone remains undelivered -> error."""
    dm = parse_map(LINE_MAP)
    # A lone drone still waiting emits nothing on turn 0, so the stall guard
    # fires instead of the loop spinning forever.
    stuck = Drone(1, ["s", "a", "e"], release_turn=1)
    with pytest.raises(SolveError):
        Simulation(dm, [stuck]).run()


def test_empty_fleet_returns_empty_list(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """No drones -> run() returns [] (nothing to do), no error."""
    dm = parse_map(LINE_MAP)
    assert Simulation(dm, []).run() == []
