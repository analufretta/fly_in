"""Min-cost max-flow solver over the zone graph (Phase 3, fleet routing).

Option B from the algorithm decision: successive-shortest-paths MCMF with
Dijkstra + Johnson potentials on a node-split graph. It turns the map into a
capacitated flow network whose max flow = the number of drone "lanes" that can
run in parallel, and whose min cost keeps those lanes short and priority-
preferring. The ``scheduler`` module drives this and turns lanes into a
turn-by-turn dispatch; this module only computes the flow and hands back the
decomposed lanes.

No graph libraries (Norm): the residual network is a hand-built adjacency list
of edge records with paired reverse edges.

Graph model (node-split so per-zone capacity becomes an edge capacity):
    Middle zones split into two string-named flow-nodes: ``"<zone>_in"``
    (links coming IN land here) and ``"<zone>_out"`` (links going OUT
    leave here).
      - internal edge ``"<zone>_in" -> "<zone>_out"``: this edge IS
        "being inside the zone". capacity = ``max_drones``, cost = enter-cost
        of the zone. This is where zone occupancy is capped.
      - each connection ``a-b`` -> two directed edges ``out(a) -> in(b)`` and
        ``out(b) -> in(a)``, capacity = ``max_link_capacity``, cost = 0. Link
        cap enforced here; the entering-cost stays on the internal edge
        (charged once per zone entered).
    Start/end are unlimited, so they are NOT split: one bare node each, with
    no internal edge. SOURCE = start's bare node, SINK = end's bare node.
    Blocked zones: skipped entirely (no nodes/edges).

Cost (integer, so Dijkstra stays exact; folds in the priority tie-break):
    ``enter-cost(v) = 2 * v.turn_cost - (1 if v is priority else 0)`` ->
    normal 2, priority 1, restricted 4, restricted+priority 3. Doubling keeps
    turn-count dominant so a priority zone never lengthens a route just to be
    preferred. All input costs >= 0 and the twins (cap 0) are invisible at
    build time, so potentials start at 0 — no seed Dijkstra, no Bellman-Ford.

Invariant (asserted in tests): reduced cost ``c + h[u] - h[v] >= 0`` on every
residual edge; the final flow is acyclic source->sink.
"""

from __future__ import annotations

import heapq

from drone_map import DroneMap
from zone import ZoneType


