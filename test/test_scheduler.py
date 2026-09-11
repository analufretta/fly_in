"""Unit tests for the Scheduler (flow -> staggered fleet).

Scheduler decomposes the MCMF flow into lanes and water-fills ``nb_drones``
across them, returning Drones with valid routes and staggered release turns.
Under test: drone count, route validity, id shape, lane splitting, staggering,
shorter-lane preference, and the no-path SolveError.
"""

from __future__ import annotations

from typing import Callable

import pytest

from drone_map import DroneMap
from errors import SolveError
from scheduler import Scheduler


def _fork_map(nb: int) -> str:
    """Two parallel lanes start->{a,b}->end carrying ``nb`` drones."""
    return (
        f"nb_drones: {nb}\n"
        "start_hub: s 0 0\n"
        "hub: a 1 1\n"
        "hub: b 1 -1\n"
        "end_hub: e 2 0\n"
        "connection: s-a\n"
        "connection: a-e\n"
        "connection: s-b\n"
        "connection: b-e\n"
    )


SINGLE_LANE = """\
nb_drones: 3
start_hub: s 0 0
hub: neck 1 0 [max_drones=1]
end_hub: e 2 0
connection: s-neck [max_link_capacity=1]
connection: neck-e [max_link_capacity=1]
"""

SHORT_AND_LONG = """\
nb_drones: 1
start_hub: s 0 0
hub: a 1 1
hub: x 1 -1
hub: y 2 -1
end_hub: e 3 0
connection: s-a
connection: a-e
connection: s-x
connection: x-y
connection: y-e
"""

NO_PATH = """\
nb_drones: 1
start_hub: s 0 0
end_hub: e 2 0
"""


def test_solve_returns_nb_drones(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """len(solve()) == map.nb_drones, even when there are fewer lanes."""
    drones = Scheduler(parse_map(_fork_map(4))).solve()
    assert len(drones) == 4


def test_every_route_is_start_to_end(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Each route starts at start, ends at end, every hop a real link."""
    dm = parse_map(_fork_map(4))
    for drone in Scheduler(dm).solve():
        assert drone.path[0] == dm.start
        assert drone.path[-1] == dm.end
        for u, v in zip(drone.path, drone.path[1:]):
            assert frozenset({u, v}) in dm.connections


def test_drone_ids_unique_and_1_based(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Ids are 1..nb_drones with no duplicates."""
    drones = Scheduler(parse_map(_fork_map(4))).solve()
    assert sorted(d.id for d in drones) == [1, 2, 3, 4]


def test_load_splits_across_parallel_lanes(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """On a fork map, drones distribute across both lanes."""
    drones = Scheduler(parse_map(_fork_map(2))).solve()
    used = {zone for d in drones for zone in d.path}
    assert "a" in used and "b" in used


def test_release_turns_stagger_on_shared_lane(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Drones forced onto one lane leave one turn apart (0, 1, 2)."""
    drones = Scheduler(parse_map(SINGLE_LANE)).solve()
    assert sorted(d.release_turn for d in drones) == [0, 1, 2]


def test_shorter_lane_preferred_first(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Water-filling sends the first drone down the shorter lane."""
    drones = Scheduler(parse_map(SHORT_AND_LONG)).solve()
    assert "a" in drones[0].path
    assert "x" not in drones[0].path


def test_no_path_raises_solve_error(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Max flow 0 (no start->end path) -> SolveError."""
    with pytest.raises(SolveError):
        Scheduler(parse_map(NO_PATH)).solve()
