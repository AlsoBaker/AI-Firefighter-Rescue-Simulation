# firefighter.py

import numpy as np
from config import *
from planning import astar, bfs, dijkstra, DStarLite


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
        # Targets where pathfinding returned [] — skipped until fire clears.
        # Cleared every FAILED_TARGET_RESET steps so targets become retryable
        # once fire spreads away or the grid otherwise changes.
        self.failed_targets      = set()
        self._failed_reset_timer = 0
        # D* Lite — one persistent instance per firefighter, reused across ticks.
        # Cleared when goal changes (pickup, delivery, floor switch, new target).
        self.dstar      = None   # DStarLite instance
        self.dstar_goal = None   # goal the current instance was built for
        self.stair_intent       = 0    # direction FF intends to travel when it steps on a staircase
        self._prev_floor        = -1   # floor the FF just switched FROM (blocks immediate yo-yo back)
        self._prev_floor_ticks  = 0    # ticks elapsed since last floor switch (yo-yo cooldown)
        self._target_floor      = None # floor FF is currently heading toward (survives path resets)

    def is_alive(self):
        return self.hp > 0

    def reset_path(self):
        self.current_path = []
        self.dstar        = None
        self.dstar_goal   = None
        self.stair_intent = 0
        # NOTE: _target_floor is intentionally NOT cleared here.
        # It must survive path resets so stair_intent can be re-derived
        # consistently in the STAIRCASE step branch.

    def recalculate_if_blocked(self, grid, algorithm="astar"):
        """
        Scan entire path for obstacles / unwalkable fire.
        - D* Lite: update the existing instance and re-extract path (incremental repair).
        - All other algorithms: wipe path and let move_all replan from scratch.
        Fire cells only block if water == 0.
        """
        blocked = False
        for pos in self.current_path:
            r, c = pos
            cell = grid[r, c]
            if cell == OBSTACLE:
                blocked = True
                break
            if cell == FIRE and self.water <= 0:
                blocked = True
                break

        if not blocked:
            return

        self.stuck_counter += 1

        if algorithm == "dstar_lite" and self.dstar is not None:
            allow_fire = self.water > 0
            # If the fire-traversal policy changed (water ran out or refilled),
            # the existing search tree has stale g-values built under the old
            # policy. Throw it away so find_path rebuilds from scratch next tick.
            if self.dstar.allow_fire != allow_fire:
                self.reset_path()
                return
            # Same policy — repair the existing tree incrementally.
            self.dstar.update(self.pos, grid)
            self.current_path = self.dstar.get_path()
        else:
            self.reset_path()


