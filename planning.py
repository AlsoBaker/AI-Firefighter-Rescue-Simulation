import heapq
import numpy as np
from config import *

def heuristic(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def neighbors(pos):
    r, c = pos
    return [(r+1,c),(r-1,c),(r,c+1),(r,c-1)]


def astar(grid, start, goal):

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

            r,c = nb

            if not (0 <= r < ROWS and 0 <= c < COLS):
                continue

            if grid[r,c] == OBSTACLE or grid[r,c] == FIRE:
                continue

            tentative = g_score[current] + 1

            if nb not in g_score or tentative < g_score[nb]:
                came_from[nb] = current
                g_score[nb] = tentative
                f = tentative + heuristic(nb, goal)
                heapq.heappush(open_set,(f,nb))

    return []