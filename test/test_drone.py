"""Unit tests for the Drone entity (playback cursor).

Drone = one drone replaying a fixed route, one turn per ``fly`` call. Under
test: normal 1-turn hops, release-turn waiting, the 2-turn restricted-zone
transit (in-flight token then arrival), and delivery drop-out.
"""

from __future__ import annotations

from typing import Callable

from drone import Drone
from drone_map import DroneMap

LINE_MAP = """\
nb_drones: 1
start_hub: s 0 0
hub: a 1 0
end_hub: e 2 0
connection: s-a
connection: a-e
"""

RESTRICTED_MAP = """\
nb_drones: 1
start_hub: s 0 0
hub: r 1 0 [zone=restricted]
end_hub: e 2 0
connection: s-r
connection: r-e
"""


def test_fly_advances_one_zone_per_turn(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Normal route: each fly() returns 'D<id>-<next zone>' in order."""
    dm = parse_map(LINE_MAP)
    drone = Drone(1, ["s", "a", "e"])
    assert drone.fly(dm) == "D1-a"
    assert drone.fly(dm) == "D1-e"


def test_fly_returns_none_after_delivered(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Once at end, is_delivered is True and further fly() -> None."""
    dm = parse_map(LINE_MAP)
    drone = Drone(1, ["s", "a", "e"])
    drone.fly(dm)
    drone.fly(dm)
    assert drone.is_delivered is True
    assert drone.fly(dm) is None


def test_token_uses_given_id(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Token prefix is 'D<id>-' with the id passed in."""
    dm = parse_map(LINE_MAP)
    drone = Drone(7, ["s", "a", "e"])
    assert drone.fly(dm) == "D7-a"


def test_release_turn_holds_then_moves(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """release_turn=k -> first k fly() calls return None, then it moves."""
    dm = parse_map(LINE_MAP)
    drone = Drone(1, ["s", "a", "e"], release_turn=2)
    assert drone.fly(dm) is None
    assert drone.fly(dm) is None
    assert drone.fly(dm) == "D1-a"


def test_restricted_reports_in_flight_then_arrival(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Entering restricted r: turn1 'D1-s-r' (on edge), turn2 'D1-r'."""
    dm = parse_map(RESTRICTED_MAP)
    drone = Drone(1, ["s", "r", "e"])
    assert drone.fly(dm) == "D1-s-r"
    assert drone.fly(dm) == "D1-r"
    assert drone.fly(dm) == "D1-e"


def test_restricted_flight_turn_not_inside_zone(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """During the in-flight turn the drone has not entered r yet."""
    dm = parse_map(RESTRICTED_MAP)
    drone = Drone(1, ["s", "r", "e"])
    drone.fly(dm)  # in flight on s->r
    assert drone._pos == 0
    drone.fly(dm)  # arrives at r
    assert drone._pos == 1


def test_is_delivered_true_only_at_end(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """is_delivered flips True exactly when the end zone is reached."""
    dm = parse_map(LINE_MAP)
    drone = Drone(1, ["s", "a", "e"])
    assert drone.is_delivered is False
    drone.fly(dm)  # at a
    assert drone.is_delivered is False
    drone.fly(dm)  # at e
    assert drone.is_delivered is True
