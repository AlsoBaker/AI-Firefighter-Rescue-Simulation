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
            SHELTER:      1,
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
