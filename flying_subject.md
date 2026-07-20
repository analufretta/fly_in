# Fly-in — Drone Routing Simulator

> Design an efficient drone routing system that navigates multiple drones through connected zones, minimizing simulation turns while respecting movement constraints.

---

## 1. Objective

Move all drones from the **start zone** to the **end zone** in the **fewest possible simulation turns**, respecting all capacity and movement constraints.

---

## 2. Constraints (Norm)

- **Language:** Python 3.10+
- **No graph libraries** allowed (e.g. `networkx`, `graphlib`, etc.) — implement graph logic yourself
- **Fully object-oriented** design
- **Fully typesafe**: `flake8` and `mypy` must both pass
  - `mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs`
  - (optional, recommended) `mypy . --strict`
- Type hints required everywhere applicable (functions, returns, variables)
- Docstrings required (PEP 257 — Google or NumPy style)
- Handle exceptions gracefully (`try/except`, context managers) — **a crash = non-functional project**
- Properly manage all resources (files, connections) via context managers
- Include a **Makefile** with: `install`, `run`, `debug`, `clean`, `lint`, (`lint-strict` optional)
- Include a `.gitignore` for Python artifacts
- Write your own test maps in addition to provided ones (tests not graded but recommended)
- All files must be placed **at the root of your Git repository**

---

## 3. Input File Format

```
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]

connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
```

### Rules
- Line 1: `nb_drones: <positive_integer>`
- Exactly **one** `start_hub` and **one** `end_hub`
- Zone names: unique, no dashes or spaces
- Metadata `[...]` is optional, order-independent:
  - `zone=<type>` (default `normal`)
  - `color=<any single word>` (default: none)
  - `max_drones=<N>` (default: 1) — **ignored** on start/end zones (unlimited there)
- Connections: `connection: <name1>-<name2> [max_link_capacity=<N>]` (default: 1)
  - Bidirectional, no duplicates (`a-b` == `b-a`)
  - Must reference already-defined zones
- Comments start with `#`
- Coordinates are always integers
- **Any invalid syntax → stop program with a clear error message (line + cause)**

### Zone types & movement cost
| Type | Cost | Notes |
|---|---|---|
| `normal` | 1 turn | default |
| `priority` | 1 turn | should be preferred by pathfinding |
| `restricted` | 2 turns | drone occupies connection, must arrive next turn (no waiting mid-flight) |
| `blocked` | — | cannot be entered, invalidates any path using it |

---

## 4. Occupancy & Movement Rules

- Default max occupancy per zone: **1 drone/turn** (unless `max_drones=N`)
- **Start** and **end** zones have unlimited capacity
- A drone may, each turn:
  - move to an adjacent zone (if capacity allows)
  - move onto a connection toward a restricted zone (must arrive exactly next turn — no waiting mid-connection)
  - stay in place (wait)
- Zone/connection capacity must never be exceeded
- Drones leaving a zone free capacity **within the same turn**
- Must avoid deadlocks and unnecessary delays; schedule for max throughput

---

## 5. Output Format

- One line per simulation turn
- Space-separated moves: `D<ID>-<zone>` or `D<ID>-<connection>` (in-flight to restricted zone)
- Drones that don't move are omitted from the line
- Drones reaching `end` are delivered and no longer tracked
- Simulation ends when all drones are delivered

```
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

---

## 6. Visual Representation (Mandatory)

Provide visual feedback via **at least one** of:
- Colored terminal output (drone movement, zone states)
- Graphical interface (network + drone positions)

---

## 7. Scoring

- Primary metric: **total simulation turns** to deliver all drones (lower = better)
- Valid simulation must respect all movement/occupancy/capacity rules
- Secondary (optional) metrics: drones moved/turn, avg turns/drone, total path cost, visualization quality

### Performance targets
| Difficulty | Target |
|---|---|
| Easy | < 10 turns |
| Medium | 10–30 turns |
| Hard | < 60 turns |
| Challenger (bonus, optional) | beat 45 turns |

---

## 8. README.md Requirements

Must include, in English:
1. First line (italic): `*This project has been created as part of the 42 curriculum by <login1>[, <login2>...]*`
2. **Description** — project goal & overview
3. **Instructions** — compile/install/run
4. **Resources** — references + how AI was used and for what
5. **Algorithm choices & implementation strategy** (detailed)
6. **Visual representation** documentation
7. Any other relevant sections (usage, features, technical choices)

---

## 9. Bonus (only reviewed if mandatory part is 100% complete)

- Meet or beat all reference turn targets on every provided map
- Solve the optional **Challenger map** ("The Impossible Dream", 25 drones) beating the 45-turn record

---

## 10. Submission & Peer-Review

- Submit via Git repo, all files at root
- Deliverable: parser + simulation engine + pathfinding algorithm(s) + visual output + correctly formatted log
- Be ready to **explain or modify your code live** during evaluation
- Evaluation maps may differ from the ones provided in the subject
