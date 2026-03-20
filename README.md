# 🚒 AI Firefighter Rescue Simulation

A multi-agent AI simulation built with Python and Pygame where firefighters use pathfinding algorithms to rescue civilians from a spreading fire across multiple building floors — followed by an ambulance delivery phase on a procedurally generated city map.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![Pygame](https://img.shields.io/badge/Pygame-2.x-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## What it does

The simulation runs in two phases:

**Phase 1 — Rescue Simulation**
Firefighter agents navigate a burning 20×20 grid building, rescuing civilians and delivering them to hospitals. Fire spreads probabilistically across 3 floors. Each agent has HP, a water tank, and uses A\* pathfinding to find the optimal route — routing through fire only when water reserves allow.

**Phase 2 — Ambulance Delivery**
After the rescue sim ends, launch an ambulance phase on a procedurally generated city map. A\* finds the nearest hospital from the fire station across roads, intersections, parks, and rivers. Traffic cars roam the streets and slow the ambulance when blocking its path.

---

## Features

### Rescue Simulation
- **3-floor building** with staircases connecting floors — firefighters navigate between floors autonomously
- **Up to 8 firefighters** spawned at fixed positions, each with independent state
- **HP system** — civilians start at 15 HP, firefighters at 35 HP, both lose HP per tick adjacent to fire
- **Water management** — each firefighter carries a 100-unit water tank; water is spent when extinguishing fire and shields the agent from HP damage; refills on hospital delivery
- **Fire-walking** — firefighters route through fire cells when water > 0, avoid them when empty
- **Per-floor fire spread** — Floor 1: 12% spread rate, Floor 2: 5%, Floor 3: 3%
- **Priority targeting** — danger civilians (adjacent to fire) rescued before safe ones
- **Full-path replanning** — scans entire planned path each tick, recalculates if any cell is blocked
- **Live HP bars** on every entity — green → orange → red as health drops
- **Water bars** shown below HP bars for each firefighter
- **Pixel art sprites** for civilians, firefighters, hospitals, and staircases

### Ambulance Phase
- **Procedurally generated city** — 42×30 grid, roads every 6 cells forming blocks
- **Rivers with bridges** — one horizontal river per map, crossable only at bridge cells
- **Parks** — 2–3 building blocks replaced with impassable green parks
- **A\* to all 3 hospitals** — picks shortest real path, not straight-line distance
- **Traffic cars** — 6 cars roam roads, bouncing at dead ends; ambulance slows to 40% when blocked
- **Siren effect** — red/blue pulsing ring around ambulance
- **Fading trail** — last 50 positions drawn behind ambulance with alpha fade
- **Road names** at intersections, crosswalk markings, dashed lane lines, building color variation

### Analytics & Scoring
- **End-screen graph** — fire cells, rescued count, civilians in danger, and avg FF HP plotted over time
- **Leaderboard** — top 10 scores saved to `scores.json` with date, algorithm, rescued count, steps
- **Score out of 2000** — based on rescue ratio, speed efficiency, and fire control
- **Burned count fix** — civilians being carried are correctly excluded from the burned tally

---

## File structure

```
├── main.py            Entry point and CLI argument parser
├── config.py          All constants — HP, water, cell types, grid size
├── environment.py     Per-floor grid generation (obstacles, people, fire, hospitals)
├── fire.py            Probabilistic fire spread, per-floor spread rates
├── firefighter.py     Firefighter class, FirefighterManager, multi-floor targeting
├── floors.py          FloorManager — staircase switching, cross-floor targeting
├── health.py          HealthSystem — civilian HP tracking, fire damage ticks
├── planning.py        A*, BFS, Dijkstra — all support allow_fire param
├── metrics.py         SimulationMetrics — score calculation, history tracking
├── leaderboard.py     Load/save top 10 scores to scores.json
├── visualize.py       Pygame simulation loop, rendering, end screen
├── city_map.py        City grid generator — roads, parks, river, bridges, buildings
├── ambulance.py       AmbulancePhase — city rendering, A*, traffic, siren, trail
├── scores.json        Auto-generated leaderboard file
└── assets/
    ├── civilian.png
    ├── firefighter.png
    ├── hospital.png
    ├── exit.png        (used for staircase cells)
    └── ambulance.png
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
python main.py --firefighters 4      # number of firefighters (max 8)
python main.py --steps 500           # max simulation steps
python main.py --algorithm bfs       # pathfinding: astar | bfs | dijkstra
python main.py --seed 42             # fixed seed for reproducible runs
```

---

## Controls

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
| `R` | Generate new city |
| `ESC` | Return to sim loop |

---

## How the AI works

### Firefighter agent loop
```
Sense  → scan grid for PERSON_DANGER, PERSON, HOSPITAL, STAIRCASE
Decide → pick nearest unclaimed target (danger-first), plan path via A*
Act    → follow path one cell per tick, pick up / deliver civilians
Replan → if any cell on planned path is now fire/obstacle, recalculate
```

### Targeting priority
1. `PERSON_DANGER` on current floor (adjacent to fire)
2. `PERSON` on current floor (safe but unrescued)
3. Staircase toward best floor (most danger civilians)

### Water + fire-walking
- `water > 0` → fire cells treated as passable (cost 3 in Dijkstra)
- `water == 0` → fire cells blocked, standard safe routing
- Standing on fire drains 2 water/step
- Hospital delivery refills +20 water (capped at 100)

### Ambulance routing
- A\* runs from fire station to each of the 3 hospitals
- Picks the hospital with the shortest actual path length
- RIVER cells are walls; BRIDGE cells are passable
- PARK cells are walls; ambulance routes around them

---

## Scoring

| Component | Points |
|-----------|--------|
| Base (rescued / total × 1000) | 0 – 1000 |
| Speed bonus (efficiency × 500) | 0 – 500 |
| Fire control bonus | 0 – 300 |
| Danger avoidance bonus | 100 |
| **Maximum** | **2000** |

---

## Algorithms

| Algorithm | Used for | Notes |
|-----------|----------|-------|
| A\* | Firefighter pathfinding (default), ambulance routing | Manhattan distance heuristic |
| BFS | Optional via `--algorithm bfs` | Guaranteed shortest path, no heuristic |
| Dijkstra | Optional via `--algorithm dijkstra` | Weighted edges — treats fire cells as cost 3 when water > 0 |

---

## Configuration

Key values in `config.py`:

```python
ROWS, COLS       = 20, 20       # grid dimensions per floor
NUM_FLOORS       = 3            # number of building floors
CIVILIAN_MAX_HP  = 15           # civilian starting HP
FF_MAX_HP        = 35           # firefighter starting HP
WATER_MAX        = 100          # firefighter water tank capacity
WATER_REFILL     = 20           # water refilled per hospital delivery
```

Fire spread rates in `fire.py`:

```python
_SPREAD_PROB = [0.12, 0.05, 0.03]   # [floor 1, floor 2, floor 3]
```

Spread frequency (all floors):

```python
if step % 4 != 0:   # fire spreads every 4 steps; lower = more frequent
    return new_grid
```