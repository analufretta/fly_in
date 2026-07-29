"""Parser layer: orchestrates file -> Tokenizer -> DroneMap -> validate().

This is the single public entry for turning a map file path into a validated
``DroneMap``. It owns file I/O (via a context manager), the per-line loop, and
the translation of any ``ValueError`` from the tokenizer/models into a
``MapError`` carrying the offending line number.
"""

from __future__ import annotations

from drone_map import DroneMap
from errors import MapError
from tokenizer import LineKind, Tokenizer


class MapParser:
    """Turns a map file into a validated ``DroneMap`` object graph."""

    def __init__(self) -> None:
        """Set up the tokenizer used for every line."""
        self._tok = Tokenizer()

    def parse(self, path: str) -> DroneMap:
        """Read and fully validate a map file.

        Args:
            path: Filesystem path to the map file.

        Returns:
            A validated ``DroneMap`` ready for pathfinding.

        Raises:
            MapError: On any I/O failure or invalid syntax/structure. This is
                the ONLY exception type callers need to handle — no raw crash.
        """
        lines = self._read_lines(path)
        drone_map: DroneMap | None = None
        for line_nb, raw_line in enumerate(lines, start=1):
            kind = self._tok.classify(raw_line)
            if kind in (LineKind.BLANK, LineKind.COMMENT):
                continue
            try:
                if kind is LineKind.DRONE_COUNT:
                    if drone_map is not None:
                        raise ValueError("duplicate nb_drones")
                    drone_map = DroneMap(self._tok.parse_drone_count(raw_line))
                else:
                    if drone_map is None:
                        raise ValueError("content before nb_drones")
                    if kind is LineKind.START_HUB:
                        zone = self._tok.parse_zone(raw_line, True, False)
                        drone_map.add_zone(zone, line_nb)
                    elif kind is LineKind.END_HUB:
                        zone = self._tok.parse_zone(raw_line, False, True)
                        drone_map.add_zone(zone, line_nb)
                    elif kind is LineKind.HUB:
                        zone = self._tok.parse_zone(raw_line, False, False)
                        drone_map.add_zone(zone, line_nb)
                    elif kind is LineKind.CONNECTION:
                        conn = self._tok.parse_connection(raw_line)
                        drone_map.add_connection(conn, line_nb)
                    else:
                        raise ValueError("unrecognized line")
            except ValueError as exc:
                raise MapError(line_nb, str(exc)) from exc
        if drone_map is None:
            raise MapError(0, "missing nb_drones")
        drone_map.validate()
        return drone_map

    def _read_lines(self, path: str) -> list[str]:
        """Read all lines from ``path`` using a context manager.

        Args:
            path: Filesystem path to the map file.

        Returns:
            The file's lines (without trailing newlines).

        Raises:
            MapError: If the file cannot be opened or read.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read().splitlines()
        except OSError as exc:
            raise MapError(0, f"cannot read file: {exc}") from exc
