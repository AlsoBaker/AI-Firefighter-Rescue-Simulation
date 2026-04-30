# metrics.py

import numpy as np
from config import *

# ── Score component ceilings ──────────────────────────────────────────────────
# Sum of all positive ceilings = 1800, so a perfect run hits 2000 after min()
_CAP_BASE        = 900   # rescue² × 900  — perfect rescue = exactly 900
_CAP_ZERO_BURN   = 150   # zero-burn bonus — full 150 at burn=0, zero at burn≥25%
_CAP_SPEED       = 350   # power-curve speed bonus
_CAP_FIRE        = 250   # fire-control bonus
_CAP_EXTINGUISH  = 150   # active firefighting bonus (30 fires = max)
_REALISTIC_FIRE  = 120   # avg fire cells in a "bad" run — denominator for fire bonus


class SimulationMetrics:

    def __init__(self):
        self.reset()

    def reset(self):
        self.steps              = 0
        self.people_rescued     = 0
        self.people_burned      = 0
        self.max_fire_spread    = 0
        self.fires_extinguished = 0

        self.fire_history          = []
        self.people_safe_history   = []
        self.people_danger_history = []
        self.rescue_history        = []
        self.ff_hp_history         = []   # avg FF HP over time

        self.initial_people_count = 0
        self._prev_total_alive    = 0
        self.current_phase        = 'outbreak'

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

        # Live burned tracking — include carried civilians (off-grid but not yet rescued)
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
        Score out of 2000.  A flawless run (100% rescued, 0 burns, fast,
        low fire, lots extinguished) yields exactly 2000.

        Component ceilings (sum = 1800; penalty can reduce to 0 minimum):
        ─────────────────────────────────────────────────────────────────
        base          (0 – 900)  rescue_ratio² × 900
                                 Quadratic — perfect = 900, partial rescues
                                 penalised more steeply than a linear scale.

        zero_burn     (0 – 150)  Full 150 when burns = 0; fades linearly to 0
                                 once burn_ratio ≥ 25%.  Cliff reward for
                                 keeping every civilian alive.

        speed         (0 – 350)  (1 − steps_ratio)^0.7 × 350
                                 Power curve: generous for early finish,
                                 normalised to max_steps so it cannot be
                                 gamed by setting a huge step budget.

        fire          (0 – 250)  (1 − avg_fire / 120) × 250
                                 Denominator is 120 (realistic "bad-run" avg),
                                 not the full grid (1200), so this component
                                 actually spans its range in practice.

        extinguish    (0 – 150)  fires_extinguished × 5, capped at 150.
                                 Maxes out at 30 extinguishes — achievable
                                 by a 4-FF team without being trivial.

        penalty       subtracted  burn_ratio² × 250 + burn_ratio × 100
                                 Progressive: first burns are cheap; losing
                                 many civilians is punished heavily.
        """
        if total_people == 0:
            return 2000.0

        rescue_ratio = min(1.0, self.people_rescued / total_people)
        burn_ratio   = min(1.0, self.people_burned / total_people)
        steps_ratio  = min(1.0, self.steps / max(1, max_steps))
        avg_fire     = float(np.mean(self.fire_history)) if self.fire_history else 0.0

        # ── Positive components ───────────────────────────────────────────────

        # Base: quadratic curve — 100% rescue → exactly 900
        base = rescue_ratio * rescue_ratio * _CAP_BASE

        # Zero-burn bonus: cliff reward — full 150 at burn=0, zero at burn≥25%
        zero_burn = max(0.0, (1.0 - burn_ratio / 0.25) * _CAP_ZERO_BURN)

        # Speed bonus: power curve normalised to configured step budget
        speed = max(0.0, (1.0 - steps_ratio) ** 0.7) * _CAP_SPEED

        # Fire bonus: realistic denominator (not the full grid size)
        fire = max(0.0, (1.0 - avg_fire / _REALISTIC_FIRE) * _CAP_FIRE)

        # Extinguish bonus: 5 pts per fire extinguished, cap at 150
        extinguish = min(float(_CAP_EXTINGUISH), self.fires_extinguished * 5.0)

        # ── Penalty ──────────────────────────────────────────────────────────
        # Progressive: escalates faster as burn ratio grows
        penalty = burn_ratio * burn_ratio * 250.0 + burn_ratio * 100.0

        total = base + zero_burn + speed + fire + extinguish - penalty
        return min(2000.0, max(0.0, total))

    def get_summary(self, total_people, firefighter_stats, max_steps=300):
        return {
            'total_steps':          self.steps,
            'people_rescued':       self.people_rescued,
            'people_burned':        self.people_burned,
            'rescue_percentage':    (self.people_rescued / total_people * 100)
                                    if total_people > 0 else 0,
            'max_fire_cells':       self.max_fire_spread,
            'fires_extinguished':   self.fires_extinguished,
            'avg_people_in_danger': (np.mean(self.people_danger_history)
                                     if self.people_danger_history else 0),
            'final_score':          self.calculate_score(total_people, max_steps),
            'firefighter_stats':    firefighter_stats,
            'phase':                self.current_phase,
        }

    def print_report(self, total_people, firefighter_stats, max_steps=300):
        s = self.get_summary(total_people, firefighter_stats, max_steps)
        print("\n" + "=" * 60)
        print("SIMULATION FINAL REPORT")
        print("=" * 60)
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
        print("=" * 60 + "\n")
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