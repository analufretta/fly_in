"""Shared pytest fixtures for the Fly-in test suite.

Placing this file at the repository root also puts the root on ``sys.path`` so
the tests under ``test/`` can import the top-level modules (``drone_map``,
``parser``, ...) directly.

The ``parse_map`` fixture writes map text to a temp file and returns the
parsed, validated ``DroneMap`` — so tests build real maps through the actual
parser instead of hand-constructing objects.
"""

from __future__ import annotations

import os
import tempfile
from typing import Callable

import pytest

from drone_map import DroneMap
from parser import MapParser


@pytest.fixture
def parse_map() -> Callable[[str], DroneMap]:
    """Return a helper that parses map text into a ``DroneMap``.

    Returns:
        A function ``(text) -> DroneMap`` round-tripping through a temp file.
    """
    def _parse(text: str) -> DroneMap:
        fd, path = tempfile.mkstemp(suffix=".map", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            return MapParser().parse(path)
        finally:
            os.remove(path)
    return _parse
