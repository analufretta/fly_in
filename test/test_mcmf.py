"""Unit tests for the MinCostMaxFlow core.

Hand-built tiny graphs with a KNOWN optimal flow. Under test: max flow equals
the min cut, node-split zone capacity is honored, run_to respects its target,
the cheapest path is augmented first (min-cost, not just max-flow), decompose
returns valid start->end routes, and the no-path case terminates at zero.
"""

from __future__ import annotations

from typing import Callable

from drone_map import DroneMap
from mcmf import MinCostMaxFlow

DIAMOND = """\
nb_drones: 2
start_hub: s 0 0
hub: a 1 1
hub: b 1 -1
end_hub: e 2 0
connection: s-a
connection: a-e
connection: s-b
connection: b-e
"""

BOTTLENECK = """\
nb_drones: 5
start_hub: s 0 0
hub: gate 1 0 [max_drones=1]
end_hub: e 2 0
connection: s-gate [max_link_capacity=5]
connection: gate-e [max_link_capacity=5]
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

NORMAL_VS_RESTRICTED = """\
nb_drones: 1
start_hub: s 0 0
hub: n 1 1
hub: r 1 -1 [zone=restricted]
end_hub: e 2 0
connection: s-n
connection: n-e
connection: s-r
connection: r-e
"""

NO_PATH = """\
nb_drones: 1
start_hub: s 0 0
end_hub: e 2 0
"""


def test_run_to_reaches_known_max_flow(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """run_to(big) returns the graph's true max flow (min cut)."""
    assert MinCostMaxFlow(parse_map(DIAMOND)).run_to(99) == 2
    assert MinCostMaxFlow(parse_map(BOTTLENECK)).run_to(99) == 1


def test_run_to_capped_by_target(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """run_to(k) never pushes more than k units even with spare capacity."""
    assert MinCostMaxFlow(parse_map(DIAMOND)).run_to(1) == 1


def test_zone_capacity_enforced_via_node_split(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """max_drones=1 caps flow through a zone despite wide links."""
    assert MinCostMaxFlow(parse_map(BOTTLENECK)).run_to(99) == 1


def test_prefers_cheaper_shorter_path_first(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """The single cheapest augmentation uses the shorter path."""
    mcmf = MinCostMaxFlow(parse_map(SHORT_AND_LONG))
    mcmf.run_to(1)
    assert mcmf.decompose()[0] == ["s", "a", "e"]


def test_restricted_entry_cost_avoided(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """A single lane routes through the normal zone, not the restricted."""
    mcmf = MinCostMaxFlow(parse_map(NORMAL_VS_RESTRICTED))
    mcmf.run_to(1)
    lane = mcmf.decompose()[0]
    assert "n" in lane and "r" not in lane


def test_decompose_returns_flow_many_routes(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """len(decompose()) == achieved flow."""
    mcmf = MinCostMaxFlow(parse_map(DIAMOND))
    mcmf.run_to(99)
    assert len(mcmf.decompose()) == 2


def test_decomposed_routes_are_valid_paths(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """Every consecutive pair in a decomposed route is a real connection."""
    dm = parse_map(DIAMOND)
    mcmf = MinCostMaxFlow(dm)
    mcmf.run_to(99)
    for lane in mcmf.decompose():
        assert lane[0] == dm.start
        assert lane[-1] == dm.end
        for u, v in zip(lane, lane[1:]):
            assert frozenset({u, v}) in dm.connections


def test_no_path_terminates_with_zero_flow(
    parse_map: Callable[[str], DroneMap]
) -> None:
    """No source->sink path -> run_to returns 0 (augmentation stopped)."""
    assert MinCostMaxFlow(parse_map(NO_PATH)).run_to(99) == 0
