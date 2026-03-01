# fire.py

import numpy as np
from config import *

def spread_fire(grid, step):

    new_grid = grid.copy()

    # fire spreads every 4 frames
    if step % 4 != 0:
        return new_grid

    for r in range(ROWS):
        for c in range(COLS):

            if grid[r, c] == FIRE:

                neighbors = [
                    (r+1,c),(r-1,c),
                    (r,c+1),(r,c-1)
                ]

                for nr, nc in neighbors:

                    if 0 <= nr < ROWS and 0 <= nc < COLS:

                        cell = grid[nr, nc]

                        # 🔥 spread fire
                        if cell in [EMPTY, PERSON, PERSON_DANGER, SHELTER]:
                            if np.random.rand() < 0.12:
                                new_grid[nr, nc] = FIRE

                        # 🟣 mark nearby person as danger
                        if cell == PERSON:
                            new_grid[nr, nc] = PERSON_DANGER

    return new_grid