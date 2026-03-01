# 🚒 AI Firefighter Rescue Simulation

An intelligent simulation where a firefighter agent uses **A* pathfinding** to rescue civilians from a spreading fire while navigating obstacles.

## 🎯 Project Overview

This project demonstrates several AI and algorithms concepts:

- **Pathfinding**: A* algorithm with Manhattan distance heuristic
- **Agent Intelligence**: Priority-based targeting and dynamic decision making
- **Simulation**: Probabilistic fire spreading with real-time visualization
- **Multi-Agent Systems**: Support for multiple firefighters
- **Performance Metrics**: Scoring system and analytics

## 📁 File Structure

### Core Files (Original)
- **`config.py`** - Game constants and grid cell types
- **`environment.py`** - Grid initialization with obstacles, people, shelters, fire
- **`fire.py`** - Fire spreading logic with probabilistic neighbor infection
- **`firefighter.py`** - Original single firefighter agent (basic version)
- **`planning.py`** - A* pathfinding algorithm
- **`visualize.py`** - Matplotlib animation and visualization
- **`main.py`** - Entry point

### Enhanced Files (New)
- **`firefighter_enhanced.py`** - Multi-firefighter support with object-oriented design
- **`metrics.py`** - Comprehensive metrics and scoring system
- **`visualize_enhanced.py`** - Improved visualization with real-time statistics
- **`advanced_features.py`** - Additional algorithms (BFS, Dijkstra) and optional features
- **`main_enhanced.py`** - Enhanced entry point with CLI arguments

## 🚀 Quick Start

### Basic Run (Single Firefighter)
```bash
python main.py
```

### Enhanced Version (Recommended)
```bash
# Single firefighter, 300 steps
python main_enhanced.py

# Multiple firefighters
python main_enhanced.py --firefighters 2

# Custom simulation length
python main_enhanced.py --steps 500

# Combined
python main_enhanced.py --firefighters 3 --steps 400
```

## 🧠 Key Features

### 1. A* Pathfinding
- Efficient optimal path finding
- Avoids obstacles and fire
- Heuristic: Manhattan distance
- Recalculates if path becomes blocked

### 2. Smart Targeting
**Priority System:**
1. People in danger (near fire) → highest priority
2. Safe people → second priority
3. No targets → wait/idle

### 3. Fire Spreading
- Spreads every 4 frames (configurable)
- 12% probability to infect adjacent cells
- Marks nearby people as "in danger"
- Affects pathfinding (avoided)

### 4. Multi-Agent Support
- Multiple firefighters start at corners
- Each has independent memory and state
- Shared grid environment
- No collision conflicts

### 5. Metrics & Scoring
```
Base Score = (rescued / total) × 1000
Speed Bonus = efficiency × 500 (up to 500 points)
Fire Penalty = max_fire_cells × 5 (up to -200 points)
TOTAL SCORE = Base + Speed - Penalty (max: 1500)
```

## 🔧 Configuration

Edit `config.py` to adjust:
```python
ROWS = 20          # Grid height
COLS = 20          # Grid width
EMPTY = 0
PERSON = 1
SHELTER = 2
FIRE = 3
OBSTACLE = 4
FIREFIGHTER = 5
PERSON_DANGER = 6
```

## 📊 Visualization

Real-time display shows:
- **Left Panel**: Animated grid with fire flicker effect
- **Right Panel**: Live statistics and scoring
- **Color Legend**: 7 different cell types

### Colors
| Color | Meaning |
|-------|---------|
| 🟩 Green | Safe person |
| 🟪 Purple | Person in danger |
| 🔵 Cyan | Shelter/Exit |
| 🔴 Red | Fire |
| ⬛ Black | Obstacle |
| 🟧 Orange | Firefighter |
| ⬜ Gray | Empty space |

## 🎓 AI Concepts Demonstrated

