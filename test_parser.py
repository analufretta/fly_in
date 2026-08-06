"""Unit tests for the map parser (Phase 1).

Covers a valid map end-to-end plus one case per error rule. Each error test
asserts that ``MapParser.parse`` raises ``MapError`` (never a raw crash), and
the line-number test checks the reported 1-based line.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from drone_map import DroneMap
from errors import MapError
from parser import MapParser

VALID_MAP = """\
nb_drones: 2
start_hub: s 0 0
end_hub: e 5 5
hub: a 1 1
hub: b 2 2
connection: s-a
connection: a-e
connection: s-b
"""


def _parse(text: str) -> DroneMap:
    """Write ``text`` to a temp file and parse it.

    Args:
        text: Full map file contents.

    Returns:
        The parsed ``DroneMap``.
    """
    fd, path = tempfile.mkstemp(suffix=".map", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        return MapParser().parse(path)
    finally:
        os.remove(path)


def test_valid_map_parses() -> None:
    """A well-formed map yields the expected zones/connections/nb_drones."""
    drone_map = _parse(VALID_MAP)
    assert drone_map.nb_drones == 2
    assert len(drone_map.zones) == 4
    assert len(drone_map.connections) == 3
    assert drone_map.start == "s"
    assert drone_map.end == "e"


def test_missing_nb_drones() -> None:
    """A map without nb_drones raises MapError."""
    with pytest.raises(MapError):
        _parse("# only a comment, no nb_drones\n")


def test_two_start_zones() -> None:
    """A second start_hub raises MapError."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "start_hub: t 1 1\n"
        "end_hub: e 2 2\n"
    )
    with pytest.raises(MapError):
        _parse(text)


def test_duplicate_zone_name() -> None:
    """Re-using a zone name raises MapError."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
        "hub: a 2 2\n"
        "hub: a 3 3\n"
    )
    with pytest.raises(MapError):
        _parse(text)


def test_duplicate_connection() -> None:
    """Declaring a-b then b-a raises MapError (order-independent)."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
        "connection: s-e\n"
        "connection: e-s\n"
    )
    with pytest.raises(MapError):
        _parse(text)


def test_connection_unknown_zone() -> None:
    """A connection to an undefined zone raises MapError."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
        "connection: s-x\n"
    )
    with pytest.raises(MapError):
        _parse(text)


def test_zone_name_with_dash() -> None:
    """A zone name containing '-' raises MapError."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
        "hub: a-b 2 2\n"
    )
    with pytest.raises(MapError):
        _parse(text)


def test_bad_metadata_token() -> None:
    """A metadata token without '=' raises MapError."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
        "hub: a 2 2 [restricted]\n"
    )
    with pytest.raises(MapError):
        _parse(text)


def test_error_carries_line_number() -> None:
    """MapError reports the 1-based line number of the offending line."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
        "hub: a-b 2 2\n"
    )
    with pytest.raises(MapError) as info:
        _parse(text)
    assert info.value.line_nb == 4
