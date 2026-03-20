# city_map.py

import numpy as np

# ── Cell types ────────────────────────────────────────────────────────────────
ROAD         = 0
BUILDING     = 1
INTERSECTION = 2
FIRE_STATION = 3
HOSPITAL     = 4
PARK         = 5
RIVER        = 6
BRIDGE       = 7

CITY_COLS  = 42
CITY_ROWS  = 30
BLOCK_SIZE = 6

_BUILDING_PALETTE = [
    (52, 52, 68), (60, 48, 48), (48, 60, 48), (62, 58, 42),
    (44, 56, 66), (64, 44, 58), (54, 62, 52), (58, 54, 44),
]

_H_NAMES = ["Main St","Oak Ave","Park Blvd","Elm St","Cedar Rd","Maple Dr","Pine St","Lake Ave","Hill Rd","River St"]
_V_NAMES = ["1st Ave","2nd Ave","3rd Ave","4th Ave","5th Ave","6th Ave","7th Ave","8th Ave","9th Ave","10th Ave"]


def generate_city(seed=None):
    rng = np.random.default_rng(seed)
    grid = np.full((CITY_ROWS, CITY_COLS), BUILDING, dtype=int)

    road_rows = list(range(0, CITY_ROWS, BLOCK_SIZE))
    road_cols = list(range(0, CITY_COLS, BLOCK_SIZE))

    for r in road_rows:
        grid[r, :] = ROAD
    for c in road_cols:
        grid[:, c] = ROAD
    for r in road_rows:
        for c in road_cols:
            grid[r, c] = INTERSECTION

    # Road names at intersections
    h_name = {r: _H_NAMES[i % len(_H_NAMES)] for i, r in enumerate(road_rows)}
    v_name = {c: _V_NAMES[i % len(_V_NAMES)] for i, c in enumerate(road_cols)}
    road_names = {(r, c): f"{h_name[r]} / {v_name[c]}"
                  for r in road_rows for c in road_cols}

    # Building colours per block
    building_colors = {}
    color_idx = 0
    for bi, r0 in enumerate(road_rows[:-1]):
        r_end = road_rows[bi + 1]
        for ci, c0 in enumerate(road_cols[:-1]):
            c_end = road_cols[ci + 1]
            col = _BUILDING_PALETTE[color_idx % len(_BUILDING_PALETTE)]
            color_idx += int(rng.integers(1, 4))
            for r in range(r0 + 1, r_end):
                for c in range(c0 + 1, c_end):
                    building_colors[(r, c)] = col

    # Parks: replace 2-3 building blocks
    block_list = [
        (r0 + 1, c0 + 1, road_rows[bi + 1], road_cols[ci + 1])
        for bi, r0 in enumerate(road_rows[:-1])
        for ci, c0 in enumerate(road_cols[:-1])
    ]
    rng.shuffle(block_list)
    for r_start, c_start, r_end, c_end in block_list[:int(rng.integers(2, 4))]:
        for r in range(r_start, r_end):
            for c in range(c_start, c_end):
                grid[r, c] = PARK

    # River: one horizontal row with bridges at road columns
    mid_rows = [r for r in range(CITY_ROWS // 3, 2 * CITY_ROWS // 3)
                if r not in road_rows]
    river_row = int(rng.choice(mid_rows))
    for c in range(CITY_COLS):
        if grid[river_row, c] in (ROAD, INTERSECTION):
            grid[river_row, c] = BRIDGE
        else:
            grid[river_row, c] = RIVER

    # Passable cells for placement
    road_cells = [(r, c) for r in range(CITY_ROWS) for c in range(CITY_COLS)
                  if grid[r, c] in (ROAD, INTERSECTION)]
    rng.shuffle(road_cells)

    fire_station_pos = road_cells.pop()
    grid[fire_station_pos] = FIRE_STATION

    # Minimum Manhattan distance between fire station and any hospital
    MIN_DIST = 10

    def far_enough(pos):
        return (abs(pos[0] - fire_station_pos[0]) +
                abs(pos[1] - fire_station_pos[1])) >= MIN_DIST

    thirds = [[], [], []]
    for r, c in road_cells:
        if far_enough((r, c)):
            thirds[min(2, c * 3 // CITY_COLS)].append((r, c))

    hospital_positions = []
    for third in thirds:
        if third:
            pos = third[int(rng.integers(len(third)))]
            grid[pos] = HOSPITAL
            hospital_positions.append(pos)
    # Fallback: relax distance constraint if not enough hospitals placed
    fallback = [p for p in road_cells if p not in hospital_positions]
    while len(hospital_positions) < 3 and fallback:
        pos = fallback.pop()
        grid[pos] = HOSPITAL
        hospital_positions.append(pos)

    return grid, fire_station_pos, hospital_positions, building_colors, road_names, river_row


def get_passable():
    return {ROAD, INTERSECTION, FIRE_STATION, HOSPITAL, BRIDGE}