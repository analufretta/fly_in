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
- **Movement cost = internal-edge cost.** Cost lives *only* on a zone's internal `z_in → z_out` edge (connections cost 0), charged once per zone entered. The enter-cost is `2 · turn_cost − (1 if priority else 0)`:
  - `normal` → **2**
  - `priority` → **1** — the `−1` discount makes it "half a turn" cheaper, so priority zones are *preferred* without ever inflating the turn count ("should be preferred by pathfinding")
  - `restricted` → **4** — its two-turn traversal, doubled
  - `restricted + priority` → **3**
  - `blocked` → node removed entirely, so no path can use it
- The `2 ·` doubling is what keeps the integer turn-count strictly dominant over the priority tie-break. All input costs are non-negative.

**Why cost-weighted flow with Dijkstra + potentials**

The deciding factor was that we wanted a solver that stays fast on **large maps with large flows**, not only on the tiny evaluation maps:

1. **Augmentation is per-path, not per-drone.** Each successive-shortest-path step pushes the *bottleneck capacity* of an entire path at once, so one augmentation can move many drones. The running time depends on the number of *distinct augmenting paths*, not on the drone count — this is what lets it scale where a unit-at-a-time or time-expanded approach would blow up.
2. **Potentials cache work across augmentations.** Johnson potentials keep the reduced cost `cost(u, v) + h[u] − h[v] ≥ 0`, which (a) makes Dijkstra safe on the residual graph even though back-edges carry negative cost, and (b) carries distance information forward from one augmentation to the next instead of recomputing cold each time. This reuse is the whole game at high flow.
3. **Handles real edge costs directly.** The `priority`/`restricted` weights are expressed as genuine costs, and the same model extends cleanly to arbitrary real-world weights (tolls, fuel, congestion) — not just the 1-vs-2 case in the subject.

Because the *initial* graph has no negative edges — the reverse residual (twin) edges start at capacity 0, so they are invisible to the search — potentials **start at 0**. There is **no seed Dijkstra pass and no Bellman–Ford**; the potentials only accumulate as augmentations proceed.

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

**Why B is the build:** A is simpler and provably optimal on the tiny evaluation maps, but the goal was a solver that stays fast on **large maps with large flows and real edge costs**, not just the eval set. B wins on exactly the axes that matter at scale: per-path augmentation instead of per-drone, potential caching across augmentations, and native handling of the `priority`/`restricted` weights. Because the initial graph has no negative edges (twin edges start at capacity 0), potentials **start at 0** — neither a seed Dijkstra nor Bellman–Ford is ever needed. A stays in this README purely to show the structural-encoding alternative we deliberately did not take.

### Phase 2 building block — single-drone shortest path (`pathfinder.py`, implemented)

Before the multi-drone flow solver, `PathFinder` computes the fewest-turn route for **one** drone with a hand-rolled **Dijkstra** (no graph libraries). It is **standalone** — it answers "what is the optimal path for a single drone, and is the end reachable at all?". It is *not* reused by the flow solver: MCMF runs its **own** Dijkstra over the residual graph (scalar reduced cost, repeated augmentation), a different search over a different graph. The two share the Dijkstra idea, not the code.

**Cost model.** A path's cost is the sum of the `turn_cost` of each zone *entered* — the start zone is free (the drone begins there). `normal`/`priority` cost 1 turn, `restricted` costs 2 (its two-turn traversal expressed directly as weight). This sum is the single drone's makespan.

**Lexicographic key `(turns, penalty)`.** Priority zones must be *preferred* without ever inflating the turn count, so cost is a pair, not a scalar:

- `turns` — the real makespan. **Primary** key.
- `penalty` — `0` for a priority zone, `1` otherwise. So `penalty` accumulates the count of *non-priority* zones entered.

Python compares tuples lexicographically: `turns` decides first, and `penalty` is consulted **only** when `turns` ties. A slower-but-priority route can therefore never beat a faster one (`(2, 5) < (3, 0)` because `2 < 3`); among equal-turn routes, the one crossing more priority zones wins (`(3, 1) < (3, 3)`). Priority is a tie-break, never an override — matching the subject's "should be preferred" against a turns-based score.

**Blocked zones.** Skipped during relaxation via `zone.is_passable`, so no route can ever enter one.

**Min-heap frontier with lazy deletion.** The frontier is a `heapq` min-heap of `(turns, penalty, name)`; `heappop` always returns the cheapest pending zone. We never *remove* superseded entries — when a cheaper route to a zone is found we simply push a new entry, leaving the stale one buried. Each pop is guarded:

