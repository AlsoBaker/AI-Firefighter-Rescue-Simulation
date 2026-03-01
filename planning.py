#planning.py

import heapq
import numpy as np
from config import *

def heuristic(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def neighbors(pos):
    r, c = pos
    return [(r+1,c),(r-1,c),(r,c+1),(r,c-1)]

# =====================================
# A* PATHFINDING
# =====================================

def astar(grid, start, goal):
    print(f"DEBUG ASTAR: start={start}, goal={goal}")  # ADD THIS
    
    open_set = []
    heapq.heappush(open_set, (0, start))

    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)
        print(f"DEBUG ASTAR: current={current}")  # ADD THIS

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            print(f"DEBUG ASTAR: Found path={path}")  # ADD THIS
            return path

        for nb in neighbors(current):
            r,c = nb

            if not (0 <= r < ROWS and 0 <= c < COLS):
                continue

            if grid[r,c] in [OBSTACLE, FIRE]:
                continue

            tentative = g_score[current] + 1

            if nb not in g_score or tentative < g_score[nb]:
                came_from[nb] = current
                g_score[nb] = tentative
                f = tentative + heuristic(nb, goal)
                heapq.heappush(open_set,(f,nb))

    print(f"DEBUG ASTAR: No path found!")  # ADD THIS
    return []
# =====================================
# BFS PATHFINDING
# =====================================

def bfs(grid, start, goal):
    """
    Breadth-First Search - guaranteed shortest path
    Simpler than A* but less efficient for large grids
    """
    from collections import deque
    
    queue = deque([(start, [start])])
    visited = {start}
    
    while queue:
        (r, c), path = queue.popleft()
        
        if (r, c) == goal:
            return path[1:]  # Exclude start
        
        for nr, nc in neighbors((r, c)):
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                if (nr, nc) not in visited:
                    if grid[nr, nc] not in [OBSTACLE, FIRE]:
                        visited.add((nr, nc))
                        queue.append(((nr, nc), path + [(nr, nc)]))
    
    return []


# =====================================
# DIJKSTRA PATHFINDING
# =====================================

def dijkstra(grid, start, goal, weights=None):
    """
    Dijkstra - finds shortest path with custom edge weights
    Use for terrain with different costs
    """
    if weights is None:
        weights = {
            EMPTY: 1,
            PERSON: 1,
            PERSON_DANGER: 2,  # Risky but passable
            SHELTER: 1,
            OBSTACLE: float('inf'),
            FIRE: float('inf')
        }
    
    distances = {start: 0}
    pq = [(0, start)]
    came_from = {}
    
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