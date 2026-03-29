# city_map.py

import numpy as np

ROAD         = 0
BUILDING     = 1
INTERSECTION = 2
FIRE_STATION = 3
HOSPITAL     = 4
RIVER        = 6
BRIDGE       = 7

CITY_COLS  = 42
CITY_ROWS  = 30
BLOCK_SIZE = 6

_BUILDING_PALETTE = [
    (52,52,68),(60,48,48),(48,60,48),(62,58,42),
    (44,56,66),(64,44,58),(54,62,52),(58,54,44),
]
_H_NAMES = ["Main St","Oak Ave","Park Blvd","Elm St","Cedar Rd",
            "Maple Dr","Pine St","Lake Ave","Hill Rd","River St"]
_V_NAMES = ["1st Ave","2nd Ave","3rd Ave","4th Ave","5th Ave",
            "6th Ave","7th Ave","8th Ave","9th Ave","10th Ave"]


def generate_city(seed=None):
    rng = np.random.default_rng(seed)
    grid = np.full((CITY_ROWS, CITY_COLS), BUILDING, dtype=int)

    road_rows = list(range(0, CITY_ROWS, BLOCK_SIZE))
    road_cols = list(range(0, CITY_COLS, BLOCK_SIZE))

    # Extended boundaries include the grid edge so edge blocks are covered
    ext_rows = road_rows + [CITY_ROWS]
    ext_cols = road_cols + [CITY_COLS]

    # Roads and intersections
    for r in road_rows:
        grid[r, :] = ROAD
    for c in road_cols:
        grid[:, c] = ROAD
    for r in road_rows:
        for c in road_cols:
            grid[r, c] = INTERSECTION

    # Road names
    h_name = {r: _H_NAMES[i % len(_H_NAMES)] for i, r in enumerate(road_rows)}
    v_name = {c: _V_NAMES[i % len(_V_NAMES)] for i, c in enumerate(road_cols)}
    road_names = {(r,c): f"{h_name[r]} / {v_name[c]}"
                  for r in road_rows for c in road_cols}

    # Building colours per block (using ext_rows/cols so edge blocks get colors too)
    building_colors = {}
    color_idx = 0
    for bi in range(len(ext_rows) - 1):
        for ci in range(len(ext_cols) - 1):
            col = _BUILDING_PALETTE[color_idx % len(_BUILDING_PALETTE)]
            color_idx += int(rng.integers(1, 4))
            for r in range(ext_rows[bi] + 1, ext_rows[bi + 1]):
                for c in range(ext_cols[ci] + 1, ext_cols[ci + 1]):
                    building_colors[(r, c)] = col

    # River
    mid_rows = [r for r in range(CITY_ROWS // 3, 2 * CITY_ROWS // 3)
                if r not in road_rows]
    river_row = int(rng.choice(mid_rows))
    for c in range(CITY_COLS):
        if grid[river_row, c] in (ROAD, INTERSECTION):
            grid[river_row, c] = BRIDGE
        else:
            grid[river_row, c] = RIVER

    # Fire station on a road cell
    road_cells = [(r, c) for r in range(CITY_ROWS) for c in range(CITY_COLS)
                  if grid[r, c] in (ROAD, INTERSECTION)]
    rng.shuffle(road_cells)
    fire_station_pos = road_cells.pop()
    grid[fire_station_pos] = FIRE_STATION

    # All block indices (including edge blocks)
    all_blocks = [(bi, ci)
                  for bi in range(len(ext_rows) - 1)
                  for ci in range(len(ext_cols) - 1)]

    # Which block contains the fire station?
    fs_r, fs_c = fire_station_pos
    fs_bi = next(i for i in range(len(ext_rows)-1)
                 if ext_rows[i] <= fs_r < ext_rows[i+1])
    fs_ci = next(i for i in range(len(ext_cols)-1)
                 if ext_cols[i] <= fs_c < ext_cols[i+1])

    MIN_DIST = 10  # min block-corner Manhattan distance from fire station

    def block_far_enough(bi, ci):
        r0 = ext_rows[bi]; c0 = ext_cols[ci]
        fs_r0 = ext_rows[fs_bi]; fs_c0 = ext_cols[fs_ci]
        return abs(r0 - fs_r0) + abs(c0 - fs_c0) >= MIN_DIST

    # Hospital blocks: one per horizontal third, far from fire station
    thirds = [[], [], []]
    for bi, ci in all_blocks:
        if (bi, ci) == (fs_bi, fs_ci): continue
        if not block_far_enough(bi, ci): continue
        c0 = ext_cols[ci]
        thirds[min(2, c0 * 3 // CITY_COLS)].append((bi, ci))

    hospital_blocks = []
    for third in thirds:
        if third:
            chosen = third[int(rng.integers(len(third)))]
            hospital_blocks.append(chosen)

    # Fallback if any third was empty
    remaining = [(bi,ci) for bi,ci in all_blocks
                 if (bi,ci) not in hospital_blocks and (bi,ci)!=(fs_bi,fs_ci)]
    while len(hospital_blocks) < 3 and remaining:
        hospital_blocks.append(remaining.pop())

    # Mark hospital block interiors as HOSPITAL in grid
    # hospital_positions = road intersection at top-left corner (passable A* target)
    hospital_positions = []
    for bi, ci in hospital_blocks:
        r0 = ext_rows[bi]; r1 = ext_rows[bi + 1]
        c0 = ext_cols[ci]; c1 = ext_cols[ci + 1]
        for r in range(r0 + 1, r1):
            for c in range(c0 + 1, c1):
                grid[r, c] = HOSPITAL
        # Road target: the intersection at this block's top-left road corner
        # Use actual road_rows/cols (clamped) since ext may include CITY_ROWS/COLS
        road_r = road_rows[min(bi, len(road_rows)-1)]
        road_c = road_cols[min(ci, len(road_cols)-1)]
        hospital_positions.append((road_r, road_c))

    # Block sprites:
    #   -1 = hospital block (drawn as big hospital image)
    #   -2 = fire station block (drawn as big firestation image)
    #   0..N-1 = normal building sprite index
    N_BUILDINGS = 10
    rng2 = np.random.default_rng(42 if seed is None else seed + 1)
    block_sprites = {}
    hosp_set = set(hospital_blocks)
    for bi, ci in all_blocks:
        if (bi, ci) in hosp_set:
            block_sprites[(bi, ci)] = -1
        elif (bi, ci) == (fs_bi, fs_ci):
            block_sprites[(bi, ci)] = -2
        else:
            block_sprites[(bi, ci)] = int(rng2.integers(0, N_BUILDINGS))

    return (grid, fire_station_pos, hospital_positions, hospital_blocks,
            (fs_bi, fs_ci), building_colors, road_names, river_row, block_sprites)


def get_passable():
    # HOSPITAL interior cells are building blocks, not road — not passable
    return {ROAD, INTERSECTION, FIRE_STATION, BRIDGE}