```python
if (turns, penalty) > best[name]:
    continue   # stale: this zone was already settled via a cheaper route
```

`best[name]` holds the true cheapest cost known; a popped entry worse than that is an outdated duplicate and is discarded. This is cheaper than searching the heap to delete stale entries.

**Back-pointer reconstruction.** A `prev[name]` map records the predecessor on the best route to each zone, updated **in lock-step with `best`** (both are written in the same relaxation branch, so they never disagree). Once the end zone pops non-stale, Dijkstra's settle guarantee makes its whole `prev` chain final. `_reconstruct` walks `prev` backward from `end` to `start` and reverses the result. The walk is guaranteed to terminate: entering any zone costs ≥ 1 turn, so `turns` strictly *decreases* along the backward chain — it cannot cycle and must bottom out at `start` (the only zone with no `prev`, cost `0`). If the end never received a cost, it is unreachable and `shortest_path` returns `None` (surfaced as a `SolveError`).

**Worked example (why stale entries and the guard matter).** Take the graph `S→X=1`, `S→Y=2`, `X→C=5`, `Y→C=1`, `C→Z=10`, with `start=S`, `end=Z` (single scalar costs, to isolate the mechanic):

| Loop | pop | action | `best[C]` / `prev[C]` | heap after |
|---|---|---|---|---|
| 1 | `(0,S)` | relax X→1, Y→2 | — | `(1,X) (2,Y)` |
| 2 | `(1,X)` | relax C via X = **6** | `6` / `X` | `(2,Y) (6,C)` |
| 3 | `(2,Y)` | relax C via Y = **3** < 6 → overwrite | `3` / **`Y`** | `(3,C) (6,C)` ← C twice |
| 4 | `(3,C)` | relax Z = 13 | — | `(6,C) (13,Z)` |
| 5 | `(6,C)` | `6 > best[C]=3` → **stale, skip** | — | `(13,Z)` |
| 6 | `(13,Z)` | `Z == end` → **break** | — | — |

`C` is pushed **twice**; `prev[C]` flips `X → Y` when the cheaper route appears; the leftover `(6,C)` is discarded by the guard in loop 5. Reconstruction walks `Z → C → Y → S` and reverses it → **`[S, Y, C, Z]`**. Note the final route goes through `Y` even though `X` was cheaper to reach first — because `Y`'s route to the goal is cheaper overall, which is exactly the trap a greedy "take the nearest neighbour" would fall into and Dijkstra does not.

### Phase 2 execution — turning a route into a per-turn log (`drone.py`, `simulation.py`)

`PathFinder` answers *where* a drone goes; `Drone` and `Simulation` answer *when*. A route is a static list of zone names, but the output is a **timeline** — one line per simulation turn — so the route has to be replayed step by step.

**`Drone` — a playback cursor.** Each drone holds its route plus a small amount of turn state (`_pos`, `_in_flight`, `_flight_dest`, `_delivered`). Its `step()` advances the drone by exactly one turn and returns that turn's move token, or `None` if it has nothing to do. Keeping the cursor on the drone (not the loop) is deliberate: Phase 3 drives a whole fleet with the same `step()` contract.

**The restricted zone's two-turn transit** is the one subtle case, and it is why a drone needs an in-flight state rather than a single position:

- **Turn 1 — departure.** Entering a restricted zone costs 2 turns, so the drone spends the first turn *on the connection*. It sets `_in_flight = True`, records the index it is heading for in `_flight_dest`, and emits the connection token `D<id>-<src>-<dst>`. It is **not** counted as inside the zone this turn.
- **Turn 2 — arrival.** `step()` sees `_in_flight`, lands the drone on `_flight_dest`, clears the flag, and emits `D<id>-<dst>`.

`_flight_dest` exists precisely because `step()` has no memory between calls except what lives on the drone: turn 2 must recover the destination that turn 1 decided.

**`Simulation` — the clock.** `run()` loops until every drone is delivered. Each turn it asks every undelivered drone to `step()`, keeps the non-`None` tokens, and joins them with spaces into one output line. If a turn produces *zero* moves while drones remain undelivered, the schedule is stuck and it raises `SolveError` — impossible for a single drone on a valid route, but a guard that Phase 3's fleet scheduling will rely on. The loop is written fleet-shaped now so Phase 3 reuses it unchanged.

