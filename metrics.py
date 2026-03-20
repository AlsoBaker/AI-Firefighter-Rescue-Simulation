# metrics.py

import numpy as np
from config import *


class SimulationMetrics:

    def __init__(self):
        self.reset()

    def reset(self):
        self.steps              = 0
        self.people_rescued     = 0
        self.people_burned      = 0    # now tracked live each step
        self.max_fire_spread    = 0
        self.fires_extinguished = 0

        self.fire_history        = []
        self.people_safe_history = []
        self.people_danger_history = []
        self.rescue_history      = []
        self.ff_hp_history       = []   # avg FF HP over time

        self.per_floor_rescued   = {i: 0 for i in range(NUM_FLOORS)}
        self.initial_people_count = 0
        self._prev_total_alive   = 0    # for burned tracking
        self.current_phase       = 'outbreak'

    def update(self, grids, firefighter_stats=None):
        self.steps += 1

        total_safe   = sum(int(np.sum(g == PERSON))        for g in grids)
        total_danger = sum(int(np.sum(g == PERSON_DANGER)) for g in grids)
        total_fire   = sum(int(np.sum(g == FIRE))          for g in grids)

        self.max_fire_spread = max(self.max_fire_spread, total_fire)

        if firefighter_stats:
            self.people_rescued = firefighter_stats.get('rescued', 0)
            avg_hp = firefighter_stats.get('avg_hp', FF_MAX_HP)
            self.ff_hp_history.append(avg_hp)

        # Live burned tracking:
        # Must include people currently being CARRIED by firefighters —
        # they are off the grid but not yet rescued, so without this
        # they falsely count as burned every step they are in transit.
        carrying = firefighter_stats.get('carrying', 0) if firefighter_stats else 0
        total_alive_now = total_safe + total_danger + self.people_rescued + carrying
        if self._prev_total_alive > 0:
            burned_this_step = max(0, self._prev_total_alive - total_alive_now)
            self.people_burned += burned_this_step
        self._prev_total_alive = total_alive_now

        self.fire_history.append(total_fire)
        self.people_safe_history.append(total_safe)
        self.people_danger_history.append(total_danger)
        self.rescue_history.append(self.people_rescued)

        self._detect_phase(total_fire, total_danger)

        return {'safe': total_safe, 'danger': total_danger, 'fire': total_fire}

    def _detect_phase(self, fire_cells, people_danger):
        if self.steps < 20:
            self.current_phase = 'outbreak'
        elif people_danger > 2 or fire_cells > 20:
            self.current_phase = 'critical'
        else:
            self.current_phase = 'recovery'

    def calculate_score(self, total_people):
        """Score out of 2000."""
        if total_people == 0:
            return 2000
        rescue_ratio = self.people_rescued / total_people
        base_score   = rescue_ratio * 1000

        efficiency   = max(0.0, 1.0 - (self.steps / 500))
        speed_bonus  = efficiency * 500

        grid_size    = ROWS * COLS * NUM_FLOORS
        fire_ratio   = self.max_fire_spread / grid_size
        # fire_bonus: reward for keeping fire small
        fire_bonus   = max(0.0, (1.0 - fire_ratio) * 300)

        danger_bonus = 100

        total = base_score + speed_bonus + fire_bonus + danger_bonus
        return min(2000.0, max(0.0, total))

    def get_summary(self, total_people, firefighter_stats):
        return {
            'total_steps':       self.steps,
            'people_rescued':    self.people_rescued,
            'people_burned':     self.people_burned,
            'rescue_percentage': (self.people_rescued / total_people * 100)
                                  if total_people > 0 else 0,
            'max_fire_cells':    self.max_fire_spread,
            'fires_extinguished': self.fires_extinguished,
            'avg_people_in_danger': (np.mean(self.people_danger_history)
                                     if self.people_danger_history else 0),
            'final_score':       self.calculate_score(total_people),
            'firefighter_stats': firefighter_stats,
            'phase':             self.current_phase,
            'per_floor_rescued': self.per_floor_rescued,
        }

    def print_report(self, total_people, firefighter_stats):
        s = self.get_summary(total_people, firefighter_stats)
        print("\n" + "="*60)
        print("SIMULATION FINAL REPORT")
        print("="*60)
        print(f"\nRESCUE STATISTICS")
        print(f"  Total Steps   : {s['total_steps']}")
        print(f"  Rescued       : {s['people_rescued']}/{total_people}")
        print(f"  Burned        : {s['people_burned']}")
        print(f"  Success Rate  : {s['rescue_percentage']:.1f}%")
        print(f"\nFIRE DYNAMICS")
        print(f"  Max Fire Spread   : {s['max_fire_cells']} cells")
        print(f"  Fires Extinguished: {s['fires_extinguished']}")
        print(f"\nFINAL SCORE : {s['final_score']:.0f} / 2000")
        print(f"Phase       : {s['phase'].upper()}")
        print("="*60 + "\n")
        return s

    def get_graph_data(self):
        return {
            'steps':   list(range(len(self.fire_history))),
            'fire':    self.fire_history,
            'safe':    self.people_safe_history,
            'danger':  self.people_danger_history,
            'rescued': self.rescue_history,
            'ff_hp':   self.ff_hp_history,
        }