*This project has been created as part of the 42 curriculum by afretta-.*

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

### The two approaches — and why B is the build

Both candidates model the problem as single-commodity flow; they differ in whether edge cost is expressed **structurally** (A) or **as a real weight** (B).

| | **A — unit-length max-flow (Edmonds–Karp / BFS)** | **B — min-cost max-flow (Dijkstra + Johnson potentials)** ✅ chosen |
|---|---|---|
| **Model** | Split the 2-cost restricted move into two unit hops via a dummy node, so *every* edge has length 1 → plain max-flow, no costs, no negatives. Priority = BFS tie-break. | Real cost-weighted network: `normal`=1, `priority`=lower, `restricted`=2, `blocked`=removed. Node-split zones enforce capacity. |
| **Augmentation** | Essentially one unit at a time; cost modelled only indirectly through dummy structure. | Per **path** — each step pushes the whole bottleneck at once; runtime scales with number of augmenting paths, not drone count. |
| **Reuse** | Recomputes BFS cold each augmentation. | Johnson potentials carry distance info forward across augmentations (reduced cost `c(u,v)+h[u]−h[v] ≥ 0` keeps Dijkstra safe on the residual). |
| **Costs** | 1-vs-2 only, and awkwardly (dummy nodes); arbitrary weights blow up the structure. | Handles real edge costs directly; extends cleanly to arbitrary weights (tolls, fuel, congestion). |
| **Status** | **Design contrast only** — *not* implemented, *not* a runtime fallback. | **Implemented.** |

**Why B is the build:** A is simpler and provably optimal on the tiny evaluation maps, but the goal was a solver that stays fast on **large maps with large flows and real edge costs**, not just the eval set. B wins on exactly the axes that matter at scale: per-path augmentation instead of per-drone, potential caching across augmentations, and native handling of the `priority`/`restricted` weights. Because the input has no negative edges, potentials are seeded with a single Dijkstra pass and **Bellman–Ford is never needed**. A stays in this README purely to show the structural-encoding alternative we deliberately did not take.

---

## Architecture & data flow

The program is a **pipeline that narrows trust**: raw bytes → lines → isolated typed objects → a validated graph → a solution. Each stage hands the next a *more-trusted* value, so by the time the solver runs it never re-validates input — this is the "**parse, don't validate**" principle spread across files.

**Runtime call chain** (root → leaf):

```
main.py            thin entry: safe file I/O, then parse → solve → print
  └─ parser.py     orchestrator: owns line numbers; wraps ValueError into
                   MapError(line, cause); assembles the DroneMap
       └─ tokenizer.py   one raw line → one typed record (classify + parse_*)
            └─ zone.py / connection.py   data objects; self-validate in
                                         __post_init__
  └─ drone_map.py  whole-map container: adjacency + graph validation
       └─ (solver / MCMF)   routes + turn-by-turn schedule → output log
```

**Layer responsibilities:**

| File | Role |
|---|---|
| `main.py` | Thin entry point. Opens the map file with a context manager (no crash), kicks off parse + solve, prints the per-turn log. |
| `parser.py` | Orchestrator. Walks lines, tracks the line number, and is the **only** place that turns a raw `ValueError` into a `MapError(line, cause)`. Assembles and returns a `DroneMap`. |
| `tokenizer.py` | Pure line-level translator: one string → one typed record. Knows nothing about line numbers or other lines. |
| `zone.py` / `connection.py` | Self-validating data objects. Each checks only its own fields, at construction. |
| `drone_map.py` | Whole-map container. Only layer that sees every object at once → owns graph rules (endpoint existence, duplicate edges via `Connection.key`, exactly one start / one end, connectivity) plus adjacency. |
| `errors.py` | `MapError(line, cause)` — the single error type surfaced to the user. |

**Three validation scopes.** Every rule lives in exactly one scope, chosen by *how much you must know to check it*:

1. **Line syntax** — tokenizer / regex. "Can I split this one line into fields?"
2. **One object** — `__post_init__`. "Are this object's own fields sane, regardless of who built it?" (non-empty, no self-loop, capacity ≥ 1, valid name shape).
3. **Whole graph** — `DroneMap.validate`. "Do all objects together form a valid map?" (endpoints exist, no duplicate edges, one start/one end, connectivity).

A name-shape rule (no dash/whitespace) has a single owner, `Zone.is_valid_name`, reused by `Connection` so the definition never drifts.

---

## Instructions

```sh
make install                                  # create .venv + install flake8/mypy/pytest
make run MAP=maps/easy/01_linear_path.txt     # parse+validate a map (MAP defaults to this)
make debug MAP=<path>                          # same, with verbose dump
make lint                                      # flake8 + mypy (subject flags)
make lint-strict                               # mypy --strict
make test                                      # run the parser unit tests
make clean                                     # remove caches / bytecode (fclean also drops .venv)
```

Runtime has **zero** third-party dependencies (graph and parser are hand-rolled); `make install` only fetches the lint/test tooling.

### Error reporting

Any malformed map **stops the program** with a single clear message on `stderr` and a non-zero exit code (`1`) — never a raw traceback. Line-specific problems name the offending 1-based line and the cause; whole-map problems (e.g. a missing `nb_drones`, or no start/end zone) omit the line:

```text
[ERROR] line 7: invalid zone name: 'a b'
[ERROR] map has no start zone
```

This satisfies the subject's rule that a parsing error must halt and report the line and cause.

---

## Visual representation

<!-- TODO: document the visual output actually implemented (colored terminal and/or GUI):
     what is shown, how to read it, how to toggle it. -->

---

## Resources

- 42 `lem-in` / network-flow background (single-commodity max-flow, min-cost max-flow, successive shortest paths).
- Johnson potentials for running Dijkstra on graphs with negative residual back-edges.

**How AI was used:** used as a reasoning partner to frame the problem as single-commodity flow (rather than MAPF), to compare the two candidate algorithms (unit max-flow vs. min-cost max-flow), and to weigh their scaling behaviour before committing to min-cost max-flow. All final algorithm choices, code, and implementation are the author's own.
