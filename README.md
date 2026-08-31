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

### From flow to schedule — the water-filling dispatcher (`scheduler.py`)

MCMF chooses *which* paths carry flow; the `Scheduler` decides *when* each drone leaves so the last one lands as early as possible. `solve()` drives the whole Phase-3 pipeline:

1. Build a `MinCostMaxFlow` over the map and `run_to(nb_drones)` — grow the flow to `min(maxflow, nb_drones)` units (never more lanes than drones).
2. If the achieved flow is `0`, the end is unreachable → raise `SolveError`. **This is the only reachability check the program needs**; a zero-flow map has no start→end route at all.
3. `decompose()` the flow into that many **lanes** (one zone-name route per flow unit; a "fat" route that carries `k` units appears `k` times).
4. `_assign()` water-fills the drones across the lanes.
5. Materialize one `Drone(id, lane, release_turn)` per drone and hand the list to `Simulation`.

**Why one drone per lane per turn is always safe.** A feasible flow guarantees that if each lane carries **one drone per turn**, no zone or connection cap is ever exceeded — the caps are baked into the edge capacities MCMF respected. So the scheduler never tracks capacity at run time; it only has to keep each lane at ≤ 1 departure per turn. Staggering successive drones on a lane by exactly one turn does that, so the whole dispatch is feasible **by construction** — no reservation table, no conflict resolution, no deadlock.

**Water-filling (`_assign`).** Drones on one lane leave one turn apart, so a lane of turn-length `L` already carrying `count` drones would land the *next* drone at turn `count + L`. Each drone is placed on the lane minimizing that value, and its `release_turn` is that lane's `count` before placement; then `count` for that lane increments. Greedily minimizing each drone's landing turn minimizes the last landing (the makespan). A lane's length `L` is `_lane_length` — the sum of `turn_cost` over every zone *entered* (`restricted` counts 2), the start being free.

**Why no sweep over lane counts.** Adding a lane only ever gives each drone more options, so it can never *worsen* the makespan (an unhelpful long lane is simply never fed). The scheduler therefore grows straight to `min(maxflow, nb_drones)` lanes and water-fills once — no need to try every candidate flow value.

### Execution — turning lanes into a per-turn log (`drone.py`, `simulation.py`)

The scheduler answers *where and when* each drone goes; `Drone` and `Simulation` replay that into the output **timeline** — one line per simulation turn.

**`Drone` — a playback cursor.** Each drone holds its route plus a small amount of turn state (`_pos`, `_in_flight`, `_in_flight_dest`, `_delivered`, and a `_wait` countdown seeded from `release_turn`). Its `fly()` advances the drone by exactly one turn and returns that turn's move token, or `None` if it has nothing to do (delivered, or still waiting for its release turn). Keeping the cursor on the drone (not the loop) is what lets one `Simulation` drive a whole fleet with the same `fly()` contract.

**`release_turn` — the stagger.** A drone with `release_turn = r` sits at the start emitting nothing for its first `r` turns (`_wait` counts down), then flies. This is the one mechanism that spaces a lane's drones one turn apart; `release_turn = 0` (the default) is an ordinary drone that leaves immediately.

**The restricted zone's two-turn transit** is the one subtle case, and it is why a drone needs an in-flight state rather than a single position:

- **Turn 1 — departure.** Entering a restricted zone costs 2 turns, so the drone spends the first turn *on the connection*. It sets `_in_flight = True`, records the index it is heading for in `_in_flight_dest`, and emits the connection token `D<id>-<src>-<dst>`. It is **not** counted as inside the zone this turn (which is exactly why the flow model treats it as latency, not extra occupancy).
- **Turn 2 — arrival.** `fly()` sees `_in_flight`, lands the drone on `_in_flight_dest`, clears the flag, and emits `D<id>-<dst>`.

`_in_flight_dest` exists precisely because `fly()` has no memory between calls except what lives on the drone: turn 2 must recover the destination that turn 1 decided.

