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
            self.people_rescued     = firefighter_stats.get('rescued', 0)
            self.fires_extinguished = firefighter_stats.get('extinguished', 0)
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
        elif people_danger > 2 or fire_cells > 20 * NUM_FLOORS:
            self.current_phase = 'critical'
        else:
            self.current_phase = 'recovery'

    def calculate_score(self, total_people, max_steps=300):
        """
        Score out of 2000.

        Components
        ──────────
        base             (0–900)  rescue_ratio × 900
        casualty_bonus   (0–200)  (1 - burn_ratio) × 200
        speed_bonus      (0–400)  relative to YOUR configured step budget
        fire_bonus       (0–300)  average fire cells over time, not peak
        extinguish_bonus (0–100)  min(100, fires_extinguished × 2)
        penalty          (0–200)  burn_ratio × 200  subtracted for burns
        """
        if total_people == 0:
            return 2000.0

        rescue_ratio = self.people_rescued / total_people
        burn_ratio   = min(1.0, self.people_burned / total_people)

        # Base: how many civilians were saved
        base = rescue_ratio * 900

        # Casualty bonus: reward for zero burns
        casualty_bonus = (1.0 - burn_ratio) * 200

        # Speed bonus: relative to the configured step budget
        efficiency   = max(0.0, 1.0 - (self.steps / max(1, max_steps)))
        speed_bonus  = efficiency * 400

        # Fire bonus: average fire cell count (not peak — peak is luck-dependent)
        grid_size = ROWS * COLS * NUM_FLOORS
        avg_fire  = float(np.mean(self.fire_history)) if self.fire_history else 0.0
        fire_bonus = max(0.0, (1.0 - avg_fire / grid_size) * 300)

        # Extinguish bonus: reward active firefighting
        extinguish_bonus = min(100.0, self.fires_extinguished * 2.0)

        # Casualty penalty: cost for every civilian lost
        penalty = burn_ratio * 200

        total = base + casualty_bonus + speed_bonus + fire_bonus + extinguish_bonus - penalty
        return min(2000.0, max(0.0, total))

    def get_summary(self, total_people, firefighter_stats, max_steps=300):
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
            'final_score':       self.calculate_score(total_people, max_steps),
            'firefighter_stats': firefighter_stats,
            'phase':             self.current_phase,
        }

    def print_report(self, total_people, firefighter_stats, max_steps=300):
        s = self.get_summary(total_people, firefighter_stats, max_steps)
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