class MinCostMaxFlow:
    """Node-split MCMF over a ``DroneMap``, augment-by-augment with potentials.

    Keeps its residual graph and potentials between calls so the scheduler can
    grow the flow value one unit at a time and reuse the work already done.

    Nodes are strings (``"<zone>_in"`` / ``"<zone>_out"``, or a bare zone
    name for start/end); only edges carry integer ids, needed for the
    reverse-twin trick (edge ``i`` and its undo edge ``i ^ 1`` sit at paired
    indices).

    Attributes:
        _map: The validated map being routed.
        _to: Per-edge destination node name (edge ``i``'s reverse is
            ``i ^ 1``).
        _capacity: Per-edge residual capacity.
        _cost: Per-edge unit cost (reverse edges carry the negated cost).
        _links: Adjacency — node name -> list of edge ids leaving that node.
        _potential_dist: Johnson potential per node name (shortest cost from
            source), refreshed each augmentation.
        _zone_node: ``node name -> zone_name`` (so ``decompose`` can turn a
            node back into its zone name).
        _source: The start node (where flow originates).
        _sink: The end node (where flow drains).
        total_flow: Units of flow currently pushed source->sink.
    """

    def __init__(self, drone_map: DroneMap) -> None:
        """Build the residual network and seed potentials.

        Args:
            drone_map: A parsed, validated map with non-``None`` start and end.
        """
        assert drone_map.start is not None and drone_map.end is not None

        self._map: DroneMap = drone_map
        self._source: str = drone_map.start
        self._sink: str = drone_map.end

        self._links: dict[str, list[int]] = {}

        # Residual table
        self._to: list[str] = []
        self._capacity: list[int] = []
        self._cost: list[int] = []

        self._zone_node: dict[str, str] = {}  # node name -> zone name

        self.total_flow: int = 0

        self._build()
        self._potential_dist: dict[str, int] = {
            node: 0 for node in self._links
        }

    def _build(self) -> None:
        """Register split nodes, then internal and link edges.

        Source/sink node names are already set in ``__init__``; this only
        materializes the nodes and edges of the residual network.
        """
        zones = self._map.zones
        for name, zone in zones.items():
            if not zone.is_passable:
                continue
            if zone.is_start or zone.is_end:
                self._add_node(name, name)
            else:
                self._add_node(self._in(name), name)
                self._add_node(self._out(name), name)
                self._add_edge(
                    self._in(name),
                    self._out(name),
                    zone.max_drones,
                    self._enter_cost(name)
                )
        for connection in self._map.connections.values():
            a, b = connection.zone_a, connection.zone_b
            if not (zones[a].is_passable and zones[b].is_passable):
                continue
            cap = connection.max_link_capacity
            self._add_edge(self._link_src(a), self._link_dst(b), cap, 0)
            self._add_edge(self._link_src(b), self._link_dst(a), cap, 0)

    def _link_src(self, name: str) -> str:
        """Node a link leaving zone ``name`` departs from.

        Args:
            name: The zone the link starts at.

        Returns:
            The bare node for start/end (not split), else ``"<name>_out"``.
        """
        zone = self._map.zones[name]
        return name if (zone.is_start or zone.is_end) else self._out(name)

    def _link_dst(self, name: str) -> str:
        """Node a link entering zone ``name`` lands on.

        Args:
            name: The zone the link ends at.

        Returns:
            The bare node for start/end (not split), else ``"<name>_in"``.
        """
        zone = self._map.zones[name]
        return name if (zone.is_start or zone.is_end) else self._in(name)

    @staticmethod
    def _in(zone_name: str) -> str:
        """Name of a zone's in node (links coming in land here).

        Args:
            zone_name: The zone.

        Returns:
            ``"<zone_name>_in"``.
        """
        return f"{zone_name}_in"

    @staticmethod
    def _out(zone_name: str) -> str:
        """Name of a zone's out node (links going out leave here).

        Args:
            zone_name: The zone.

        Returns:
            ``"<zone_name>_out"``.
        """
        return f"{zone_name}_out"

    def _add_node(self, node: str, zone_name: str) -> None:
        """Register a node name so edges can attach to it.

        Args:
            node: The node name (``_in``/``_out`` of some zone).
            zone_name: The zone this node is a half of (for the reverse map).
        """
        self._links[node] = []
        self._zone_node[node] = zone_name

    def _add_edge(self, src: str, dst: str, cap: int, cost: int) -> None:
        """Append a forward edge ``src -> dst`` and its zero-capacity reverse.

        Args:
            src: Source node name.
            dst: Destination node name.
            cap: Forward residual capacity.
            cost: Forward unit cost; the reverse edge carries ``-cost``.
        """
        index = len(self._to)
        self._links[src].append(index)
        self._to.append(dst)
        self._capacity.append(cap)
        self._cost.append(cost)

        # Residual edge
        self._links[dst].append(len(self._to))
        self._to.append(src)
        self._capacity.append(0)
        self._cost.append(-cost)

    def _enter_cost(self, zone_name: str) -> int:
        """Integer cost of entering a zone (priority tie-break folded in).

        Args:
            zone_name: Name of the zone whose internal edge cost is wanted.

        Returns:
            ``2 * turn_cost - (1 if priority else 0)`` -> normal 2, priority 1,
            restricted 4, restricted+priority 3. Only ever called for middle
            zones (start/end have no internal edge).
        """
        zone = self._map.zones[zone_name]
        priority = 1 if zone.zone_type is ZoneType.PRIORITY else 0
        return 2 * zone.turn_cost - priority

    def _dijkstra_augument(self) -> bool:
        """Push one cheapest augmenting path's bottleneck, if one remains.

        Returns:
            ``True`` if flow increased, ``False`` once no source->sink path
            with residual capacity exists (max flow reached).
        """
        pot = self._potential_dist
        shortest_dist: dict[str, int] = {self._source: 0}
        prev_edge: dict[str, int] = {}
        explored: list[tuple[int, str]] = [(0, self._source)]

        while explored:
            dist, node = heapq.heappop(explored)
            if dist > shortest_dist[node]:
                continue
            for edge in self._links[node]:
                if self._capacity[edge] <= 0:
                    continue
                nxt = self._to[edge]
                cost_conv = self._cost[edge] + pot[node] - pot[nxt]
                new_dist = dist + cost_conv
                if nxt not in shortest_dist or new_dist < shortest_dist[nxt]:
                    shortest_dist[nxt] = new_dist
                    prev_edge[nxt] = edge
                    heapq.heappush(explored, (new_dist, nxt))

        if self._sink not in shortest_dist:
            return False

        for reached, reached_dist in shortest_dist.items():
            pot[reached] += reached_dist

        path_edges: list[int] = []
        node = self._sink
        while node != self._source:
            edge = prev_edge[node]
            path_edges.append(edge)
            node = self._to[edge ^ 1]

        max_flow = min(self._capacity[edge] for edge in path_edges)
        for edge in path_edges:
            self._capacity[edge] -= max_flow
            self._capacity[edge ^ 1] += max_flow

        self.total_flow += max_flow
        return True

    def run_to(self, target_flow: int) -> int:
        """Grow the flow up to a target value, reusing existing residual state.

        Args:
            target_flow: Desired number of flow units (lanes).

        Returns:
            The flow value actually achieved (``< target_flow`` if the map
            maxes out first).
        """
        while self.total_flow < target_flow and self._dijkstra_augument():
            continue
        return self.total_flow

    def decompose(self) -> list[list[str]]:
        """Peel the current flow into concrete source->sink node routes.

        Returns:
            One lane per unit of flow. Each lane is a zone-name sequence
            ``[start, ..., end]`` — the shape a ``Drone`` plays back unchanged.
        """
        paths: list[list[str]] = []
        edge_flow_registry: dict[int, int] = {
            edge_id: self._capacity[edge_id ^ 1]
            for edge_id in range(0, len(self._to), 2)
        }

        for _ in range(self.total_flow):
            nodes: list[str] = []
            node = self._source
            while node != self._sink:
                nodes.append(node)
                for edge in self._links[node]:
                    if edge_flow_registry.get(edge, 0) > 0:
                        edge_flow_registry[edge] -= 1
                        node = self._to[edge]
                        break
            nodes.append(self._sink)

            path: list[str] = []
            for node in nodes:
                zone_name = self._zone_node[node]
                # collapse the in/out pair of one zone into a single entry
                if not path or path[-1] != zone_name:
                    path.append(zone_name)
            paths.append(path)
        return paths
