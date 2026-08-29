"""Browser visualizer: turn a solved run into a self-contained HTML file.

Pipeline:
    DroneMap + Simulation.run() token lines
        -> build_timeline()   (pure Python: tokens -> per-turn positions)
        -> render(outfile)    (inject JSON into HTML/CSS/JS templates)
        -> one self-contained .html a browser animates.

Split of concerns (why this file is thin):
    Python only produces *data* + assembles the output string. All animation
    lives in ``viz.js`` (runs in the browser). This module never executes JS.

Token grammar (from ``drone.py``), the only thing build_timeline must decode:
    ``D<id>-<zone>``        drone <id> is IN <zone> this turn.
    ``D<id>-<src>-<dst>``   drone <id> is IN FLIGHT on edge src->dst
                            (restricted entry, turn 1 of 2). Edge midpoint.
    A drone absent from a turn line did not move -> carry its previous position
    forward. Delivered drones stop emitting and hold at the end zone.
"""

from __future__ import annotations

import json
import os

from drone_map import DroneMap
from errors import SolveError


class Visualizer:
    """Builds an animated HTML view of a solved drone run.

    Attributes:
        _map: The validated map (zones with x/y/color/capacity, connections).
        _turn_lines: Output of ``Simulation.run()`` — one space-separated
            token string per simulation turn (moved drones only).
    """

    def __init__(self, drone_map: DroneMap, turn_lines: list[str]) -> None:
        """Bind the visualizer to a map and its per-turn move tokens.

        Args:
            drone_map: The map the drones traversed.
            turn_lines: One string per turn from ``Simulation.run()``.
        """
        self._map: DroneMap = drone_map
        self._turn_lines: list[str] = turn_lines

    # ------------------------------------------------------------------ #
    # Data side                                                          #
    # ------------------------------------------------------------------ #

    def _build_timeline(self) -> dict[str, object]:
        """Reduce the run to a JSON-ready payload the JS animates.

        The real correctness seam. Everything visual is downstream of this,
        so this is what ``test/test_visualizer.py`` exercises.

        Returns:
            A dict shaped for ``json.dumps``:
                {
                  "zones":   [ <_zone_payload per zone> ],
                  "edges":   [ <_edge_payload per connection> ],
                  "turns":   [ [ <position>, ... ], ... ],
                  "nb_drones": int,
                }
            where each turn is a list indexed by ``drone_id - 1`` and each
            <position> is one of:
                {"kind": "zone", "zone": <name>}
                {"kind": "edge", "src": <name>, "dst": <name>}
            ``turns[0]`` is the seed frame (all drones at the start hub); one
            frame per ``run()`` line follows.
        """
        start = self._map.start
        assert start is not None
        nb = self._map.nb_drones
        positions: list[dict[str, str]] = [
            {"kind": "zone", "zone": start} for _ in range(nb)
        ]
        turns: list[list[dict[str, str]]] = [list(positions)]
        for line in self._turn_lines:
            for token in line.split():
                drone_id, position = self._parse_token(token)
                if not 1 <= drone_id <= nb:
                    raise SolveError(f"drone id out of range: {token!r}")
                positions[drone_id - 1] = position
            turns.append(list(positions))
        return {
            "zones": [
                self._zone_payload(name) for name in self._map.zones.keys()
            ],
            "edges": [
                self._edge_payload(conn.zone_a, conn.zone_b)
                for conn in self._map.connections.values()
            ],
            "turns": turns,
            "nb_drones": nb,
        }

    def _parse_token(self, token: str) -> tuple[int, dict[str, str]]:
        """Decode one ``D<id>-...`` move token into (drone_id, position).

        Args:
            token: A single whitespace-free move token from a turn line.

        Returns:
            (drone_id, position) where position matches the <position> shape
            documented on ``build_timeline``.

        Raises:
            SolveError: If the token is malformed or names an unknown zone.
        """
        if not token.startswith("D"):
            raise SolveError(f"malformed move token: {token!r}")
        parts = token[1:].split("-")
        try:
            drone_id = int(parts[0])
        except ValueError:
            raise SolveError(f"malformed drone id in token: {token!r}")
        names = parts[1:]
        for name in names:
            if name not in self._map.zones:
                raise SolveError(f"unknown zone {name!r} in token: {token!r}")
        if len(names) == 1:
            return drone_id, {"kind": "zone", "zone": names[0]}
        if len(names) == 2:
            return drone_id, {"kind": "edge", "src": names[0], "dst": names[1]}
        raise SolveError(f"malformed move token: {token!r}")

    def _zone_payload(self, name: str) -> dict[str, object]:
        """Flatten one zone into JSON fields the JS needs to draw it.

        Args:
            name: Zone key in ``_map.zones``.

        Returns:
            {"name","x","y","color","max_drones","type","is_start","is_end"}.
            ``color`` passed through raw (a CSS color name or None; JS falls
            back on unknown/absent).
        """
        zone = self._map.zones[name]
        return {
            "name": zone.name,
            "x": zone.x,
            "y": zone.y,
            "color": zone.color,
            "max_drones": zone.max_drones,
            "type": zone.zone_type.value,
            "is_start": zone.is_start,
            "is_end": zone.is_end,
        }

    def _edge_payload(self, name_a: str, name_b: str) -> dict[str, object]:
        """Flatten one connection into JSON fields for drawing a line.

        Args:
            name_a: One endpoint zone name.
            name_b: Other endpoint zone name.

        Returns:
            {"a","b","capacity"}.
        """
        conn = self._map.connections[frozenset({name_a, name_b})]
        return {
            "a": name_a,
            "b": name_b,
            "capacity": conn.max_link_capacity,
        }

    # ------------------------------------------------------------------ #
    # Assembly side                                                      #
    # ------------------------------------------------------------------ #

    def render(self, outfile: str) -> None:
        """Write a single self-contained HTML file animating the run.

        Args:
            outfile: Destination path for the ``.html`` file.

        Raises:
            SolveError: On any file-read/write failure (crash rule: never let
                an OSError escape uncaught).
        """
        data = json.dumps(self._build_timeline())
        html = self._load_template("viz_template.html")
        style = self._load_template("viz.css")
        script = self._load_template("viz.js")
        full_content = (
            html.replace("/* {{STYLE}} */", style)
            .replace("/* {{SCRIPT}} */", script)
            .replace("{{DATA}}", data)
        )
        self._write(outfile, full_content)

    def _load_template(self, path: str) -> str:
        """Read a template file next to this module, crash-safe.

        Args:
            path: Template filename (repo root).

        Returns:
            File contents as text.

        Raises:
            SolveError: If the template cannot be read.
        """
        full_path = os.path.join(os.path.dirname(__file__), path)
        try:
            with open(full_path, encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            raise SolveError(f"cannot read template {path!r}: {exc}")

    def _write(self, path: str, content: str) -> None:
        """Write ``content`` to ``path``, crash-safe.

        Args:
            path: Destination file.
            content: Full file text.

        Raises:
            SolveError: If the write fails.
        """
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except OSError as exc:
            raise SolveError(f"cannot write {path!r}: {exc}")
