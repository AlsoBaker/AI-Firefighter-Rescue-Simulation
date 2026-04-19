# city_map.py

import numpy as np
from collections import deque

ROAD         = 0
BUILDING     = 1
INTERSECTION = 2
FIRE_STATION = 3
HOSPITAL     = 4
ROAD_CLOSURE = 5   # impassable road segment (barrier / construction)
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

# Traffic-light timing constants (frames at 60 FPS)
TL_CYCLE  = 60  # total frames per full cycle
TL_GREEN  = 30   # frames spent green; red = TL_CYCLE - TL_GREEN = 30


# ── Connectivity check (inline BFS — avoids circular imports) ─────────────────

def _connected(grid, start, goal, passable):
    """Return True if goal is reachable from start via passable cells."""
    if start == goal:
        return True
    visited = {start}
    q = deque([start])
    while q:
        r, c = q.popleft()
        for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
            if (0 <= nr < CITY_ROWS and 0 <= nc < CITY_COLS
                    and (nr, nc) not in visited
                    and grid[nr, nc] in passable):
                if (nr, nc) == goal:
                    return True
                visited.add((nr, nc))
                q.append((nr, nc))
    return False


def generate_city(seed=None):
    rng = np.random.default_rng(seed)
    grid = np.full((CITY_ROWS, CITY_COLS), BUILDING, dtype=int)

    road_rows = list(range(0, CITY_ROWS, BLOCK_SIZE))
    road_cols = list(range(0, CITY_COLS, BLOCK_SIZE))

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

    # Building colours per block
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

    # Fire station
    road_cells = [(r, c) for r in range(CITY_ROWS) for c in range(CITY_COLS)
                  if grid[r, c] in (ROAD, INTERSECTION)]
    rng.shuffle(road_cells)
    fire_station_pos = road_cells.pop()
    grid[fire_station_pos] = FIRE_STATION

    # Block indices
    all_blocks = [(bi, ci)
                  for bi in range(len(ext_rows) - 1)
                  for ci in range(len(ext_cols) - 1)]

    fs_r, fs_c = fire_station_pos
    fs_bi = next(i for i in range(len(ext_rows)-1)
                 if ext_rows[i] <= fs_r < ext_rows[i+1])
    fs_ci = next(i for i in range(len(ext_cols)-1)
                 if ext_cols[i] <= fs_c < ext_cols[i+1])

    MIN_DIST = 10

    def block_far_enough(bi, ci):
        r0 = ext_rows[bi]; c0 = ext_cols[ci]
        fs_r0 = ext_rows[fs_bi]; fs_c0 = ext_cols[fs_ci]
        return abs(r0 - fs_r0) + abs(c0 - fs_c0) >= MIN_DIST

    # Hospital blocks
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

    remaining = [(bi,ci) for bi,ci in all_blocks
                 if (bi,ci) not in hospital_blocks and (bi,ci)!=(fs_bi,fs_ci)]
    while len(hospital_blocks) < 3 and remaining:
        hospital_blocks.append(remaining.pop())

    # Mark hospital interiors + record road targets
    hospital_positions = []
    for bi, ci in hospital_blocks:
        r0 = ext_rows[bi]; r1 = ext_rows[bi + 1]
        c0 = ext_cols[ci]; c1 = ext_cols[ci + 1]
        for r in range(r0 + 1, r1):
            for c in range(c0 + 1, c1):
                grid[r, c] = HOSPITAL
        road_r = road_rows[min(bi, len(road_rows)-1)]
        road_c = road_cols[min(ci, len(road_cols)-1)]
        hospital_positions.append((road_r, road_c))

    # Block sprites
    N_BUILDINGS = 10
    rng2 = np.random.default_rng(42 if seed is None else seed + 1)
    block_sprites = {}
    hosp_set = set(map(tuple, hospital_blocks))
    for bi, ci in all_blocks:
        if (bi, ci) in hosp_set:
            block_sprites[(bi, ci)] = -1
        elif (bi, ci) == (fs_bi, fs_ci):
            block_sprites[(bi, ci)] = -2
        else:
            block_sprites[(bi, ci)] = int(rng2.integers(0, N_BUILDINGS))

    # ── Road closures (3 random road-only segments, connectivity verified) ────
    passable_set = get_passable()
    forbidden    = {fire_station_pos} | set(map(tuple, hospital_positions))
    # Only ROAD cells (not intersections) that aren't fire station / hospital road
    road_only = [(r, c) for r in range(CITY_ROWS) for c in range(CITY_COLS)
                 if grid[r, c] == ROAD and (r, c) not in forbidden]
    rng.shuffle(road_only)

    closures_placed = []
    for candidate in road_only:
        if len(closures_placed) >= 3:
            break
        # Temporarily mark as closure and verify all hospitals still reachable
        grid[candidate] = ROAD_CLOSURE
        still_connected = all(
            _connected(grid, fire_station_pos, h, passable_set)
            for h in hospital_positions
        )
        if still_connected:
            closures_placed.append(candidate)
        else:
            grid[candidate] = ROAD   # revert — would disconnect

    # ── Traffic lights at alternating intersections (checkerboard) ───────────
    # Each light: (row, col, phase_offset_frames)
    traffic_lights = []
    for i, r in enumerate(road_rows):
        for j, c in enumerate(road_cols):
            if (i + j) % 2 == 0:
                phase = (i * 7 + j * 13) % TL_CYCLE
                traffic_lights.append((r, c, phase))

    return (grid, fire_station_pos, hospital_positions, hospital_blocks,
            (fs_bi, fs_ci), building_colors, road_names, river_row,
            block_sprites, traffic_lights)


def get_passable():
    # ROAD_CLOSURE is intentionally excluded — treated as wall
    return {ROAD, INTERSECTION, FIRE_STATION, BRIDGE}
