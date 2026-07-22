*This project has been created as part of the 42 curriculum by <afretta->*

# Fly-in — Drone Routing Simulator

Move every drone from the **start zone** to the **end zone** in the fewest possible simulation turns, while respecting zone capacities, connection capacities, and per-zone movement costs (normal, priority, restricted, blocked).

---

## Description

Fly-in is a routing and scheduling problem. A map defines zones (nodes) and connections (edges), each carrying capacity limits, plus a number of anonymous, interchangeable drones that all share **one** start and **one** end. The goal is to minimise the **makespan** — the total number of turns until the last drone is delivered.

The key insight that drives every design decision: because the drones are *anonymous* (only the count matters, not which drone is which) and share a single source and sink, this is **not** a multi-agent pathfinding (MAPF) problem. It is a **single-commodity network-flow problem** — the same family as 42's `lem-in`. Sending everyone down one shortest path jams into single file; the win comes from spreading drones across **multiple parallel paths** at once. That is exactly what a flow algorithm computes.

Consequences of this framing (why we did *not* reach for the "obvious" tools):

- **No MAPF / CBS / cooperative-A\*.** Those model *distinct* agents with *distinct* goals and pairwise collision avoidance. Our drones are interchangeable, so agent-vs-agent conflicts are artificial work. Flow never generates them.
- **No geometric A\*.** Map coordinates are cosmetic (visualisation only); movement is defined purely by connections. With no geometry there is no admissible heuristic, so A\* degrades to Dijkstra anyway.

---

## Algorithm choice & implementation strategy

### Chosen algorithm: Min-Cost Max-Flow (successive shortest paths, Dijkstra + Johnson potentials)

We model the map as a capacitated, cost-weighted flow network and solve it with **min-cost max-flow (MCMF)** using **successive shortest augmenting paths**, where each shortest path is found with **Dijkstra guided by Johnson potentials**.

**Graph construction**

- **Zone capacities via node splitting.** Every zone `z` becomes two nodes, `z_in → z_out`, joined by an internal edge with capacity `max_drones` (default 1). All incoming connections land on `z_in`, all outgoing leave from `z_out`. This is what enforces "at most N drones in a zone per turn." Start and end zones are *not* split (unlimited capacity).
- **Connection capacities.** Each connection becomes an edge with capacity `max_link_capacity` (default 1).
- **Movement cost = edge cost.**
  - `normal` → cost 1
  - `priority` → lower cost, so the shortest-path search naturally *prefers* it ("should be preferred by pathfinding")
  - `restricted` → cost 2, modelling the two-turn traversal directly as a real edge weight
  - `blocked` → node removed entirely, so no path can use it
- All input costs are non-negative.

**Why cost-weighted flow with Dijkstra + potentials**

The deciding factor was that we wanted a solver that stays fast on **large maps with large flows**, not only on the tiny evaluation maps:

1. **Augmentation is per-path, not per-drone.** Each successive-shortest-path step pushes the *bottleneck capacity* of an entire path at once, so one augmentation can move many drones. The running time depends on the number of *distinct augmenting paths*, not on the drone count — this is what lets it scale where a unit-at-a-time or time-expanded approach would blow up.
2. **Potentials cache work across augmentations.** Johnson potentials keep the reduced cost `cost(u, v) + h[u] − h[v] ≥ 0`, which (a) makes Dijkstra safe on the residual graph even though back-edges carry negative cost, and (b) carries distance information forward from one augmentation to the next instead of recomputing cold each time. This reuse is the whole game at high flow.
3. **Handles real edge costs directly.** The `priority`/`restricted` weights are expressed as genuine costs, and the same model extends cleanly to arbitrary real-world weights (tolls, fuel, congestion) — not just the 1-vs-2 case in the subject.

Because the input has no negative edges, potentials are initialised with a single Dijkstra pass; **Bellman–Ford is never needed**.

**Overall complexity:** `O(F_paths · E · log V)`, where `F_paths` is the number of augmenting paths (not the number of drones).

**From flow to a turn-by-turn schedule.** MCMF chooses *which* paths carry flow and *how much* each carries (minimising total movement cost). We then decompose the flow into paths and run a greedy **water-filling scheduler** that staggers drone departures across those parallel paths, respecting per-turn zone/connection capacity, to minimise the makespan and avoid deadlocks. The flow solver picks good routes; the scheduler turns routes into the per-turn output log.

### Alternatives considered (and why we passed on them)

| Approach | Model | Why not chosen |
|---|---|---|
| **A — unit-length max-flow (Edmonds–Karp / BFS)** | Split the 2-cost restricted move into two unit hops via a dummy node, so *every* edge has length 1 → plain max-flow, no costs, no negatives. Priority = BFS tie-break. | Simplest and provably optimal at small scale, and we keep it as a **reference/fallback** to cross-check the MCMF output on small maps. But it augments essentially one unit at a time and models cost only indirectly, so it does not carry to large-flow / real-cost scenarios. |
| **Time-expanded max-flow ("flipbook") + binary-search on horizon T** | Copy the graph once per turn; edges point from layer *t* to *t+1*; binary-search the smallest T where max-flow ≥ number of drones. | Gives the **provably optimal makespan** with no separate scheduler, and is genuinely the cleanest answer on small maps. But the graph grows ×T, and both drone count and path length push T up, so it becomes heavy (≈`O(Z·E²·T³)`) on large instances — the exact regime we wanted to stay fast in. |
| **C — MCMF with SPFA (Bellman–Ford queue)** | Same min-cost flow as our choice, but the inner shortest path uses SPFA instead of Dijkstra+potentials. | Same model, less code, but no potential caching and a worse worst case; dropped in favour of the Dijkstra+potentials variant. |

*Reference:* an independent implementation, [robbplo/ft-fly-in](https://github.com/robbplo/ft-fly-in), arrives at the same flow framing via the time-expanded route (node-split zones, transit-node restricted encoding, binary search on T) — useful confirmation of the model, and a concrete illustration of the ×T cost we chose to avoid. By contrast, repos that reached for MAPF/CBS or greedy priority-planning (e.g. `evaristoc/fly-in-school-42`, `krameraad/Fly-in`) run into exactly the model-mismatch and capacity-handling problems the flow framing sidesteps.

---

## Instructions

```sh
make install    # set up the environment / dependencies
make run        # run on a map
make debug      # run with verbose / step tracing
make lint       # flake8 + mypy
make clean      # remove Python artifacts
```

<!-- TODO: fill in exact run invocation, e.g. `make run MAP=maps/challenger.map` -->

---

## Visual representation

<!-- TODO: document the visual output actually implemented (colored terminal and/or GUI):
     what is shown, how to read it, how to toggle it. -->

---

## Resources

- 42 `lem-in` / network-flow background (single-commodity max-flow, min-cost max-flow, successive shortest paths).
- Johnson potentials for running Dijkstra on graphs with negative residual back-edges.
- Surveyed reference implementations: [robbplo/ft-fly-in](https://github.com/robbplo/ft-fly-in), [evaristoc/fly-in-school-42](https://github.com/evaristoc/fly-in-school-42), [krameraad/Fly-in](https://github.com/krameraad/Fly-in).

**How AI was used:** used as a reasoning partner to frame the problem as single-commodity flow (rather than MAPF), to compare candidate algorithms (unit max-flow vs. time-expanded vs. min-cost max-flow), and to weigh their scaling behaviour before committing to min-cost max-flow. All final algorithm choices, code, and implementation are the author's own.