**Unreachable end.** If `PathFinder` returns `None`, there is no route at all; `main` raises `SolveError("no path from start to end")`, which prints `[ERROR] no path from start to end` to `stderr` and exits `1` — the same halt-and-report contract as a malformed map.

### Output format

One line per simulation turn, printed to `stdout`. Each line is the space-separated set of moves made **that** turn; a drone that does not move is omitted from the line entirely. A move is one of:

- `D<ID>-<zone>` — drone `<ID>` arrived in `<zone>` this turn.
- `D<ID>-<src>-<dst>` — drone `<ID>` is in flight along the connection toward the restricted zone `<dst>` (the two-turn transit, turn 1 of 2).

For example, a single drone crossing a route whose second-to-last hop is a restricted zone `R` (`[S, R, E]`) prints:

```text
D1-S-R
D1-R
D1-E
```

Diagnostics (`--debug`: the parsed-map summary and adjacency) go to `stderr`, keeping `stdout` a clean, gradable move log.

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
  └─ pathfinder.py single-drone Dijkstra → route [start … end], or None
  └─ mcmf.py       fleet flow: node-split residual net → min-cost max-flow;
                   decompose → parallel lanes; lane_turn_length → lane cost
  └─ simulation.py turn loop: steps each drone, joins per-turn tokens
       └─ drone.py       one drone's cursor: route → per-turn move token
  └─ (Phase 3: scheduler)  water-filling over lanes → per-turn output log
```

**Layer responsibilities:**

| File | Role |
|---|---|
| `main.py` | Thin entry point. Opens the map file with a context manager (no crash), kicks off parse + solve, prints the per-turn log. |
| `parser.py` | Orchestrator. Walks lines, tracks the line number, and is the **only** place that turns a raw `ValueError` into a `MapError(line, cause)`. Assembles and returns a `DroneMap`. |
| `tokenizer.py` | Pure line-level translator: one string → one typed record. Knows nothing about line numbers or other lines. |
| `zone.py` / `connection.py` | Self-validating data objects. Each checks only its own fields, at construction. |
| `drone_map.py` | Whole-map container. Only layer that sees every object at once → owns graph rules (endpoint existence, duplicate edges via `Connection.key`, exactly one start / one end, connectivity) plus adjacency. |
| `pathfinder.py` | Single-drone solver. Hand-rolled Dijkstra over the zone graph → the fewest-turn route, or `None` when the end is unreachable. **Standalone** (single-drone / reachability); *not* reused by MCMF, which runs its own residual Dijkstra. |
| `mcmf.py` | Fleet flow solver (Phase 3). Builds the node-split residual network (bare start/end, `z_in→z_out` internal edges, paired twin edges), pushes min-cost max-flow via `dijkstra_augument` (reduced-cost Dijkstra + Johnson potentials), then `decompose` peels the flow into concrete lanes and `lane_turn_length` scores each. |
| `simulation.py` | Turn-by-turn engine. Each turn steps every undelivered drone and joins their move tokens into one output line; raises `SolveError` on a stalled schedule. |
| `drone.py` | One drone's playback cursor. Walks its assigned route, emitting the per-turn move token and handling the restricted zone's two-turn in-flight transit. |
| `errors.py` | `MapError(line, cause)` for a bad map and `SolveError(cause)` for an unsolvable run — the two error types surfaced to the user. |

**Three validation scopes.** Every rule lives in exactly one scope, chosen by *how much you must know to check it*:

1. **Line syntax** — tokenizer / regex. "Can I split this one line into fields?"
2. **One object** — `__post_init__`. "Are this object's own fields sane, regardless of who built it?" (non-empty, no self-loop, capacity ≥ 1, valid name shape).
3. **Whole graph** — `DroneMap.validate`. "Do all objects together form a valid map?" (endpoints exist, no duplicate edges, one start/one end, connectivity).

A name-shape rule (no dash/whitespace) has a single owner, `Zone.is_valid_name`, reused by `Connection` so the definition never drifts.

---

## Instructions

```sh
make install                                  # create .venv + install flake8/mypy/pytest
make run MAP=maps/easy/01_linear_path.txt     # solve one drone + print the per-turn log (MAP defaults to this)
make debug MAP=<path>                          # same, plus map summary + adjacency on stderr
make lint                                      # flake8 + mypy (subject flags)
make lint-strict                               # mypy --strict
make test                                      # run the unit test suite (none yet — added in Phase 6)
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
