# planning.py

import heapq
import numpy as np
from config import *


def heuristic(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def neighbors(pos):
    r, c = pos
    return [(r+1,c),(r-1,c),(r,c+1),(r,c-1)]


def _blocked(cell, allow_fire):
    """Return True if cell is impassable given current water state."""
    if cell == OBSTACLE:
        return True
    if cell == FIRE and not allow_fire:
        return True
    return False


# ============================================================
# A* PATHFINDING
# ============================================================

def astar(grid, start, goal, allow_fire=False):
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path

        for nb in neighbors(current):
            r, c = nb
            if not (0 <= r < ROWS and 0 <= c < COLS):
                continue
            if _blocked(grid[r, c], allow_fire):
                continue

            tentative = g_score[current] + 1
            if nb not in g_score or tentative < g_score[nb]:
                came_from[nb] = current
                g_score[nb] = tentative
                f = tentative + heuristic(nb, goal)
                heapq.heappush(open_set, (f, nb))

    return []


# ============================================================
# BFS PATHFINDING
# ============================================================

def bfs(grid, start, goal, allow_fire=False):
    from collections import deque
    queue   = deque([(start, [start])])
    visited = {start}

    while queue:
        (r, c), path = queue.popleft()
        if (r, c) == goal:
            return path[1:]

        for nr, nc in neighbors((r, c)):
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                if (nr, nc) not in visited:
                    if not _blocked(grid[nr, nc], allow_fire):
                        visited.add((nr, nc))
                        queue.append(((nr, nc), path + [(nr, nc)]))

    return []


# ============================================================
# DIJKSTRA PATHFINDING
# ============================================================

def dijkstra(grid, start, goal, allow_fire=False, weights=None):
    if weights is None:
        weights = {
            EMPTY:        1,
            PERSON:       1,
            PERSON_DANGER:2,
            HOSPITAL:     1,
            STAIRCASE:    1,
            OBSTACLE:     float('inf'),
            FIRE:         3 if allow_fire else float('inf'),
        }

    distances  = {start: 0}
    pq         = [(0, start)]
    came_from  = {}

    while pq:
        current_dist, current = heapq.heappop(pq)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path

        if current_dist > distances.get(current, float('inf')):
            continue

        r, c = current
        for nr, nc in neighbors((r, c)):
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                cell_type = grid[nr, nc]
                cost = weights.get(cell_type, float('inf'))
                if cost == float('inf'):
                    continue
                new_dist = current_dist + cost
                if new_dist < distances.get((nr, nc), float('inf')):
                    distances[(nr, nc)] = new_dist
                    came_from[(nr, nc)] = current
                    heapq.heappush(pq, (new_dist, (nr, nc)))

    return []


# ============================================================
# D* LITE — INCREMENTAL DYNAMIC PATHFINDING
# ============================================================

class DStarLite:
    """
    D* Lite pathfinder for dynamic environments (Koenig & Likhachev, 2002).

    Unlike A*, BFS, or Dijkstra which replan from scratch when the grid
    changes, D* Lite *repairs* the existing search tree incrementally —
    only reprocessing the cells affected by the change.

    This is the right algorithm for the rescue sim because fire spreads
    every 4 steps, turning passable cells into costly/blocked ones mid-path.

    Searching direction: goal → start (reversed), so g(s) = optimal cost
    from s to goal.  Path extraction: from current position, greedily step
    to the neighbour with minimum (edge_cost + g_value).

    Public API
    ----------
    ds = DStarLite(grid, start, goal, allow_fire=False)
    path = ds.get_path()               # first path

    ds.update(new_start, new_grid)     # after robot moves + fire spreads
    path = ds.get_path()               # repaired path
    """

    INF = float('inf')

    def __init__(self, grid, start, goal, allow_fire=False):
        self.grid       = grid.copy()
        self.start      = start
        self.goal       = goal
        self.allow_fire = allow_fire
        self.k_m        = 0          # accumulated heuristic drift
        self.s_last     = start      # robot position at last update

        self.g   = {}   # g[s]   = estimated cost from s to goal
        self.rhs = {}   # rhs[s] = one-step lookahead value

        # Lazy-deletion priority queue: heap of (key, node)
        # _tag[node] = key currently "valid" for that node; mismatches = stale
        self._heap = []
        self._tag  = {}

        # Seed: only goal has rhs = 0; everything else defaults to INF
        self.rhs[self.goal] = 0
        self._push(self.goal, self._calc_key(self.goal))
        self._compute()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _g(self, s):
        return self.g.get(s, self.INF)

    def _rhs(self, s):
        return self.rhs.get(s, self.INF)

    def _h(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _calc_key(self, s):
        gv = min(self._g(s), self._rhs(s))
        return (gv + self._h(self.start, s) + self.k_m, gv)

    def _enter_cost(self, r, c):
        """
        Forward cost of entering cell (r, c) from any neighbour.
        D* Lite edge cost u→v = cost to enter v in forward direction.
        """
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return self.INF
        cell = int(self.grid[r, c])
        if cell == OBSTACLE:
            return self.INF
        if cell == FIRE:
            return 3.0 if self.allow_fire else self.INF
        return 1.0

    def _edge_cost(self, u, v):
        """Cost of the directed edge u→v = cost to enter v."""
        return self._enter_cost(v[0], v[1])

    def _succ(self, s):
        """4-connected grid neighbours within bounds."""
        r, c = s
        out = []
        for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                out.append((nr, nc))
        return out

    # ── Priority queue (lazy deletion) ────────────────────────────────────────

    def _push(self, s, key):
        heapq.heappush(self._heap, (key, s))
        self._tag[s] = key

    def _top_key(self):
        while self._heap:
            key, s = self._heap[0]
            if self._tag.get(s) == key:
                return key
            heapq.heappop(self._heap)
        return (self.INF, self.INF)

    def _pop(self):
        while self._heap:
            key, s = heapq.heappop(self._heap)
            if self._tag.get(s) == key:
                self._tag.pop(s, None)
                return key, s
        return (self.INF, self.INF), None

    def _remove(self, s):
        """Logically remove s (tag cleared; stale heap entries stay)."""
        self._tag.pop(s, None)

    # ── D* Lite core ──────────────────────────────────────────────────────────

    def _update_vertex(self, u):
        """Recompute rhs(u) and reinsert into queue if inconsistent."""
        if u != self.goal:
            self.rhs[u] = min(
                (self._edge_cost(u, s) + self._g(s) for s in self._succ(u)),
                default=self.INF
            )
        self._remove(u)
        if self._g(u) != self._rhs(u):
            self._push(u, self._calc_key(u))

    def _compute(self):
        """
        Process queue until start is locally consistent.
        Safety cap = 20 × grid size to prevent any runaway on degenerate inputs.
        """
        cap = ROWS * COLS * 20
        for _ in range(cap):
            top_key   = self._top_key()
            start_key = self._calc_key(self.start)

            if not (top_key < start_key
                    or self._rhs(self.start) != self._g(self.start)):
                break

            old_key, u = self._pop()
            if u is None:
                break

            new_key = self._calc_key(u)
            if old_key < new_key:
                # Key grew — reinsert with corrected key
                self._push(u, new_key)
            elif self._g(u) > self._rhs(u):
                # Over-consistent: lower g to rhs, propagate
                self.g[u] = self._rhs(u)
                for s in self._succ(u):
                    self._update_vertex(s)
            else:
                # Under-consistent: raise g to inf, re-propagate
                self.g[u] = self.INF
                for s in self._succ(u) + [u]:
                    self._update_vertex(s)

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, new_start, new_grid):
        """
        Incrementally repair the search after the robot moves and the grid
        may have changed (e.g. fire spread).

        Only cells whose cost changed are reprocessed — O(changed × log n)
        instead of O(n log n) for a full A* replan.
        """
        # Accumulate heuristic drift caused by the robot moving
        self.k_m   += self._h(self.s_last, new_start)
        self.s_last = new_start
        self.start  = new_start

        # Detect changed cells (fire only spreads → monotone cost increase)
        changed = []
        for r in range(ROWS):
            for c in range(COLS):
                if int(new_grid[r, c]) != int(self.grid[r, c]):
                    changed.append((r, c))

        self.grid = new_grid.copy()

        for cell in changed:
            # A cell's cost change affects paths running through it AND
            # the rhs of all nodes whose best successor was that cell.
            self._update_vertex(cell)
            for nb in self._succ(cell):
                self._update_vertex(nb)

        self._compute()

    def get_path(self):
        """
        Greedily extract the optimal path from start to goal using g values.
        Returns a list of (r,c) positions NOT including start.
        Returns [] if no path exists or start == goal.
        """
        if self.start == self.goal:
            return []
        if self._g(self.start) >= self.INF:
            return []

        path    = []
        current = self.start
        visited = {current}

        for _ in range(ROWS * COLS + 1):
            if current == self.goal:
                break

            best_nb  = None
            best_val = self.INF

            for nb in self._succ(current):
                val = self._edge_cost(current, nb) + self._g(nb)
                if val < best_val:
                    best_val = val
                    best_nb  = nb

            if best_nb is None or best_nb in visited:
                return []   # no path or cycle — shouldn't happen if g values correct

            path.append(best_nb)
            visited.add(best_nb)
            current = best_nb

        return path if current == self.goal else []
