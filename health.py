# health.py

import numpy as np
from config import *


class HealthSystem:
    """
    Tracks HP for every civilian on every floor.
    Key: (floor_idx, row, col)  Value: current HP int
    Firefighter HP is tracked directly on Firefighter objects.
    """

    def __init__(self):
        self.hp = {}

    def register(self, floor, r, c):
        self.hp[(floor, r, c)] = CIVILIAN_MAX_HP

    def remove(self, floor, r, c):
        self.hp.pop((floor, r, c), None)

    def register_all(self, grids):
        self.hp.clear()
        for floor_idx, grid in enumerate(grids):
            for r in range(ROWS):
                for c in range(COLS):
                    if grid[r, c] in (PERSON, PERSON_DANGER):
                        self.register(floor_idx, r, c)

    def get(self, floor, r, c):
        return self.hp.get((floor, r, c), CIVILIAN_MAX_HP)

    def damage(self, floor, r, c, amount=1):
        key = (floor, r, c)
        self.hp[key] = max(0, self.hp.get(key, CIVILIAN_MAX_HP) - amount)
        return self.hp[key]

    def is_dead(self, floor, r, c):
        return self.hp.get((floor, r, c), CIVILIAN_MAX_HP) <= 0

    def move(self, floor, old_r, old_c, new_r, new_c):
        old = (floor, old_r, old_c)
        new = (floor, new_r, new_c)
        if old in self.hp:
            self.hp[new] = self.hp.pop(old)

    def tick_civilian_damage(self, grids):
        """
        Every fire-spread tick civilians adjacent to or standing on fire lose 1 HP.
        Returns list of (floor, r, c) where HP just hit 0.
        """
        newly_dead = []
        for floor_idx, grid in enumerate(grids):
            for r in range(ROWS):
                for c in range(COLS):
                    if grid[r, c] not in (PERSON, PERSON_DANGER):
                        continue
                    # Damage if adjacent to fire OR standing directly on a fire cell
                    # (the latter can happen on the same tick fire spreads into the cell
                    # before the civilian has been processed).
                    in_or_near_fire = any(
                        0 <= nr < ROWS and 0 <= nc < COLS and grid[nr, nc] == FIRE
                        for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1))
                    ) or grid[r, c] == FIRE
                    if in_or_near_fire:
                        hp = self.damage(floor_idx, r, c, 1)
                        if hp <= 0:
                            newly_dead.append((floor_idx, r, c))
        return newly_dead

    def tick_ff_damage(self, firefighters, grids):
        """
        Every fire-spread tick firefighters adjacent to fire take damage.
        If ff.water > 0 — water shields, no HP damage but water drains by
        WATER_FIRE_STEP per adjacent-fire step.
        If ff.water == 0 — takes 1 HP damage as normal.
        FF commits to its path regardless (damage taken but not stopped).
        """
        for ff in firefighters:
            grid = grids[ff.current_floor]
            r, c = ff.pos
            near_fire = any(
                0 <= nr < ROWS and 0 <= nc < COLS and grid[nr, nc] == FIRE
                for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1))
            )
            if not near_fire:
                # Standing directly on fire (no adjacent fire cells)
                if grid[r, c] == FIRE:
                    if ff.water > 0:
                        ff.water = max(0, ff.water - WATER_FIRE_STEP)
                    else:
                        # No water and standing on fire — take HP damage
                        ff.hp = max(0, ff.hp - 1)
                continue

            if ff.water > 0:
                # Water shields HP but drains tank
                ff.water = max(0, ff.water - WATER_FIRE_STEP)
            else:
                # No water — takes HP damage, path continues anyway
                ff.hp = max(0, ff.hp - 1)