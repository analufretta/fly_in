"""Unit tests for the visualizer's pure data seam (_build_timeline).

Only the Python side is exercised (the browser layer has no Python). Under
test: the payload shape (zones/edges/turns/nb_drones and their fields), token
-> position decoding (zone vs edge), carry-forward of absent drones, the start
seed frame, and SolveError on malformed / unknown-zone tokens.
"""

from __future__ import annotations

from typing import Any, Callable, cast

import pytest

from drone_map import DroneMap
from errors import SolveError
from visualizer import Visualizer

TINY = """\
nb_drones: 2
start_hub: s 0 0 [color=green]
hub: mid 1 0 [color=blue]
end_hub: e 2 0 [color=red]
connection: s-mid
connection: mid-e
"""

RESTRICTED = """\
nb_drones: 1
start_hub: s 0 0
hub: r 1 0 [zone=restricted]
end_hub: e 2 0
connection: s-r
connection: r-e
"""


def _timeline(dm: DroneMap, lines: list[str]) -> dict[str, Any]:
    """Build the timeline payload for ``dm`` and move ``lines``."""
    return cast(dict[str, Any], Visualizer(dm, lines)._build_timeline())


def test_timeline_top_level_keys(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """_build_timeline returns zones/edges/turns/nb_drones."""
    payload = _timeline(parse_map(TINY), [])
    assert set(payload) >= {"zones", "edges", "turns", "nb_drones"}


def test_zone_payload_fields(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Each zone dict carries the documented fields."""
    payload = _timeline(parse_map(TINY), [])
    fields = {
        "name", "x", "y", "color", "max_drones",
        "type", "is_start", "is_end",
    }
    for zone in payload["zones"]:
        assert fields <= set(zone)


def test_edge_payload_fields(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Each edge dict carries a/b/capacity."""
    payload = _timeline(parse_map(TINY), [])
    for edge in payload["edges"]:
        assert {"a", "b", "capacity"} <= set(edge)


def test_all_drones_seed_at_start(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Turn 0 seeds every drone at the start hub."""
    payload = _timeline(parse_map(TINY), [])
    assert payload["turns"][0] == [
        {"kind": "zone", "zone": "s"},
        {"kind": "zone", "zone": "s"},
    ]


def test_zone_token_places_drone_in_zone(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """'D1-mid' -> turn entry {kind:'zone', zone:'mid'} for drone 1."""
    payload = _timeline(parse_map(TINY), ["D1-mid"])
    assert payload["turns"][1][0] == {"kind": "zone", "zone": "mid"}


def test_edge_token_places_drone_on_edge(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """'D1-s-r' -> {kind:'edge', src:'s', dst:'r'}."""
    payload = _timeline(parse_map(RESTRICTED), ["D1-s-r"])
    assert payload["turns"][1][0] == {
        "kind": "edge", "src": "s", "dst": "r",
    }


def test_absent_drone_carries_position_forward(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """A drone missing from a turn line keeps its previous position."""
    payload = _timeline(parse_map(TINY), ["D1-mid"])
    # D2 never moved -> still at the start hub in turn 1.
    assert payload["turns"][1][1] == {"kind": "zone", "zone": "s"}


def test_malformed_token_raises_solve_error(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """A token that isn't D<id>-... raises SolveError."""
    with pytest.raises(SolveError):
        _timeline(parse_map(TINY), ["X1-mid"])


def test_unknown_zone_token_raises_solve_error(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """A token naming a zone not in the map raises SolveError."""
    with pytest.raises(SolveError):
        _timeline(parse_map(TINY), ["D1-ghost"])
