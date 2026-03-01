import numpy as np
from config import *
from planning import astar

# -----------------------------
# AGENT MEMORY
# -----------------------------
carrying_person = False
current_path = []
under_cell = EMPTY


# -----------------------------
# Locate firefighter
# -----------------------------
def find_firefighter(grid):
    pos = np.argwhere(grid == FIREFIGHTER)
    return tuple(pos[0])


# -----------------------------
# Helper: find all cells of type
# -----------------------------
def find_all(grid, value):
    positions = np.argwhere(grid == value)
    return [tuple(p) for p in positions]


# -----------------------------
# Choose nearest target
# -----------------------------
def nearest_target(grid, start):

    # Priority 1: people in danger
    danger_people = find_all(grid, PERSON_DANGER)

    if danger_people:
        targets = danger_people
    else:
        targets = find_all(grid, PERSON)

    if not targets:
        return None

    # choose closest using Manhattan distance
    distances = [
        abs(start[0]-t[0]) + abs(start[1]-t[1])
        for t in targets
    ]

    return targets[np.argmin(distances)]


# -----------------------------
# Move firefighter intelligently
# -----------------------------
def move_firefighter(grid):

    global carrying_person, current_path, under_cell

    new_grid = grid.copy()

    fr, fc = find_firefighter(grid)

    # restore previous tile
    new_grid[fr, fc] = under_cell

    # ---------------- Decide Goal ----------------
    if not carrying_person:
        target = nearest_target(grid, (fr, fc))
        if target is None:
            return grid

        if not current_path:
            current_path = astar(grid, (fr, fc), target)

    else:
        shelters = find_all(grid, SHELTER)
        if not shelters:
            return grid

        target = shelters[0]

        if not current_path:
            current_path = astar(grid, (fr, fc), target)

    # ---------------- Follow Path ----------------
    if not current_path:
        return grid

    nr, nc = current_path.pop(0)

    destination_cell = grid[nr, nc]

    # pickup
    if destination_cell in [PERSON, PERSON_DANGER]:
        carrying_person = True
        print("🚒 Picked up person!")
        destination_cell = EMPTY

    # deliver
    if destination_cell == SHELTER and carrying_person:
        carrying_person = False
        print("✅ Person delivered!")

    # remember underlying tile
    under_cell = destination_cell

    # move firefighter
    new_grid[nr, nc] = FIREFIGHTER

    return new_grid