# floors.py

import numpy as np
from config import *


class FloorManager:
    """
    Owns the list of per-floor grids and handles staircase switching.
    Both staircases (col 0 and col COLS-1) can go UP or DOWN — direction
    is determined by ff.stair_intent set before the FF steps onto the cell.
    Firefighters always use the nearest staircase cell (closest of all 4).
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
        """
        Returns whether (r, c) is a staircase cell: +1 or -1 (either is valid,
        since both staircases go both directions). Returns 0 if not a staircase.
        The actual travel direction is stored on ff.stair_intent, set before
        the FF steps onto the cell.
        """
        if STAIR_ROW_START <= r <= STAIR_ROW_END:
            if c in (STAIR_UP_COL, STAIR_DOWN_COL):
                return 1   # non-zero = is a staircase; direction comes from ff.stair_intent
        return 0

    def switch_floor(self, ff, direction):
        """
        Teleport firefighter to the adjacent floor in the given direction,
        arriving at the same staircase column they used (both cols serve both
        directions). Tries STAIR_ROW_START first; falls back to STAIR_ROW_END.
        Returns True if the switch was successful.
        """
        new_floor = ff.current_floor + direction
        if not (0 <= new_floor < self.num_floors):
            return False

        # Arrive at the same column the FF used — both staircases go both ways
        arrival_col = ff.pos[1]
        new_grid    = self.grids[new_floor]

        origin_floor = ff.current_floor

        for arrival_row in (STAIR_ROW_START, STAIR_ROW_END):
            cell = int(new_grid[arrival_row, arrival_col])
            # Only arrive on a bare staircase cell — if another FF is occupying it,
            # wait rather than stacking two FFs on the same cell.
            if cell == STAIRCASE:
                ff._prev_floor        = origin_floor
                ff._prev_floor_ticks  = 0
                ff.current_floor      = new_floor
                ff.pos                = (arrival_row, arrival_col)
                ff.under_cell         = STAIRCASE
                ff.current_path       = []
                return True

        # Both staircase cells occupied — wait on current floor
        return False

    # ------------------------------------------------------------------
    # Cross-floor targeting helpers
    # ------------------------------------------------------------------

    def people_count(self, floor_idx):
        g = self.grids[floor_idx]
        return int(np.sum(g == PERSON)) + int(np.sum(g == PERSON_DANGER))

    def danger_count(self, floor_idx):
        return int(np.sum(self.grids[floor_idx] == PERSON_DANGER))

    def best_floor_to_visit(self, current_floor, exclude_floor=-1):
        """
        Return (floor_idx, score) of the best floor to visit next.

        exclude_floor: skip this floor index (used to prevent a FF from
        immediately switching back to the floor it just came from).

        Preference order:
          1. Adjacent floor (|distance| == 1) with people — pick highest score.
          2. Non-adjacent floor — only if NO adjacent floor has people at all.

        Returns (None, 0) if no other floor has people.
        """
        adjacent, non_adjacent = [], []
        for f in range(self.num_floors):
            if f == current_floor:
                continue
            if f == exclude_floor:
                continue
            score = self.danger_count(f) * 2 + self.people_count(f)
            if score <= 0:
                continue
            if abs(f - current_floor) == 1:
                adjacent.append((score, f))
            else:
                non_adjacent.append((score, f))

        # Prefer adjacent floors; fall back to non-adjacent only when adjacent
        # floors are empty of people.
        pool = adjacent if adjacent else non_adjacent
        if not pool:
            return None, 0
        best_score, best_floor = max(pool)
        return best_floor, best_score

    def nearest_staircase(self, ff_pos):
        """
        Return the staircase cell (row, col) closest to ff_pos by Manhattan
        distance, choosing from all 4 staircase cells:
          (STAIR_ROW_START, STAIR_UP_COL), (STAIR_ROW_END, STAIR_UP_COL),
          (STAIR_ROW_START, STAIR_DOWN_COL), (STAIR_ROW_END, STAIR_DOWN_COL)
        Both columns serve both directions.
        """
        r, c = ff_pos
        candidates = [
            (STAIR_ROW_START, STAIR_UP_COL),
            (STAIR_ROW_END,   STAIR_UP_COL),
            (STAIR_ROW_START, STAIR_DOWN_COL),
            (STAIR_ROW_END,   STAIR_DOWN_COL),
        ]
        return min(candidates, key=lambda cell: abs(cell[0] - r) + abs(cell[1] - c))