### 1. Heuristic Search
- A* algorithm beats Dijkstra and BFS
- Good heuristics → fewer node expansions
- Manhattan distance works well for grid navigation

### 2. Agent Architecture
```
Sense → Decide → Act
├─ Sense: Find people, detect fire, observe obstacles
├─ Decide: Prioritize targets, calculate path
└─ Act: Move along path, pickup/deliver people
```

### 3. State Management
- Firefighter position tracking
- Carrying state (person or empty)
- Path planning memory
- "Under cell" restoration

### 4. Dynamic Replanning
- Original path blocked? Recalculate
- New threats emerge? Reprioritize
- Change in environment → adaptive response

## 📈 Performance Tips

### To improve rescue rate:
1. **More firefighters** → cover more ground
   ```bash
   python main_enhanced.py --firefighters 4
   ```

2. **Better pathfinding** → use Dijkstra for risky areas
   - Edit `planning.py` to switch algorithms

3. **Fire awareness** → modify spread probability in `fire.py`
   - Reduce `0.12` to `0.08` for slower spreading

### To improve score:
- Rescue quickly (speed bonus)
- Minimize fire spread (penalty reduction)
- Balance: rescue vs. fire control trade-off

## 🔬 Extension Ideas

### For Project Enhancement:
1. **Fire Extinguishing** - Firefighters spray water to stop fire
   - See `advanced_features.py` → `FireExtinguisher` class
   - Adds action cooldown mechanic

2. **Evacuation Zones** - Dynamic safe zones
   - `EvacuationZone` class in advanced features
   - Expands/shrinks based on fire spread

3. **Different Pathfinding** - Compare algorithms
   - A* vs BFS vs Dijkstra
   - Performance metrics included

4. **Machine Learning** - Train agent with reinforcement learning
   - Grid state → action mapping
   - Optimize policy to maximize score

5. **Resource Management** - Limited water/fuel
   - Firefighter stamina
   - Equipment degradation

6. **Realistic Physics** - Wind direction, fire intensity
   - Directional fire spread
   - Heat radiation effects

## 📝 Algorithm Complexity

| Algorithm | Time | Space | Use Case |
|-----------|------|-------|----------|
| A* | O(b^d) | O(b^d) | **Our choice** - optimal + efficient |
| Dijkstra | O(E log V) | O(V) | Weighted edges |
| BFS | O(V + E) | O(V) | Unweighted, simpler |

*Where b = branching factor, d = depth*

## 🐛 Debugging

Enable debug info in `visualize_enhanced.py`:
```python
# Add to update() function:
print(f"Step {step}: Fire={fire_cells}, People={people_safe+people_danger}")
```

Monitor firefighter stuck attempts:
```python
ff_stats = get_firefighter_stats(grid)
print(f"Stuck attempts: {ff_stats['total_stuck_attempts']}")
```

## 📚 References

- **A* Algorithm**: Hart, Nilsson, Raphael (1968)
- **Pathfinding**: Red Blob Games pathfinding guide
- **Heuristics**: Manhattan distance, Chebyshev distance
- **Multi-agent**: Independent agents in shared environment

## 🎯 Project Checklist

- ✅ Core A* pathfinding working
- ✅ Fire spreading simulation
- ✅ Priority-based targeting
- ✅ Visualization with animation
- ✅ Multiple firefighters support
- ✅ Metrics and scoring
- ✅ Performance optimizations
- ✅ Documentation
- 📝 Your ideas here!

## 💡 Pro Tips

1. **Run multiple times** - Results vary due to randomization
2. **Compare configurations** - See which works best
3. **Watch the visualization** - Understand firefighter behavior
4. **Check the console output** - Detailed event logging
5. **Experiment with parameters** - Learn cause/effect relationships

## 📞 Support

Issues or questions? Check:
1. Grid initialization in `environment.py`
2. Fire spreading rules in `fire.py`
3. Pathfinding in `planning.py`
4. Agent logic in `firefighter_enhanced.py`
