# fire.py

import numpy as np
from config import *

# Cells that fire cannot spread to
_FIRE_IMMUNE = {OBSTACLE, FIREFIGHTER, STAIRCASE, HOSPITAL}

# Spread probability per floor — floor 0 burns fast, upper floors burn slower
_SPREAD_PROB = [0.20, 0.16, 0.12]


def spread_fire(grid, step, floor_idx=0):
    """
    Spread fire on a single floor grid.
    floor_idx controls spread probability:
      Floor 0 (ground): 14% — maximum danger
      Floor 1         :  10% — medium
      Floor 2 (top)   :  7% — slow
    """
    new_grid = grid.copy()

    if step % 4 != 0:
        return new_grid

    prob = _SPREAD_PROB[min(floor_idx, len(_SPREAD_PROB) - 1)]

    for r in range(ROWS):
        for c in range(COLS):
            if grid[r, c] != FIRE:
                continue

            for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
                if not (0 <= nr < ROWS and 0 <= nc < COLS):
                    continue

                cell = grid[nr, nc]

                if cell in _FIRE_IMMUNE:
                    continue

                # Step 1: mark person as in danger (visual warning)
                if cell == PERSON:
                    new_grid[nr, nc] = PERSON_DANGER

                # Step 2: probabilistic spread to empty / already-danger cells
                elif cell in (EMPTY, PERSON_DANGER):
                    if np.random.rand() < prob:
                        new_grid[nr, nc] = FIRE

    return new_grid