# environment.py

import numpy as np
from config import *


def _place_staircases(grid):
    """Stamp fixed-edge staircases onto any floor grid."""
    for r in (STAIR_ROW_START, STAIR_ROW_END):
        grid[r, STAIR_UP_COL]   = STAIRCASE
        grid[r, STAIR_DOWN_COL] = STAIRCASE
    return grid


def create_floor(floor_num):
    """
    Generate one floor grid.
    Floor 0 = most fire / most people (ground floor, most danger)
    Floor 1 = medium
    Floor 2 = least fire / fewest people (top floor, easiest to reach)
    """
    grid = np.zeros((ROWS, COLS), dtype=int)

    # Obstacles — fewer on higher floors
    n_obstacles = max(20, 40 - floor_num * 8)
    for _ in range(n_obstacles):
        r = np.random.randint(1, ROWS - 1)
        c = np.random.randint(1, COLS - 1)
        if grid[r, c] == EMPTY:
            grid[r, c] = OBSTACLE

    # People — more on lower floors (harder to reach first)
    # Exclude staircase rows so people are never silently overwritten
    safe_rows = [r for r in range(ROWS)
                 if r not in (STAIR_ROW_START, STAIR_ROW_END)]
    n_people = [10, 8, 6][floor_num]
    for _ in range(n_people):
        r = safe_rows[np.random.randint(len(safe_rows))]
        c = np.random.randint(COLS)
        if grid[r, c] == EMPTY:
            grid[r, c] = PERSON

    # Hospital (2 per floor — replaces SHELTER)
    for _ in range(2):
        r = safe_rows[np.random.randint(len(safe_rows))]
        c = np.random.randint(COLS)
        if grid[r, c] == EMPTY:
            grid[r, c] = HOSPITAL

    # Fire — maximum on floor 0, minimum on floor 2
    n_fire = [5, 1, 1][floor_num]
    for _ in range(n_fire):
        r = np.random.randint(ROWS)
        c = np.random.randint(COLS)
        if grid[r, c] == EMPTY:
            grid[r, c] = FIRE

    # Staircases always placed last so they override anything
    grid = _place_staircases(grid)

    return grid


def create_all_floors():
    return [create_floor(i) for i in range(NUM_FLOORS)]


# ---------- backward compat ----------
def create_environment():
    return create_floor(0)
