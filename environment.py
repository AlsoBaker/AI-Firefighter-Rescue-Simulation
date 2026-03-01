# environment.py

import numpy as np
from config import *

def create_environment():

    grid = np.zeros((ROWS, COLS))

    # ---------------- Obstacles ----------------
    for _ in range(45):
        r = np.random.randint(ROWS)
        c = np.random.randint(COLS)

        if grid[r, c] == EMPTY:
            grid[r, c] = OBSTACLE

    # ---------------- People ----------------
    for _ in range(10):
        r = np.random.randint(ROWS)
        c = np.random.randint(COLS)

        if grid[r, c] == EMPTY:
            grid[r, c] = PERSON

    # ---------------- Shelters ----------------
    for _ in range(3):
        r = np.random.randint(ROWS)
        c = np.random.randint(COLS)

        if grid[r, c] == EMPTY:
            grid[r, c] = SHELTER

    # ---------------- Multiple Fire Sources ----------------
    for _ in range(4):
        r = np.random.randint(ROWS)
        c = np.random.randint(COLS)

        if grid[r, c] == EMPTY:
            grid[r, c] = FIRE

    return grid