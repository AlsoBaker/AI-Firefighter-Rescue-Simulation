# floors.py

import numpy as np
from config import *


class FloorManager:
    """
    Owns the list of per-floor grids and handles staircase switching.
    Left-edge staircase  (col 0)        -> go UP   (+1 floor)
    Right-edge staircase (col COLS-1)   -> go DOWN (-1 floor)
    Staircase spans rows STAIR_ROW_START and STAIR_ROW_END.
    """

    def __init__(self, grids):
        self.grids = grids
        self.num_floors = len(grids)

    # ------------------------------------------------------------------
    # Grid access
    # ------------------------------------------------------------------

    def get_grid(self, floor_idx):
        return self.grids[floor_idx]

    def set_grid(self, floor_idx, grid):
        self.grids[floor_idx] = grid

    # ------------------------------------------------------------------
    # Staircase helpers
    # ------------------------------------------------------------------

    def is_staircase(self, r, c):
        return (STAIR_ROW_START <= r <= STAIR_ROW_END and
                c in (STAIR_UP_COL, STAIR_DOWN_COL))

    def stair_direction(self, r, c):
        """Returns +1 (up), -1 (down), or 0 (not a staircase)."""
        if STAIR_ROW_START <= r <= STAIR_ROW_END:
            if c == STAIR_UP_COL:
                return +1
            if c == STAIR_DOWN_COL:
                return -1
        return 0

    def switch_floor(self, ff, direction):
        """
        Teleport firefighter to adjacent floor via matching staircase.
        Returns True if the switch was successful.
        """
        new_floor = ff.current_floor + direction
        if not (0 <= new_floor < self.num_floors):
            return False

        # Arrive at the same staircase column on new floor
        arrival_col = STAIR_UP_COL if direction == +1 else STAIR_DOWN_COL
        ff.current_floor = new_floor
        ff.pos = (STAIR_ROW_START, arrival_col)
        ff.under_cell = STAIRCASE
        ff.current_path = []
        return True

    # ------------------------------------------------------------------
    # Cross-floor targeting helpers
    # ------------------------------------------------------------------

    def people_count(self, floor_idx):
        g = self.grids[floor_idx]
        return int(np.sum(g == PERSON)) + int(np.sum(g == PERSON_DANGER))

    def danger_count(self, floor_idx):
        return int(np.sum(self.grids[floor_idx] == PERSON_DANGER))

    def best_floor_to_visit(self, current_floor):
        """
        Return (floor_idx, count) of the floor (excluding current)
        with the most people, weighted by danger.
        Returns (None, 0) if no other floor has people.
        """
        best_floor, best_score = None, 0
        for f in range(self.num_floors):
            if f == current_floor:
                continue
            score = self.danger_count(f) * 2 + self.people_count(f)
            if score > best_score:
                best_score = score
                best_floor = f
        return best_floor, best_score

    def staircase_toward(self, current_floor, target_floor):
        """Return the staircase column that moves toward target_floor."""
        direction = +1 if target_floor > current_floor else -1
        return STAIR_UP_COL if direction == +1 else STAIR_DOWN_COL