**`Simulation` — the clock.** `run()` loops until every drone is delivered. Each turn it asks every undelivered drone to `fly()`, keeps the non-`None` tokens, and joins them with spaces into one output line. If a turn produces *zero* moves while drones remain undelivered, the schedule is stuck and it raises `SolveError` — a safety guard that water-filling's staggered releases make unreachable in practice (every lane's first drone flies continuously from turn 0, so some drone always moves until the makespan).

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
main.py            thin entry: safe file I/O, then parse → schedule → run
  └─ parser.py     orchestrator: owns line numbers; wraps ValueError into
                   MapError(line, cause); assembles the DroneMap
       └─ tokenizer.py   one raw line → one typed record (classify + parse_*)
            └─ zone.py / connection.py   data objects; self-validate in
                                         __post_init__
  └─ drone_map.py  whole-map container: adjacency + graph validation
  └─ scheduler.py  fleet dispatch: drives MCMF, water-fills drones over lanes
       └─ mcmf.py       node-split residual net → min-cost max-flow;
                        decompose → parallel lanes
  └─ simulation.py turn loop: flies each drone, joins per-turn tokens
       └─ drone.py       one drone's cursor: route + release → move token
```

**Layer responsibilities:**

| File | Role |
|---|---|
| `main.py` | Thin entry point. Opens the map file with a context manager (no crash), kicks off parse + schedule + run, prints the per-turn log. |
| `parser.py` | Orchestrator. Walks lines, tracks the line number, and is the **only** place that turns a raw `ValueError` into a `MapError(line, cause)`. Assembles and returns a `DroneMap`. |
| `tokenizer.py` | Pure line-level translator: one string → one typed record. Knows nothing about line numbers or other lines. |
| `zone.py` / `connection.py` | Self-validating data objects. Each checks only its own fields, at construction. |
| `drone_map.py` | Whole-map container. Only layer that sees every object at once → owns graph rules (endpoint existence, duplicate edges via `Connection.key`, exactly one start / one end, connectivity) plus adjacency. |
| `mcmf.py` | Fleet flow solver. Builds the node-split residual network (bare start/end, `z_in→z_out` internal edges, paired twin edges), pushes min-cost max-flow via `_dijkstra_augument` (reduced-cost Dijkstra + Johnson potentials) — `run_to(target)` grows to a flow value, `decompose` peels the flow into concrete lanes. |
| `scheduler.py` | Fleet dispatcher. Drives `mcmf` (`run_to` → `decompose`), water-fills the drones across the lanes (`_assign`), and returns one `Drone` per drone carrying its lane and `release_turn`. Raises `SolveError` when the max flow is `0` (end unreachable). |
| `simulation.py` | Turn-by-turn engine. Each turn flies every undelivered drone and joins their move tokens into one output line; raises `SolveError` on a stalled schedule. |
| `drone.py` | One drone's playback cursor. Waits out its `release_turn`, then walks its assigned route, emitting the per-turn move token and handling the restricted zone's two-turn in-flight transit. |
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
make run MAP=maps/easy/01_linear_path.txt     # schedule the fleet + print the per-turn log (MAP defaults to this)
make debug MAP=<path>                          # same, plus map summary + adjacency on stderr
make lint                                      # flake8 + mypy (subject flags)
make lint-strict                               # mypy --strict
make test                                      # run the unit test suite (none yet — added in Phase 6)
make clean                                     # remove caches / bytecode (fclean also drops .venv)
```

Runtime has **zero** third-party dependencies (graph and parser are hand-rolled); `make install` only fetches the lint/test tooling.

