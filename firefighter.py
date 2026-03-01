#firefighter.py

import numpy as np
from config import *
from planning import astar,bfs,dijkstra

# =====================================
# FIREFIGHTER CLASS (replaces globals)
# =====================================
class Firefighter:
    def __init__(self, start_pos):
        self.pos = start_pos
        self.carrying_person = False
        self.current_path = []
        self.under_cell = EMPTY
        self.people_rescued = 0
        self.stuck_counter = 0
        
    def is_at(self, pos):
        return self.pos == pos
    
    def reset_path(self):
        """Force recalculation on next move"""
        self.current_path = []
    
    def recalculate_if_blocked(self, grid):
        """Check if current path is blocked and recalculate"""
        if self.current_path:
            next_pos = self.current_path[0]
            r, c = next_pos
            if grid[r, c] == FIRE or grid[r, c] == OBSTACLE:
                self.reset_path()
                self.stuck_counter += 1


class FirefighterManager:
    """Manages all firefighters in the simulation"""
    
    def __init__(self, num_firefighters=1, algorithm="astar"):
        self.firefighters = []
        self.num_firefighters = num_firefighters
        self.algorithm = algorithm
        
    def find_path(self, grid, start, goal):
        """Use configured algorithm for pathfinding"""
        if self.algorithm == "astar":
            return astar(grid, start, goal)
        elif self.algorithm == "bfs":
            return bfs(grid, start, goal)
        elif self.algorithm == "dijkstra":
            return dijkstra(grid, start, goal)
        else:
            return astar(grid, start, goal)  # Default
        
    def initialize(self, grid):
        """Place firefighters on grid at starting positions"""
        self.firefighters = []
        positions = [
            (0, 0),
            (0, COLS-1),
            (ROWS-1, 0),
            (ROWS-1, COLS-1)
        ]
        
        for i in range(min(self.num_firefighters, len(positions))):
            r, c = positions[i]
            if grid[r, c] == EMPTY:
                self.firefighters.append(Firefighter((r, c)))
                grid[r, c] = FIREFIGHTER
        
        return grid
    
    def find_nearest_target(self, grid, start_pos):
        """Priority: danger people > safe people > none"""
        danger_people = np.argwhere(grid == PERSON_DANGER)
        danger_people = [tuple(p) for p in danger_people]
        
        if danger_people:
            targets = danger_people
        else:
            safe_people = np.argwhere(grid == PERSON)
            targets = [tuple(p) for p in safe_people]
        
        if not targets:
            return None
        
        # Manhattan distance
        distances = [
            abs(start_pos[0]-t[0]) + abs(start_pos[1]-t[1])
            for t in targets
        ]
        
        return targets[np.argmin(distances)]
    
    def move_all(self, grid):
        """Execute all firefighters' moves"""
        new_grid = grid.copy()
        firefighter_positions = set()  # Track firefighter positions to handle collisions

        for ff in self.firefighters:
            # Restore tile under firefighter
            new_grid[ff.pos] = ff.under_cell

            # Check if path is blocked
            ff.recalculate_if_blocked(new_grid)

            # ===== DECIDE GOAL =====
            if not ff.carrying_person:
                target = self.find_nearest_target(new_grid, ff.pos)

                if target is None:
                    # No one to rescue, wait
                    new_grid[ff.pos] = FIREFIGHTER
                    firefighter_positions.add(ff.pos)
                    continue

                if not ff.current_path:
                    ff.current_path = self.find_path(new_grid, ff.pos, target)
            else:
                # Carrying person - find nearest shelter
                shelters = np.argwhere(new_grid == SHELTER)
                shelters = [tuple(p) for p in shelters]

                if not shelters:
                    new_grid[ff.pos] = FIREFIGHTER
                    firefighter_positions.add(ff.pos)
                    continue

                # Find the closest shelter based on Manhattan distance
                distances = [
                    abs(ff.pos[0] - shelter[0]) + abs(ff.pos[1] - shelter[1])
                    for shelter in shelters
                ]
                target = shelters[np.argmin(distances)]  # Select the closest shelter
                if not ff.current_path:
                    ff.current_path = self.find_path(new_grid, ff.pos, target)

            # ===== FOLLOW PATH =====
            if not ff.current_path:
                new_grid[ff.pos] = FIREFIGHTER
                firefighter_positions.add(ff.pos)
                continue

            next_pos = ff.current_path.pop(0)
            nr, nc = next_pos

            # Handle collisions: Skip move if another firefighter is already at the destination
            if next_pos in firefighter_positions:
                new_grid[ff.pos] = FIREFIGHTER
                firefighter_positions.add(ff.pos)
                continue

            destination_cell = new_grid[nr, nc]

            # PICKUP
            if destination_cell in [PERSON, PERSON_DANGER]:
                ff.carrying_person = True
                print(f"🚒 Firefighter picked up person!")
                ff.under_cell = EMPTY  # Ensure the firefighter leaves an empty cell
                destination_cell = EMPTY

            # DELIVER
            elif destination_cell == SHELTER and ff.carrying_person:
                ff.carrying_person = False
                ff.people_rescued += 1
                print(f"✅ Delivered person! (Total: {ff.people_rescued})")
                ff.under_cell = EMPTY  # Ensure the firefighter leaves an empty cell

            # Remember underlying tile
            ff.under_cell = destination_cell
            ff.pos = next_pos

            # Place firefighter on new tile
            new_grid[nr, nc] = FIREFIGHTER
            firefighter_positions.add(next_pos)

        return new_grid
    
    def get_stats(self, grid):
        """Return current statistics"""
        total_rescued = sum(ff.people_rescued for ff in self.firefighters)
        return {
            'rescued': total_rescued,
            'firefighters': len(self.firefighters),
            'total_stuck_attempts': sum(ff.stuck_counter for ff in self.firefighters)
        }


# ===== BACKWARD COMPATIBILITY =====
# These functions maintain the original API

_manager = None

def initialize_firefighters(grid, num=1, algorithm="astar"):
    """Call this at start of simulation"""
    global _manager
    _manager = FirefighterManager(num, algorithm=algorithm)
    _manager.initialize(grid)
    return grid

def move_firefighter(grid):
    """Drop-in replacement for original function"""
    global _manager
    if _manager is None:
        _manager = FirefighterManager(1)
        _manager.initialize(grid)
    return _manager.move_all(grid)

def get_firefighter_stats(grid):
    """New function to get stats"""
    global _manager
    if _manager is None:
        return {}
    return _manager.get_stats(grid)