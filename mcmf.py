"""Min-cost max-flow solver over the zone graph (Phase 3, fleet routing).

SCAFFOLD ONLY — signatures + pseudocode. Bodies not implemented yet.

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
    Every zone splits into two string-named flow-nodes: ``"<zone>:arrival"``
    (links coming IN land here) and ``"<zone>:departure"`` (links going OUT
    leave here).
      - internal edge ``"<zone>:arrival" -> "<zone>:departure"``: this edge IS
        "being inside the zone". capacity = ``zone.capacity`` (``max_drones``;
        unlimited for start/end), cost = enter-cost of the zone. This is where
        zone occupancy is capped.
      - each connection ``a-b`` -> two directed edges ``"a:departure" ->
        "b:arrival"`` and ``"b:departure" -> "a:arrival"``, capacity =
        ``max_link_capacity``, cost = 0. Link cap enforced here; the entering-
        cost stays on the internal edge (charged once per zone entered).
    SOURCE = ``"<start>:departure"``  (start's internal edge is unlimited).
    SINK   = ``"<end>:arrival"``      (end is unlimited).
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

    Nodes are strings (``"<zone>:arrival"`` / ``"<zone>:departure"``); only
    edges carry integer ids, needed for the reverse-twin trick (edge ``i`` and
    its undo edge ``i ^ 1`` sit at paired indices).

    Attributes:
        _map: The validated map being routed.
        _to: Per-edge destination node name (edge ``i``'s reverse is ``i ^ 1``).
        _capacity: Per-edge residual capacity (unlimited sentinel for start/end).
        _cost: Per-edge unit cost (reverse edges carry the negated cost).
        _head: Adjacency — node name -> list of edge ids leaving that node.
        _potentials: Johnson potential per node name, refreshed each augmentation.
        _zone_hub: ``node name -> zone_name`` (reverse, so ``decompose`` can
            turn a node back into its zone name).
        _source: The start zone's departure node (where flow originates).
        _sink: The end zone's arrival node (where flow drains).
        total_flow: Units of flow currently pushed source->sink.
        total_cost: Accumulated real (non-reduced) cost of that flow.
    """

    def __init__(self, drone_map: DroneMap) -> None:
        """Build the residual network and seed potentials.

        Args:
            drone_map: A parsed, validated map with non-``None`` start and end.
        """
        self._map: DroneMap = drone_map
        self._source, self._sink = drone_map.start, drone_map.end
        assert self._source is not None and self._sink is not None
      
        self._links: dict[str, list[int]] = {}

        #Residual table 
        self._to: list[str] = []
        self._capacity: list[int] = []
        self._cost: list[int] = []
        
        self._zone_node: dict[str, str] = {}  # node name -> zone name

        self.total_flow: int = 0
        self.total_cost: int = 0

        self._build()
        self._potential_cost: dict[str, int] = {node: 0 for node in self._links}

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
            if not (self._map.zones[a].is_passable and self._map.zones[b].is_passable):
                continue

            def out_check(n: str) -> str:
                return n if (zones[n].is_start or zones[n].is_end) else self._out(n)

            def in_check(n: str) -> str:
                return n if (zones[n].is_start or zones[n].is_end) else self._in(n)
                
            cap = connection.max_link_capacity
            self._add_edge(out_check(a), in_check(b), cap, 0)
            self._add_edge(out_check(b), in_check(a), cap, 0)

    @staticmethod
    def _in(zone_name: str) -> str:
        """Name of a zone's in node (links coming in land here).

        Args:
            zone_name: The zone.

        Returns:
            ``"<zone_name>->in"``.
        """
        return f"{zone_name}->in"

    @staticmethod
    def _out(zone_name: str) -> str:
        """Name of a zone's out node (links going out leave here).

        Args:
            zone_name: The zone.

        Returns:
            ``"<zone_name>->out"``.
        """
        return f"{zone_name}->out"

    def _add_node(self, node: str, zone_name: str) -> None:
        """Register a node name so edges can attach to it.

        Args:
            node: The node name (``_arrival``/``_departure`` of some zone).
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
        """Integer cost of entering a zone (with the priority tie-break folded in).

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

    def dijkstra_augument(self) -> bool:
        """Push one cheapest augmenting path's bottleneck, if one remains.

        Returns:
            ``True`` if flow increased, ``False`` once no source->sink path with
            residual capacity exists (max flow reached).
        """
        pot = self._potential_cost
        shortest_dist: dict[str, int] = {self._source: 0}
        prev_edge: dict[str, int] = {}
        explored: list[tuple[int, str]] = [(0, self._source)]
        
        while explored:
            dist, zone = heapq.heappop(explored)
            if dist > shortest_dist[zone]:
                continue
            for edge in self._links[zone]:
                if self._capacity[edge] <= 0:
                    continue
                nxt = self._to[edge]
                cost_conv = self._cost[edge] + pot[zone] - pot[nxt]
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
        zone = self._sink
        while zone != self._source:
            edge = prev_edge[zone]
            path_edges.append(edge)
            zone = self._to[edge ^ 1] # why zone is = to the _to of residual one?

        max_flow = min(self._capacity[edge] for edge in path_edges)
        path_cost = 0
        for edge in path_edges:
            self._capacity[edge] -= max_flow
            self._capacity[edge ^ 1] += max_flow
            path_cost += self._cost[edge]
        
        self.total_flow = +max_flow
        self.total_cost = max_flow * path_cost # why not only += path_cost? I'm confused here
        return True



    def run_to(self, target_flow: int) -> int:
        """Grow the flow up to a target value, reusing existing residual state.

        Args:
            target_flow: Desired number of flow units (lanes).

        Returns:
            The flow value actually achieved (``< target_flow`` if the map maxes
            out first).
        """
        while self.total_flow < target_flow and self.dijkstra_augument():
                continue
        return self.total_flow


    def decompose(self) -> list[list[str]]:
        """Peel the current flow into concrete source->sink zone routes.

        Returns:
            One lane per unit of flow. Each lane is a zone-name sequence
            ``[start, ..., end]`` — the SAME shape ``PathFinder.shortest_path``
            returns, so a ``Drone`` can play it back unchanged.
        """
        paths: list[list[str]] = []
        path: list[str] = []
        # Copy each edge's used flow into a scratch `remaining` array.
        # While flow still leaves _source:
        #     walk _source -> ... -> _sink, at each node taking any out-edge with
        #         remaining > 0 and decrementing it by 1 along the walk;
        #     translate node names to zones via _zone_hub, dropping consecutive
        #         duplicates (arrival+departure of one zone collapse), to get
        #         [start, ..., end];
        #     append that sequence to the lane list.
        # Return the lanes. (Flow is acyclic, so every walk reaches _sink.)
        return paths

    def lane_turn_length(self, lane: list[str]) -> int:
        """Turns one drone alone needs to fly a lane (restricted zones count 2).

        Args:
            lane: A zone-name sequence ``[start, ..., end]`` from ``decompose``.

        Returns:
            Sum of ``turn_cost`` of every zone ENTERED (start is free). Used by
            the scheduler's water-filling to rank lanes.
        """
        # Sum turn_cost over lane[1:] (each entered zone); return the total.