Every successful `make run` also writes `<mapname>.html` (e.g. `01_linear_path.html`) — the animated visualiser (see [Visual representation](#visual-representation)). Open it in any browser; the move log still goes to `stdout` untouched.

### Error reporting

Any malformed map **stops the program** with a single clear message on `stderr` and a non-zero exit code (`1`) — never a raw traceback. Line-specific problems name the offending 1-based line and the cause; whole-map problems (e.g. a missing `nb_drones`, or no start/end zone) omit the line:

```text
[ERROR] line 7: invalid zone name: 'a b'
[ERROR] map has no start zone
```

This satisfies the subject's rule that a parsing error must halt and report the line and cause.

---

## Visual representation

The mandatory visual feedback is a **graphical interface** (subject option 2): a
single, self-contained **HTML file** that animates the run in any browser. It is
built with **SVG + vanilla JavaScript**; the Python side (`visualizer.py`) only
produces data and string-assembles the file, so there is **no third-party
graphics dependency** (no `matplotlib`), honouring the no-graph-libs rule.

**How to see it.** Every successful run automatically writes `<mapname>.html`
next to where you run it — e.g. `make run MAP=maps/easy/02_simple_fork.txt`
produces `02_simple_fork.html`. Open that file in any browser: no server, no
network, no dependencies (CSS and JS are inlined into the one file).

**What it shows.**

- The network laid out by each zone's `x`/`y` coordinate (y-flipped so map "up"
  is screen "up"), padded to fit the stage.
- **Zones** as circles filled with the map's `color=` field (start and end
  ringed in white); each labelled with its name and its live occupancy.
- **Connections** as lines, labelled with their capacity.
- **Drones** as dots — one per drone.

**Playback controls.**

- **▶ Play / ⏸ Pause** animates the schedule turn by turn; **⏮ Prev / Next ⏭**
  step one turn; a **slider** scrubs to any turn; a label reads `turn N / total`.
- Drones **glide** between positions (CSS transitions). When several drones
  share a zone they **fan out** around a small ring so each stays visible.
- A drone crossing a restricted zone is drawn at the **connection midpoint**
  during its two-turn transit, matching the `D<id>-<src>-<dst>` token.
- A zone whose occupancy would exceed its capacity flashes a **red outline**.

**Who does what (the stack).** Each layer has one job:

- **HTML** (`viz_template.html`) builds the empty page and a blank
  `<svg id="stage">` — the drawing surface. It draws nothing itself; it just
  reserves the canvas and the slots the other layers fill.
- **SVG** is that vector surface. Its tags *are* the shapes: `<circle>` is a
  zone or a drone, `<line>` is a connection, `<text>` is a label. Vectors stay
  crisp at any zoom.
- **CSS** (`viz.css`) styles the *uniform* appearance — fill/stroke colours,
  line thickness, fonts, and the drone **glide** (a `transition` on the circle's
  centre, so a position change animates instead of teleporting).
- **JavaScript** (`viz.js`) runs in the browser: it reads the embedded map data,
  **generates** the SVG shapes and their positions, and drives the animation and
  controls. Data-driven styling that CSS can't express as a fixed rule (each
  zone's `color=`) is set inline by JS.

**Why the geometry lives in JS, not Python.** A browser only executes
JavaScript, and by the time the file is opened Python has already exited — so
anything interactive *must* be JS. The animation needs each zone's **pixel**
coordinates live, to drop drones onto zone centres or connection midpoints, so
the grid→pixel transform (scaling, padding, the y-flip) has to run in the
browser regardless. Computing those pixels in Python *as well* would duplicate
the same transform in two languages and invite drift — change the padding in one
and drones land off their zones. So Python ships only the **raw map data** (grid
coordinates, capacities, colours, and the turn-by-turn zone/edge *names*), and
JS is the **single source of truth** for pixels.

**Why it can't lie.** The per-turn positions are parsed straight from the same
`stdout` move log the grader reads — the visualizer replays the tokens rather
than re-deriving the schedule, so the animation and the log can never disagree.

---

## Resources

- 42 `lem-in` / network-flow background (single-commodity max-flow, min-cost max-flow, successive shortest paths).
- Johnson potentials for running Dijkstra on graphs with negative residual back-edges.

**How AI was used:** used as a reasoning partner to frame the problem as single-commodity flow (rather than MAPF), to compare the two candidate algorithms (unit max-flow vs. min-cost max-flow), and to weigh their scaling behaviour before committing to min-cost max-flow. All final algorithm choices, code, and implementation are the author's own.
