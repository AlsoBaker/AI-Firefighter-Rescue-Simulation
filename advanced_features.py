# advanced_features.py

import numpy as np
from config import *


class FireExtinguisher:
    """
    Firefighters can extinguish fire within range
    This creates a secondary mechanic beyond just rescue
    """
    
    def __init__(self, range=3, cooldown=5):
        self.range = range
        self.cooldown = cooldown
        self.cooldown_counter = 0
    
    def can_extinguish(self):
        return self.cooldown_counter <= 0
    
    def extinguish(self, grid, firefighter_pos):
        """Extinguish fire in range of firefighter"""
        if not self.can_extinguish():
            self.cooldown_counter -= 1
            return grid
        
        fr, fc = firefighter_pos
        new_grid = grid.copy()
        
        # Find all fire within range
        for r in range(max(0, fr-self.range), min(ROWS, fr+self.range+1)):
            for c in range(max(0, fc-self.range), min(COLS, fc+self.range+1)):
                if grid[r, c] == FIRE:
                    # Manhattan distance
                    dist = abs(r - fr) + abs(c - fc)
                    if dist <= self.range:
                        new_grid[r, c] = EMPTY
        
        self.cooldown_counter = self.cooldown
        return new_grid


class EvacuationZone:
    """
    Dynamic evacuation zones that expand as fire spreads
    Firefighters prioritize people in evacuation zones
    """
    
    def __init__(self, initial_radius=8):
        self.radius = initial_radius
        self.center = (ROWS // 2, COLS // 2)
        self.priority_boost = 1.5
    
    def is_in_zone(self, pos):
        """Check if position is in evacuation zone"""
        r, c = pos
        cr, cc = self.center
        return abs(r - cr) + abs(c - cc) <= self.radius
    
    def update(self, fire_count):
        """Shrink evacuation zone as fire spreads"""
        # More fire = smaller safe zone
        self.radius = max(3, 8 - (fire_count // 20))
    
    def get_safe_shelters(self, grid):
        """Get shelters within evacuation zone"""
        shelter_positions = np.argwhere(grid == SHELTER)
        safe_shelters = [
            tuple(p) for p in shelter_positions
            if self.is_in_zone(tuple(p))
        ]
        return safe_shelters if safe_shelters else [tuple(shelter_positions[0])] if len(shelter_positions) > 0 else []


class PerformanceMonitor:
    """Track computational performance"""
    
    def __init__(self):
        self.path_calculations = 0
        self.path_recalculations = 0
        self.avg_path_length = 0
        self.fire_spread_checks = 0
        self.total_fire_cells_processed = 0
    
    def record_path_calc(self, path_length, is_recalc=False):
        self.path_calculations += 1
        if is_recalc:
            self.path_recalculations += 1
        
        # Update running average
        old_avg = self.avg_path_length
        self.avg_path_length = (
            (old_avg * (self.path_calculations - 1) + path_length) / self.path_calculations
        )
    
    def print_stats(self):
        print("\n" + "="*50)
        print("PERFORMANCE STATISTICS")
        print("="*50)
        print(f"Path Calculations: {self.path_calculations}")
        print(f"Path Recalculations: {self.path_recalculations}")
        print(f"Avg Path Length: {self.avg_path_length:.1f}")
        print("="*50 + "\n")