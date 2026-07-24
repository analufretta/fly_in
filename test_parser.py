"""Unit tests for the map parser (Phase 1).

Covers a valid map end-to-end plus one case per error rule. Skeleton only:
each test states, in comments, the map fixture and the expected outcome.
"""

from __future__ import annotations

import pytest

from drone_map import DroneMap
from errors import MapError
from parser import MapParser


def _parse(text: str) -> DroneMap:
    """Write ``text`` to a temp file and parse it.

    Args:
        text: Full map file contents.

    Returns:
        The parsed ``DroneMap``.
    """
    # PSEUDOCODE:
    # - write text to a tmp_path file (or use tmp_path fixture)
    # - return MapParser().parse(that path)
    raise NotImplementedError


def test_valid_map_parses() -> None:
    """A well-formed map yields the expected zones/connections/nb_drones."""
    # PSEUDOCODE:
    # - feed the subject's example map
    # - assert nb_drones, len(zones), len(connections)
    # - assert start/end names set correctly
    raise NotImplementedError


def test_missing_nb_drones() -> None:
    """A map without nb_drones raises MapError."""
    # PSEUDOCODE: parse map lacking nb_drones -> pytest.raises(MapError)
    raise NotImplementedError


def test_two_start_zones() -> None:
    """A second start_hub raises MapError."""
    # PSEUDOCODE: map with two start_hub lines -> MapError
    raise NotImplementedError


def test_duplicate_zone_name() -> None:
    """Re-using a zone name raises MapError."""
    raise NotImplementedError


def test_duplicate_connection() -> None:
    """Declaring a-b then b-a raises MapError (order-independent)."""
    raise NotImplementedError


def test_connection_unknown_zone() -> None:
    """A connection to an undefined zone raises MapError."""
    raise NotImplementedError


def test_zone_name_with_dash() -> None:
    """A zone name containing '-' raises MapError."""
    raise NotImplementedError


def test_bad_metadata_token() -> None:
    """A metadata token without '=' raises MapError."""
    raise NotImplementedError


def test_error_carries_line_number() -> None:
    """MapError reports the 1-based line number of the offending line."""
    # PSEUDOCODE:
    # - craft a map whose 4th line is invalid
    # - with pytest.raises(MapError) as info: parse
    # - assert info.value.line_no == 4
    raise NotImplementedError