class FirefighterManager:

    def __init__(self, num_firefighters=1, algorithm="astar"):
        self.firefighters       = []
        self.num_firefighters   = num_firefighters
        self.algorithm          = algorithm
        self.floor_manager      = None
        self._total_extinguished = 0

    def set_floor_manager(self, fm):
        self.floor_manager = fm

    # ----------------------------------------------------------
    # Pathfinding — passes allow_fire based on water level
    # ----------------------------------------------------------

    def find_path(self, grid, start, goal, water=0, ff=None):
        allow_fire = water > 0
        if self.algorithm == "astar":
            return astar(grid, start, goal, allow_fire=allow_fire)
        elif self.algorithm == "bfs":
            return bfs(grid, start, goal, allow_fire=allow_fire)
        elif self.algorithm == "dijkstra":
            return dijkstra(grid, start, goal, allow_fire=allow_fire)
        elif self.algorithm == "dstar_lite":
            if ff is None:
                # Fallback: no FF object to attach instance to
                return astar(grid, start, goal, allow_fire=allow_fire)
            if ff.dstar is None or ff.dstar_goal != goal:
                # New goal — build a fresh D* Lite instance
                ff.dstar      = DStarLite(grid, start, goal, allow_fire=allow_fire)
                ff.dstar_goal = goal
            else:
                # Same goal, grid may have changed — repair incrementally
                ff.dstar.update(start, grid)
            return ff.dstar.get_path()
        # Unknown algorithm — fall back to A*
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

    def _find_person_target(self, grid, start_pos, claimed, failed=None):
        failed = failed or set()
        danger = [tuple(p) for p in np.argwhere(grid == PERSON_DANGER)
                  if tuple(p) not in claimed and tuple(p) not in failed]
        safe   = [tuple(p) for p in np.argwhere(grid == PERSON)
                  if tuple(p) not in claimed and tuple(p) not in failed]
        targets = danger if danger else safe
        if not targets:
            # If all reachable targets are in failed, fall back to ANY target
            # (at least give the FF something to retry)
            danger2 = [tuple(p) for p in np.argwhere(grid == PERSON_DANGER) if tuple(p) not in claimed]
            safe2   = [tuple(p) for p in np.argwhere(grid == PERSON)        if tuple(p) not in claimed]
            targets = danger2 if danger2 else safe2
        if not targets:
            return None
        return min(targets, key=lambda t: abs(start_pos[0]-t[0]) + abs(start_pos[1]-t[1]))

    def _find_hospital(self, grid, start_pos):
        hospitals = [tuple(p) for p in np.argwhere(grid == HOSPITAL)]
        if not hospitals:
            return None
        return min(hospitals, key=lambda h: abs(start_pos[0]-h[0]) + abs(start_pos[1]-h[1]))

    def _staircase_target(self, ff_pos, direction):
        """
        Return the staircase cell (row, col) closest to ff_pos.
        Also stores direction on the FF via stair_intent so switch_floor
        knows which way to go when the FF steps on the cell.
        Both staircase columns go both directions.
        """
        return self.floor_manager.nearest_staircase(ff_pos)

    # ----------------------------------------------------------
    # Fire extinguishing
    # ----------------------------------------------------------

    def _extinguish_adjacent(self, ff, grid):
        """Extinguish fire cells adjacent to FF if water > 0. Returns count extinguished."""
        if ff.water <= 0:
            return 0
        r, c = ff.pos
        extinguished = 0
        for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
            if 0 <= nr < ROWS and 0 <= nc < COLS and grid[nr, nc] == FIRE:
                grid[nr, nc] = EMPTY
                ff.water = max(0, ff.water - WATER_EXTINGUISH)
                extinguished += 1
                if ff.water <= 0:
                    break
        return extinguished

    # ----------------------------------------------------------
    # Main move loop
    # ----------------------------------------------------------

    def move_all(self, grids):
        self.firefighters = [ff for ff in self.firefighters if ff.is_alive()]

        # Restore every FF's cell to what was under it before we process moves.
        for ff in self.firefighters:
            grids[ff.current_floor][ff.pos] = ff.under_cell

        claimed = {}

        for ff in self.firefighters:
            floor_idx     = ff.current_floor
            grid          = grids[floor_idx]
            floor_claimed = claimed.setdefault(floor_idx, set())

            ff.recalculate_if_blocked(grid, algorithm=self.algorithm)

            # Tick the yo-yo cooldown. After PREV_FLOOR_COOLDOWN ticks the
            # "don't go back" guard expires so the FF can revisit if needed.
            _PREV_FLOOR_COOLDOWN = 8
            if ff._prev_floor != -1:
                ff._prev_floor_ticks += 1
                if ff._prev_floor_ticks >= _PREV_FLOOR_COOLDOWN:
                    ff._prev_floor       = -1
                    ff._prev_floor_ticks = 0

            # Periodically retry failed targets (fire may have changed)
            ff._failed_reset_timer += 1
            if ff._failed_reset_timer >= 12:
                ff.failed_targets.clear()
                ff._failed_reset_timer = 0

            # ----------------------------------------------------------------
            # Helper: attempt a floor switch from the FF's current position.
            # Returns True and continues outer loop if the switch fires.
            # ----------------------------------------------------------------
            def _try_stair_switch(intent_direction):
                """
                Switch floor in intent_direction from ff.current_floor.
                Writes the old staircase cell back to STAIRCASE, stamps the
                new position as FIREFIGHTER, clears failed_targets.
                Returns True if the switch happened (caller should `continue`).
                """
                old_floor = ff.current_floor
                old_pos   = ff.pos
                ff.dstar      = None
                ff.dstar_goal = None
                switched = self.floor_manager.switch_floor(ff, intent_direction)
                ff.stair_intent = 0
                if switched:
                    # Restore old staircase cell to STAIRCASE (not ff.under_cell —
                    # that may be stale from a prior move, not from stair arrival).
                    grids[old_floor][old_pos] = STAIRCASE
                    ff.failed_targets.clear()
                    ff._target_floor = None   # reached destination floor, clear intent
                    grids[ff.current_floor][ff.pos] = FIREFIGHTER
                else:
                    # Switch failed (arrival occupied) — stay put.
                    grids[old_floor][old_pos] = FIREFIGHTER
                return switched

            # ---- DECIDE GOAL ----
            if not ff.carrying_person:
                target = self._find_person_target(
                    grid, ff.pos, floor_claimed, failed=ff.failed_targets)

                if target is not None:
                    # Found someone on this floor — cancel any pending floor-switch.
                    ff._target_floor = None
                    ff.stair_intent  = 0

                if target is None and self.floor_manager:
                    # Re-use committed target floor if we already have one and it
                    # still has people — avoids re-evaluating best_floor every tick
                    # which was the root cause of yo-yo.
                    if ff._target_floor is not None:
                        tf = ff._target_floor
                        if (0 <= tf < self.floor_manager.num_floors and
                                self.floor_manager.people_count(tf) > 0 and
                                tf != floor_idx):
                            direction = +1 if tf > floor_idx else -1
                        else:
                            # Target floor is now empty or invalid — re-evaluate.
                            ff._target_floor = None
                            direction        = None
                    else:
                        direction = None

                    if ff._target_floor is None:
                        best_floor, count = self.floor_manager.best_floor_to_visit(
                            floor_idx, exclude_floor=ff._prev_floor)
                        if best_floor is not None and count > 0:
                            ff._target_floor = best_floor
                            direction        = +1 if best_floor > floor_idx else -1

                    if ff._target_floor is not None and direction is not None:
                        ff.stair_intent = direction
                        target = self._staircase_target(ff.pos, direction)

                        # FF is already standing on the target staircase cell —
                        # trigger the floor switch immediately.
                        if target == ff.pos:
                            if _try_stair_switch(ff.stair_intent):
                                continue
                            else:
                                # Arrival blocked — wait here
                                grids[floor_idx][ff.pos] = FIREFIGHTER
                                continue

                if target is None:
                    ff._prev_floor = -1   # no longer guarding against yo-yo
                    grids[floor_idx][ff.pos] = FIREFIGHTER
                    continue

                floor_claimed.add(target)

                # Invalidate D* Lite if goal changed
                if target != ff.dstar_goal:
                    ff.dstar      = None
                    ff.dstar_goal = None

                if not ff.current_path:
                    ff.current_path = self.find_path(grid, ff.pos, target,
                                                     water=ff.water, ff=ff)
                    if not ff.current_path:
                        # Only mark as failed if we're not already standing on the
                        # target (start==goal returns [] but is not a failure).
                        already_there = (ff.pos == target)
                        if not already_there and not (self.floor_manager and
                                self.floor_manager.is_staircase(*target)):
                            ff.failed_targets.add(target)
                        grids[floor_idx][ff.pos] = FIREFIGHTER
                        continue

            else:
                target = self._find_hospital(grid, ff.pos)

                if target is None and self.floor_manager:
                    hospital_floor = None
                    best_dist = float('inf')
                    for f in range(self.floor_manager.num_floors):
                        if f == floor_idx:
                            continue
                        if self._find_hospital(self.floor_manager.grids[f], ff.pos):
                            dist = abs(f - floor_idx)
                            if dist < best_dist:
                                best_dist     = dist
                                hospital_floor = f
                    if hospital_floor is not None:
                        direction = +1 if hospital_floor > floor_idx else -1
                        ff.stair_intent = direction
                        target = self._staircase_target(ff.pos, direction)

                        if target == ff.pos:
                            if _try_stair_switch(ff.stair_intent):
                                continue
                            else:
                                grids[floor_idx][ff.pos] = FIREFIGHTER
                                continue

                if target is None:
                    grids[floor_idx][ff.pos] = FIREFIGHTER
                    continue

                if target != ff.dstar_goal:
                    ff.dstar      = None
                    ff.dstar_goal = None

                if not ff.current_path:
                    ff.current_path = self.find_path(grid, ff.pos, target,
                                                     water=ff.water, ff=ff)

            # ---- FOLLOW PATH ----
            if not ff.current_path:
                grids[floor_idx][ff.pos] = FIREFIGHTER
                continue

            next_pos = ff.current_path.pop(0)
            nr, nc   = next_pos

            if grid[nr, nc] == FIREFIGHTER:
                # Blocked by another FF. If it is a staircase cell, wait (they
                # will move away). Otherwise replan from scratch.
                if self.floor_manager and self.floor_manager.is_staircase(nr, nc):
                    ff.current_path.insert(0, next_pos)
                else:
                    ff.current_path = []
                grids[floor_idx][ff.pos] = FIREFIGHTER
                continue

            dest_cell = grid[nr, nc]

            # ---- Moving onto fire ----
            if dest_cell == FIRE:
                if ff.water > 0:
                    ff.water = max(0, ff.water - WATER_FIRE_STEP)
                else:
                    ff.hp = max(0, ff.hp - 1)

            # ---- STAIRCASE step ----
            if dest_cell == STAIRCASE and self.floor_manager:
                if self.floor_manager.stair_direction(nr, nc) != 0:
                    # Re-derive stair_intent from _target_floor if it was cleared
                    # by a path reset.  This ensures the FF always travels in the
                    # direction it originally committed to.
                    if ff.stair_intent == 0 and ff._target_floor is not None:
                        tf = ff._target_floor
                        if (0 <= tf < self.floor_manager.num_floors and
                                tf != floor_idx and
                                self.floor_manager.people_count(tf) > 0):
                            ff.stair_intent = +1 if tf > floor_idx else -1
                        else:
                            # Target floor emptied — abandon switch, clear intent.
                            ff._target_floor = None

                    if ff.stair_intent != 0:
                        # Move FF onto the staircase cell first so switch_floor
                        # uses the correct arrival column.
                        ff.pos        = next_pos
                        ff.under_cell = STAIRCASE
                        if _try_stair_switch(ff.stair_intent):
                            continue
                        else:
                            # Arrival blocked — stand on the staircase and retry
                            grids[floor_idx][ff.pos] = FIREFIGHTER
                            continue
                    # stair_intent still 0 — nothing to do, fall through and
                    # treat the staircase cell as a normal move.

            # ---- PICKUP ----
            if dest_cell in (PERSON, PERSON_DANGER):
                ff.carrying_person = True
                ff.dstar           = None
                ff.dstar_goal      = None
                ff.failed_targets.clear()   # fresh mission — forget unreachable targets
                print(f"  FF picked up person on floor {floor_idx + 1}!")
                dest_cell = EMPTY

            # ---- DELIVER ----
            elif dest_cell == HOSPITAL and ff.carrying_person:
                ff.carrying_person  = False
                ff.people_rescued  += 1
                ff.water            = min(WATER_MAX, ff.water + WATER_REFILL)
                ff.dstar            = None
                ff.dstar_goal       = None
                ff.failed_targets.clear()   # back to rescue mode — forget old failures
                print(f"  Delivered! Floor {floor_idx+1} | rescued={ff.people_rescued} | water={ff.water}")
                dest_cell = HOSPITAL

            ff.under_cell  = dest_cell
            ff.pos         = next_pos
            # _prev_floor is cleared by the tick-based cooldown above, not here,
            # so a single normal step doesn't immediately re-open the yo-yo gate.
            grids[floor_idx][nr, nc] = FIREFIGHTER
            # Do NOT clear failed_targets here — that would immediately re-expose
            # unreachable targets after every single step. failed_targets is cleared
            # on: (a) the periodic 12-tick timer, (b) floor switch, (c) pickup/delivery.

            # Extinguish adjacent fire after moving
            self._total_extinguished += self._extinguish_adjacent(ff, grids[floor_idx])

        return grids

    def get_stats(self):
        total_rescued = sum(ff.people_rescued for ff in self.firefighters)
        avg_hp    = float(np.mean([ff.hp    for ff in self.firefighters])) if self.firefighters else 0.0
        avg_water = float(np.mean([ff.water for ff in self.firefighters])) if self.firefighters else 0.0
        carrying = sum(1 for ff in self.firefighters if ff.carrying_person)
        return {
            'rescued':      total_rescued,
            'carrying':     carrying,
            'extinguished': self._total_extinguished,
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