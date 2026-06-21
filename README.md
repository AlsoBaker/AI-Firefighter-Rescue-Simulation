# 🚒 AI Firefighter Rescue Simulation

A multi-agent AI simulation built with Python and Pygame where firefighters use pathfinding algorithms to rescue civilians from a spreading fire across multiple building floors — followed by a full emergency response pipeline on a procedurally generated city map.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![Pygame](https://img.shields.io/badge/Pygame-2.x-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

📄 **[Full Project Report](https://drive.google.com/file/d/16XC8qPywEdDmZpRGQBNo1GQBWOkSqeov/view?usp=sharing)** — literature review, architecture, algorithm benchmarking methodology, and a full validation/debugging writeup *(update this path once the report is added to the repo)*

---

## What it does

The simulation runs in three phases:

**Phase 1 — Emergency Dispatch**
A city map is generated. The player clicks any building to report a fire. A firetruck drives autonomously from the fire station to the burning building via A\* pathfinding. On arrival, a cutscene plays — the camera zooms into the building, a flash effect fires, and "ENTERING BUILDING" appears before fading to black.

**Phase 2 — Rescue Simulation**
Firefighter agents navigate the burning 20×20 grid building, rescuing civilians and delivering them to hospitals. Fire spreads probabilistically across 3 floors. Each agent has HP, a water tank, and uses configurable pathfinding to find the optimal route — routing through fire only when water reserves allow.

**Phase 3 — Ambulance Delivery**
After the rescue sim ends, an ambulance drives from the burning building (where the firetruck arrived) to the nearest hospital on the same city map. Traffic cars, traffic lights, and road closures add obstacles along the route. Pressing R after delivery restarts the entire pipeline from the dispatch screen.

---

## Features

### Dispatch Phase
- **Interactive city map** — 42×30 procedurally generated grid with roads, rivers, bridges, buildings, hospitals, and a fire station
- **Click-to-ignite** — hover over any building to highlight it; click to dispatch the firetruck
- **Firetruck A\* routing** — drives from fire station to the burning building's road entrance
- **Cutscene** — zoom into burning building → orange flash → "ENTERING BUILDING" banner → fade to black

### Rescue Simulation
- **3-floor building** with staircases connecting floors — firefighters navigate between floors autonomously
- **Up to 8 firefighters** spawned at fixed positions, each with independent state
- **HP system** — civilians start at 20 HP, firefighters at 35 HP, both lose HP per tick adjacent to fire
- **Water management** — each firefighter carries a 100-unit water tank; water is spent when extinguishing fire and shields the agent from HP damage; refills on hospital delivery
- **Fire-walking** — firefighters route through fire cells when water > 0, avoid them when empty
- **Per-floor fire spread** — Floor 1: 24% spread rate, Floor 2: 20%, Floor 3: 16%
- **Priority targeting** — danger civilians (adjacent to fire) rescued before safe ones
- **Full-path replanning** — scans entire planned path each tick, recalculates if any cell is blocked
- **Live HP bars** on every entity — green → orange → red as health drops
- **Water bars** shown below HP bars for each firefighter
- **Pixel art sprites** for civilians, firefighters, hospitals, and staircases

### Ambulance Phase
- **Same city map reused** — ambulance starts where the firetruck arrived, not the fire station
- **Traffic lights** — checkerboard pattern of staggered red/green lights at intersections; ambulance slows to 5% speed on red
- **Road closures** — 3 randomly placed barriers block road segments; connectivity to all hospitals is guaranteed
- **12 traffic cars** — roam roads and slow the ambulance to 40% speed when blocking its path
- **A\* to all 3 hospitals** — picks shortest real path, not straight-line distance
- **Siren effect** — red/blue pulsing ring around ambulance
- **Fading trail** — last 50 positions drawn behind ambulance with alpha fade
- **Road names** at intersections, crosswalk markings, dashed lane lines, building colour variation

### Analytics & Scoring
- **End-screen graph** — fire cells, rescued count, civilians in danger, and avg FF HP plotted over time
- **Leaderboard** — top 10 scores saved to `scores.json` with date, algorithm, rescued count, steps
- **Score out of 2000** — composite formula across six components (see [Scoring](#scoring) below)
- **Burned count fix** — civilians being carried are correctly excluded from the burned tally

---

## Benchmark Results

Algorithm performance was measured using a custom **headless test harness** that stubs out Pygame entirely with no-op replacements, letting all four pathfinding algorithms run head-to-head without rendering overhead.

To get a fair comparison, an **800-candidate random-seed search** was run to find a configuration (4 firefighters, 300-step budget) where every algorithm produces clearly separated outcomes under identical conditions — same obstacle layout, civilian positions, fire seeds, and fire spread sequence. Seed `194` was selected for showing minimum gaps exceeding 50 points between every adjacent algorithm pair.

| Algorithm | Score / 2000 | Gap to Next |
|---|---|---|
| BFS | 921 | — |
| Dijkstra | 1061 | +140 |
| A\* | 1192 | +131 |
| **D\* Lite** | **1286** | +94 |

**Why the ordering holds:**
- **BFS** treats fire cells the same as empty cells, leading agents into unnecessary fire crossings and faster water depletion.
- **Dijkstra's** weighted cost model (fire = 3, danger = 2, empty = 1) discourages unsafe routing, improving water conservation over BFS.
- **A\*'s** Manhattan-distance heuristic reduces cells expanded per replan, leaving more of the step budget for actual navigation.
- **D\* Lite** wins by repairing only the portion of its search tree affected by each fire-spread event — at a cost proportional to the number of changed cells — rather than replanning from scratch like the other three.

*The headless harness isn't part of the current public repo — worth adding as a documented entry point (e.g. `benchmark.py --seed 194`) so these numbers are independently reproducible.*

---

## Engineering Process: Validation & Debugging

After the initial implementation was complete, a systematic line-by-line audit of the entire codebase was conducted, identifying and resolving **10 logic errors across 6 modules**. Each was diagnosed by root cause rather than patched at the symptom. A few representative examples:

- **Civilian fire-damage gap** (`health.py`) — a civilian whose cell was overwritten by fire spread on the same tick wasn't taking damage that tick, because the damage check ran against the already-updated cell value rather than checking the civilian's own cell state directly. Fixed by adding an on-fire check in addition to adjacency.
- **D\* Lite stale g-values after water depletion** (`firefighter.py`) — when a firefighter's water tank emptied mid-route, the existing D\* Lite search tree (built while fire was traversable) kept producing paths through fire using now-invalid costs. Fixed by detecting the policy change and rebuilding the search instance from scratch under the new constraints.
- **Score overflow edge case** (`metrics.py`) — the rescue ratio could exceed 1.0 when carried civilians were double-counted at simulation end, inflating the quadratic base score past its intended cap. Fixed by clamping the ratio to `min(1.0, ratio)` before the score computation.
- **False pathfinding failure on self-collocation** (`firefighter.py`) — all four algorithms correctly return an empty path when an agent is already standing on its target, but the decision loop treated any empty path as a failure — causing agents to mark their own position as unreachable. Fixed with an explicit "already there" check.

Full writeup of all 10 fixes — symptom, root cause, and resolution — is in the [project report](https://drive.google.com/file/d/16XC8qPywEdDmZpRGQBNo1GQBWOkSqeov/view?usp=sharing).

---

## File structure

```
├── main.py              Entry point, CLI parser, full pipeline loop
├── config.py            All constants — HP, water, cell types, grid size
├── environment.py       Per-floor grid generation (obstacles, people, fire, hospitals)
├── fire.py              Probabilistic fire spread, per-floor spread rates
├── firefighter.py       Firefighter class, FirefighterManager, multi-floor targeting
├── floors.py            FloorManager — staircase switching, cross-floor targeting
├── health.py            HealthSystem — civilian HP tracking, fire damage ticks
├── planning.py          A*, BFS, Dijkstra, D* Lite pathfinding algorithms
├── metrics.py           SimulationMetrics — score calculation, history tracking
├── leaderboard.py       Load/save top 10 scores to scores.json
├── visualize.py         Pygame rescue sim loop, rendering, end screen
├── city_map.py          City grid generator — roads, river, bridges, closures, traffic lights
├── city_phase_base.py   Shared rendering base for firetruck and ambulance phases
├── firetruck.py         FiretruckPhase — dispatch screen, A* drive, cutscene
├── ambulance.py         AmbulancePhase — city rendering, A*, traffic, siren, trail
├── scores.json          Auto-generated leaderboard file
└── assets/
    ├── civilian.png
    ├── firefighter.png
    ├── firetruck.png
    ├── hospital.png
    ├── firestation.png
    ├── ambulance.png
    ├── exit.png          (used for staircase cells)
    └── building1-10.png  (city building sprites)
```

---

## Setup

**Requirements**
```
pip install pygame numpy
```

**Run**
```bash
python main.py
```

**CLI options**
```bash
python main.py --firefighters 4        # number of firefighters (max 8)
python main.py --steps 500             # max simulation steps
python main.py --algorithm dstar_lite  # pathfinding: astar | bfs | dijkstra | dstar_lite
python main.py --seed 42               # fixed seed for reproducible runs
```

---

## Controls

### Dispatch Phase
| Key / Action | Effect |
|-------------|--------|
| Click building | Report fire, dispatch firetruck |
| `↑` / `↓` | Firetruck speed (during drive) |
| `R` | Generate new city |
| `ESC` | Quit |

### Rescue Simulation
| Key | Action |
|-----|--------|
| `SPACE` | Pause / resume |
| `↑` / `↓` | Increase / decrease speed |
| `1` / `2` / `3` | Switch viewed floor |
| `R` | Reset simulation |
| `ESC` | Quit |

### End Screen
| Key | Action |
|-----|--------|
| `A` | Launch ambulance phase |
| `R` | Restart simulation |
| `ESC` | Quit |

### Ambulance Phase
| Key | Action |
|-----|--------|
| `↑` / `↓` | Speed up / slow down |
| `R` | Restart from dispatch (full pipeline reset) |
| `ESC` | Quit |

---

## How the AI works

### Firefighter agent loop
```
Sense  → scan grid for PERSON_DANGER, PERSON, HOSPITAL, STAIRCASE
Decide → pick nearest unclaimed target (danger-first), plan path
Act    → follow path one cell per tick, pick up / deliver civilians
Replan → if any cell on planned path is now fire/obstacle, recalculate
```

### Targeting priority
1. `PERSON_DANGER` on current floor (adjacent to fire)
2. `PERSON` on current floor (safe but unrescued)
3. Staircase toward best floor (most danger civilians)

### Multi-agent coordination
At the start of each tick, every agent claims its chosen target (adding it to a per-floor claimed set) before other agents on the same floor process their decision. This prevents multiple firefighters from converging on the same civilian while ignoring others — a lightweight allocation mechanism rather than explicit inter-agent communication.

### Water + fire-walking
- `water > 0` → fire cells treated as passable (cost 3 in Dijkstra / D\* Lite)
- `water == 0` → fire cells blocked, standard safe routing
- Standing on or adjacent to fire drains 2 water/step
- Hospital delivery refills +20 water (capped at 100)
- When water transitions from available to exhausted mid-route, the active D\* Lite instance is discarded and rebuilt under the new traversal policy, rather than patching the flag alone — see [Engineering Process](#engineering-process-validation--debugging)

### Ambulance routing
- A\* runs from the burning building's road entrance to each of the 3 hospitals
- Picks the hospital with the shortest actual path length
- `RIVER` cells are walls; `BRIDGE` cells are passable
- `ROAD_CLOSURE` cells are walls; connectivity to all hospitals is guaranteed at generation time
- Ambulance slows at red traffic lights and behind blocking cars

---

## Scoring

> ⚠️ **Verify against `metrics.py` before relying on this table** — this reflects the formula documented in the project report; confirm it matches the current implementation.

The simulation evaluates performance through a composite score bounded between 0 and 2000 points, computed from six components at the end of each run:

| Component | Range | Formula |
|---|---|---|
| Base (rescue ratio) | 0 – 900 | `min(1, rescued/total)² × 900` |
| Zero-burn bonus | 0 – 150 | `max(0, 1 − burn_ratio/0.25) × 150` |
| Speed bonus | 0 – 350 | `max(0, (1 − steps/max_steps)^0.7) × 350` |
| Fire control bonus | 0 – 250 | `max(0, 1 − avg_fire/120) × 250` |
| Extinguish bonus | 0 – 150 | `min(150, fires_extinguished × 5)` |
| Casualty penalty | subtracted | `burn_ratio² × 250 + burn_ratio × 100` |

The base component is **quadratic**, penalising partial rescues more steeply than a linear scale would. The zero-burn bonus is a cliff reward — it only reaches its maximum when no civilians are lost. The fire control bonus uses *average* fire cell count over the full run rather than peak fire, since peak fire is highly seed-dependent while the average better reflects sustained containment quality.

---

## Algorithms

| Algorithm | Used for | Notes |
|-----------|----------|-------|
| A\* | Default firefighter pathfinding; ambulance + firetruck routing | Manhattan distance heuristic, optimal on static grids |
| BFS | Optional via `--algorithm bfs` | Guaranteed shortest hop-count path, no heuristic |
| Dijkstra | Optional via `--algorithm dijkstra` | Weighted edges — treats fire cells as cost 3 when water > 0, danger cells as cost 2 |
| D\* Lite | Optional via `--algorithm dstar_lite` | Incremental replanning — repairs the existing search tree when fire spreads instead of replanning from scratch; highest-scoring algorithm in benchmarking (see above) |

All four are implemented from first principles — no pathfinding libraries.

---

## Configuration

Key values in `config.py`:

```python
ROWS, COLS       = 20, 20       # grid dimensions per floor
NUM_FLOORS       = 3            # number of building floors
CIVILIAN_MAX_HP  = 20           # civilian starting HP
FF_MAX_HP        = 35           # firefighter starting HP
WATER_MAX        = 100          # firefighter water tank capacity
WATER_REFILL     = 20           # water refilled per hospital delivery
```

Fire spread rates in `fire.py`:

```python
_SPREAD_PROB = [0.24, 0.20, 0.16]   # [floor 1, floor 2, floor 3]
```

Spread frequency (all floors):

```python
if step % 4 != 0:   # fire spreads every 4 steps; lower = more frequent
    return new_grid
```

City map constants in `city_map.py`:

```python
CITY_COLS  = 42      # city grid width
CITY_ROWS  = 30      # city grid height
BLOCK_SIZE = 6       # cells per building block
TL_CYCLE   = 90      # traffic light cycle in frames (60 FPS)
TL_GREEN   = 60      # frames spent green per cycle
```
