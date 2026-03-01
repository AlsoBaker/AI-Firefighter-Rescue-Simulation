#metrics.py

import numpy as np
from config import *

class SimulationMetrics:
    """Track comprehensive metrics throughout simulation"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.steps = 0
        self.people_rescued = 0
        self.people_burned = 0
        self.people_remaining = 0
        self.max_fire_spread = 0
        self.fires_extinguished = 0
        self.fire_history = []
        self.people_safe_history = []
        self.people_danger_history = []
        self.rescue_history = []
        self.initial_people_count = 0
        self.current_phase = 'outbreak'
        
    def update(self, grid, firefighter_stats=None):
        """Update metrics based on current grid state"""
        self.steps += 1
        
        people_safe = np.sum(grid == PERSON)
        people_danger = np.sum(grid == PERSON_DANGER)
        fire_cells = np.sum(grid == FIRE)
        
        self.people_remaining = people_safe + people_danger
        self.max_fire_spread = max(self.max_fire_spread, fire_cells)
        
        # Update from firefighter stats
        if firefighter_stats:
            self.people_rescued = firefighter_stats.get('rescued', 0)
            self.fires_extinguished = firefighter_stats.get('extinguished', 0)
        
        # Track histories
        self.fire_history.append(fire_cells)
        self.people_safe_history.append(people_safe)
        self.people_danger_history.append(people_danger)
        self.rescue_history.append(self.people_rescued)
        
        # Detect phase
        self._detect_phase(fire_cells, people_danger)
        
        return {
            'safe': people_safe,
            'danger': people_danger,
            'fire': fire_cells
        }
    
    def _detect_phase(self, fire_cells, people_danger):
        """Detect simulation phase"""
        if self.steps < 20:
            self.current_phase = 'outbreak'
        elif people_danger > 2 or fire_cells > 20:
            self.current_phase = 'critical'
        else:
            self.current_phase = 'recovery'
    
    def calculate_score(self, total_people):
        """
        Scoring system (0-2000):
        - Base: (rescued / total) * 1000
        - Speed: efficiency * 500
        - Fire Control: fire_minimization * 300
        - Danger Avoidance: 100 points
        """
        if total_people == 0:
            return 2000
        
        rescue_ratio = self.people_rescued / total_people
        base_score = rescue_ratio * 1000
        
        efficiency = max(0, 1 - (self.steps / 500))
        speed_bonus = efficiency * 500
        
        grid_size = ROWS * COLS
        fire_ratio = self.max_fire_spread / grid_size
        fire_bonus = max(0, (1 - fire_ratio) * 300)
        
        danger_bonus = 100
        
        total = base_score + speed_bonus + fire_bonus + danger_bonus
        return min(2000, max(0, total))
    
    def get_summary(self, total_people, firefighter_stats):
        """Generate final summary report"""
        summary = {
            'total_steps': self.steps,
            'people_rescued': self.people_rescued,
            'people_burned': self.people_burned,
            'rescue_percentage': (self.people_rescued / total_people * 100) if total_people > 0 else 0,
            'max_fire_cells': self.max_fire_spread,
            'fires_extinguished': self.fires_extinguished,
            'avg_people_in_danger': np.mean(self.people_danger_history) if self.people_danger_history else 0,
            'final_score': self.calculate_score(total_people),
            'firefighter_stats': firefighter_stats,
            'phase': self.current_phase
        }
        return summary
    
    def print_report(self, total_people, firefighter_stats):
        """Print formatted report"""
        summary = self.get_summary(total_people, firefighter_stats)
        
        print("\n" + "="*60)
        print("🚒 SIMULATION FINAL REPORT 🔥")
        print("="*60)
        print(f"\n📊 RESCUE STATISTICS")
        print(f"  Total Steps: {summary['total_steps']}")
        print(f"  People Rescued: {summary['people_rescued']}/{total_people}")
        print(f"  Success Rate: {summary['rescue_percentage']:.1f}%")
        print(f"\n🔥 FIRE DYNAMICS")
        print(f"  Max Fire Spread: {summary['max_fire_cells']} cells")
        print(f"  Fires Extinguished: {summary['fires_extinguished']}")
        print(f"  Avg People in Danger: {summary['avg_people_in_danger']:.1f}")
        print(f"\n⭐ FINAL SCORE: {summary['final_score']:.0f}/2000")
        print(f"  Phase: {summary['phase'].upper()}")
        print("="*60 + "\n")
        
        return summary
    
    def get_graph_data(self):
        """Return data for graphing"""
        return {
            'steps': list(range(len(self.fire_history))),
            'fire': self.fire_history,
            'safe': self.people_safe_history,
            'danger': self.people_danger_history,
            'rescued': self.rescue_history,
        }