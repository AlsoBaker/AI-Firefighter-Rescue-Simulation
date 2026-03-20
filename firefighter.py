# firefighter.py

import numpy as np
from config import *
from planning import astar, bfs, dijkstra


class Firefighter:
    def __init__(self, start_pos, floor=0):
        self.pos             = start_pos
        self.current_floor   = floor
        self.hp              = FF_MAX_HP
        self.water           = WATER_MAX
        self.carrying_person = False
        self.current_path    = []
        self.under_cell      = EMPTY
        self.people_rescued  = 0
        self.stuck_counter   = 0

    def is_alive(self):
        return self.hp > 0

    def reset_path(self):
        self.current_path = []

    def recalculate_if_blocked(self, grid):
        """
        Scan entire path for obstacles.
        Fire cells only block if water == 0.
        """
        for pos in self.current_path:
            r, c = pos
            cell = grid[r, c]
            if cell == OBSTACLE:
                self.reset_path()
                self.stuck_counter += 1
                return
            if cell == FIRE and self.water <= 0:
                self.reset_path()
                self.stuck_counter += 1
                return


class FirefighterManager:

    def __init__(self, num_firefighters=1, algorithm="astar"):
        self.firefighters     = []
        self.num_firefighters = num_firefighters
        self.algorithm        = algorithm
        self.floor_manager    = None

    def set_floor_manager(self, fm):
        self.floor_manager = fm

    # ----------------------------------------------------------
    # Pathfinding — passes allow_fire based on water level
    # ----------------------------------------------------------

    def find_path(self, grid, start, goal, water=0):
        allow_fire = water > 0
        if self.algorithm == "astar":
            return astar(grid, start, goal, allow_fire=allow_fire)
        elif self.algorithm == "bfs":
            return bfs(grid, start, goal, allow_fire=allow_fire)
        elif self.algorithm == "dijkstra":
            return dijkstra(grid, start, goal, allow_fire=allow_fire)
        return astar(grid, start, goal, allow_fire=allow_fire)

    # ----------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------

    def _find_nearest_empty(self, grid, pos, max_radius=6):
        r, c = pos
        for radius in range(max_radius + 1):
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS and grid[nr, nc] == EMPTY:
                        return (nr, nc)
        return None

    def initialize(self, grids):
        self.firefighters = []
        spawn_positions = [
            (0, 0),              (0, COLS-1),
            (ROWS-1, 0),         (ROWS-1, COLS-1),
            (0, COLS//2),        (ROWS-1, COLS//2),
            (ROWS//4, COLS//2),  (ROWS*3//4, COLS//2),
        ]
        grid = grids[0]
        for i in range(min(self.num_firefighters, len(spawn_positions))):
            r, c  = spawn_positions[i]
            spawn = (r, c) if grid[r, c] == EMPTY else self._find_nearest_empty(grid, (r, c))
            if spawn:
                ff = Firefighter(spawn, floor=0)
                self.firefighters.append(ff)
                grid[spawn] = FIREFIGHTER
        return grids

    # ----------------------------------------------------------
    # Targeting
    # ----------------------------------------------------------

    def _find_person_target(self, grid, start_pos, claimed):
        danger = [tuple(p) for p in np.argwhere(grid == PERSON_DANGER) if tuple(p) not in claimed]
        safe   = [tuple(p) for p in np.argwhere(grid == PERSON)        if tuple(p) not in claimed]
        targets = danger if danger else safe
        if not targets:
            return None
        return min(targets, key=lambda t: abs(start_pos[0]-t[0]) + abs(start_pos[1]-t[1]))

    def _find_hospital(self, grid, start_pos):
        hospitals = [tuple(p) for p in np.argwhere(grid == HOSPITAL)]
        if not hospitals:
            return None
        return min(hospitals, key=lambda h: abs(start_pos[0]-h[0]) + abs(start_pos[1]-h[1]))

    def _staircase_target(self, col):
        return (STAIR_ROW_START, col)

    # ----------------------------------------------------------
    # Water drain while standing on fire
    # ----------------------------------------------------------

    def _drain_water_on_fire(self, ff, grid):
        r, c = ff.pos
        if grid[r, c] == FIRE and ff.water > 0:
            ff.water = max(0, ff.water - WATER_FIRE_STEP)

    # ----------------------------------------------------------
    # Main move loop
    # ----------------------------------------------------------

    def move_all(self, grids):
        self.firefighters = [ff for ff in self.firefighters if ff.is_alive()]

        # Clear all FF cells
        for ff in self.firefighters:
            grids[ff.current_floor][ff.pos] = ff.under_cell

        claimed = {}

        for ff in self.firefighters:
            floor_idx    = ff.current_floor
            grid         = grids[floor_idx]
            floor_claimed = claimed.setdefault(floor_idx, set())

            ff.recalculate_if_blocked(grid)

            # ---- DECIDE GOAL ----
            if not ff.carrying_person:
                target = self._find_person_target(grid, ff.pos, floor_claimed)

                if target is None and self.floor_manager:
                    best_floor, count = self.floor_manager.best_floor_to_visit(floor_idx)
                    if best_floor is not None and count > 0:
                        stair_col = self.floor_manager.staircase_toward(floor_idx, best_floor)
                        target    = self._staircase_target(stair_col)

                if target is None:
                    grids[floor_idx][ff.pos] = FIREFIGHTER
                    continue

                floor_claimed.add(target)
                if not ff.current_path:
                    ff.current_path = self.find_path(grid, ff.pos, target, water=ff.water)

            else:
                target = self._find_hospital(grid, ff.pos)

                if target is None and self.floor_manager and floor_idx > 0:
                    target = self._staircase_target(STAIR_DOWN_COL)

                if target is None:
                    grids[floor_idx][ff.pos] = FIREFIGHTER
                    continue

                if not ff.current_path:
                    ff.current_path = self.find_path(grid, ff.pos, target, water=ff.water)

            # ---- FOLLOW PATH ----
            if not ff.current_path:
                grids[floor_idx][ff.pos] = FIREFIGHTER
                continue

            next_pos = ff.current_path.pop(0)
            nr, nc   = next_pos

            if grid[nr, nc] == FIREFIGHTER:
                ff.current_path = []
                grids[floor_idx][ff.pos] = FIREFIGHTER
                continue

            dest_cell = grid[nr, nc]

            # ---- Moving onto fire: drain water, take damage if empty ----
            if dest_cell == FIRE:
                if ff.water > 0:
                    ff.water = max(0, ff.water - WATER_FIRE_STEP)
                else:
                    ff.hp = max(0, ff.hp - 1)

            # ---- STAIRCASE ----
            if dest_cell == STAIRCASE and self.floor_manager:
                direction = self.floor_manager.stair_direction(nr, nc)
                if direction != 0:
                    grids[floor_idx][ff.pos] = ff.under_cell
                    switched = self.floor_manager.switch_floor(ff, direction)
                    if switched:
                        grids[ff.current_floor][ff.pos] = FIREFIGHTER
                    else:
                        grids[floor_idx][ff.pos] = FIREFIGHTER
                    continue

            # ---- PICKUP ----
            if dest_cell in (PERSON, PERSON_DANGER):
                ff.carrying_person = True
                print(f"  FF picked up person on floor {floor_idx + 1}!")
                dest_cell = EMPTY

            # ---- DELIVER ----
            elif dest_cell == HOSPITAL and ff.carrying_person:
                ff.carrying_person  = False
                ff.people_rescued  += 1
                ff.water            = min(WATER_MAX, ff.water + WATER_REFILL)
                print(f"  Delivered! Floor {floor_idx+1} | rescued={ff.people_rescued} | water={ff.water}")
                dest_cell = HOSPITAL

            ff.under_cell = dest_cell
            ff.pos        = next_pos
            grids[floor_idx][nr, nc] = FIREFIGHTER

        return grids

    def get_stats(self):
        total_rescued = sum(ff.people_rescued for ff in self.firefighters)
        avg_hp    = float(np.mean([ff.hp    for ff in self.firefighters])) if self.firefighters else 0.0
        avg_water = float(np.mean([ff.water for ff in self.firefighters])) if self.firefighters else 0.0
        carrying = sum(1 for ff in self.firefighters if ff.carrying_person)
        return {
            'rescued':      total_rescued,
            'carrying':     carrying,
            'firefighters': len(self.firefighters),
            'total_stuck':  sum(ff.stuck_counter for ff in self.firefighters),
            'avg_hp':       avg_hp,
            'avg_water':    avg_water,
            'ff_hp':        [ff.hp    for ff in self.firefighters],
            'ff_water':     [ff.water for ff in self.firefighters],
        }


# ============================================================
# Module-level singletons
# ============================================================

_manager = None


def initialize_firefighters(grids, num=1, algorithm="astar", floor_manager=None):
    global _manager
    _manager = FirefighterManager(num, algorithm=algorithm)
    if floor_manager:
        _manager.set_floor_manager(floor_manager)
    _manager.initialize(grids)
    return grids


def move_firefighter(grids):
    global _manager
    if _manager is None:
        return grids
    return _manager.move_all(grids)


def get_firefighter_stats():
    global _manager
    if _manager is None:
        return {}
    return _manager.get_stats()