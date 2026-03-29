# ambulance.py

import heapq, os, math, pygame
import numpy as np

from city_map import (
    generate_city, get_passable,
    ROAD, BUILDING, INTERSECTION, FIRE_STATION, HOSPITAL,
    RIVER, BRIDGE,
    CITY_COLS, CITY_ROWS, BLOCK_SIZE,
)

pygame.init()

_info    = pygame.display.Info()
SCREEN_W = _info.current_w
SCREEN_H = _info.current_h

PANEL_W  = 280
MAP_W    = SCREEN_W - PANEL_W
CELL_SIZE = min(MAP_W // CITY_COLS, SCREEN_H // CITY_ROWS)
OFFSET_X = PANEL_W + (MAP_W  - CELL_SIZE * CITY_COLS) // 2
OFFSET_Y = (SCREEN_H - CELL_SIZE * CITY_ROWS) // 2

# ── Colours ───────────────────────────────────────────────────────────────────
C_BG           = (12, 14, 18)
C_ROAD         = (68, 70, 78)
C_ROAD_LINE    = (90, 88, 50)      # dashed centre line
C_INTER        = (78, 76, 58)
C_CROSS_WALK   = (200, 200, 195)   # crosswalk stripes
C_BUILDING_LN  = (28, 28, 36)      # building outline
C_PARK         = (32, 72, 36)
C_PARK_TREE    = (24, 58, 28)
C_PARK_CANOPY  = (40, 100, 44)
C_RIVER        = (30, 70, 130)
C_RIVER_SHINE  = (50, 100, 170)
C_BRIDGE       = (120, 100, 70)
C_BRIDGE_PLANK = (100, 82, 55)
C_FIRE_ST      = (170, 70, 20)
C_FIRE_ST_TXT  = (255, 210, 170)
C_HOSP         = (30, 110, 55)
C_HOSP_TARGET  = (255, 240, 80)
C_PATH_DONE    = (140, 140, 140)
C_PATH_AHEAD   = (255, 210, 40)
C_PANEL        = (16, 18, 24)
C_PANEL_LINE   = (40, 42, 52)
C_TEXT         = (210, 212, 220)
C_TEXT_DIM     = (100, 104, 116)
C_GOLD         = (255, 200, 50)
C_GREEN        = (50, 200, 80)
C_NAME_TXT     = (160, 158, 120)   # road name at intersection
C_CAR          = [(220, 60, 60),(60, 140, 220),(240, 200, 50),
                  (80, 200, 100),(200, 80, 200),(220, 140, 50)]

ASSETS = "assets"

F_LARGE  = pygame.font.Font(None, 42)
F_MEDIUM = pygame.font.Font(None, 28)
F_SMALL  = pygame.font.Font(None, 22)
F_TINY   = pygame.font.Font(None, 15)


# ── A* ────────────────────────────────────────────────────────────────────────
def city_astar(grid, start, goal):
    passable = get_passable()
    open_set = [(0, start)]
    came_from, g = {}, {start: 0}
    while open_set:
        _, cur = heapq.heappop(open_set)
        if cur == goal:
            path = []
            while cur in came_from:
                path.append(cur); cur = came_from[cur]
            return path[::-1]
        r, c = cur
        for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
            if not (0 <= nr < CITY_ROWS and 0 <= nc < CITY_COLS): continue
            if grid[nr, nc] not in passable: continue
            ng = g[cur] + 1
            if ng < g.get((nr,nc), 1e9):
                came_from[(nr,nc)] = cur; g[(nr,nc)] = ng
                heapq.heappush(open_set, (ng + abs(nr-goal[0]) + abs(nc-goal[1]), (nr,nc)))
    return []


def _px(r, c):
    return OFFSET_X + c * CELL_SIZE, OFFSET_Y + r * CELL_SIZE

def _centre(r, c):
    x, y = _px(r, c)
    return x + CELL_SIZE // 2, y + CELL_SIZE // 2

def _load(fn, size):
    path = os.path.join(ASSETS, fn)
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size)
    except:
        return None


# ── Traffic car ───────────────────────────────────────────────────────────────
class TrafficCar:
    DIRS = [(0,1),(0,-1),(1,0),(-1,0)]

    def __init__(self, r, c, color, grid, rng):
        self.r, self.c = r, c
        self.color     = color
        self.dir       = list(rng.choice(self.DIRS))
        self.timer     = 0
        self.interval  = int(rng.integers(30, 60))
        self._grid     = grid
        self._passable = get_passable()

    def update(self, occupied):
        """Move one step. occupied = set of (r,c) positions of other cars."""
        self.timer += 1
        if self.timer < self.interval:
            return
        self.timer = 0
        nr = self.r + self.dir[0]
        nc = self.c + self.dir[1]
        if (0 <= nr < CITY_ROWS and 0 <= nc < CITY_COLS and
                self._grid[nr, nc] in self._passable and
                (nr, nc) not in occupied):
            self.r, self.c = nr, nc
        else:
            self.dir = [-self.dir[0], -self.dir[1]]

    def draw(self, screen):
        x, y = _px(self.r, self.c)
        pad  = CELL_SIZE // 5
        pygame.draw.rect(screen, self.color,
                         (x+pad, y+pad, CELL_SIZE-pad*2, CELL_SIZE-pad*2),
                         border_radius=2)


# ── Main class ────────────────────────────────────────────────────────────────
class AmbulancePhase:

    def __init__(self, rescued_count=0):
        self.rescued_count = rescued_count
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
        pygame.display.set_caption("Ambulance Delivery Phase")
        self.clock  = pygame.time.Clock()
        self.speed  = 3.0
        self._reset()

    def _reset(self):
        rng = np.random.default_rng()
        result = generate_city(seed=int(rng.integers(0, 99999)))
        (self.grid, self.fire_station, self.hospitals, self.hospital_blocks,
         self.fs_block, self.building_colors, self.road_names, self.river_row,
         self.block_sprites) = result

        self._find_best_path()
        self._load_images()

        # Traffic
        passable = get_passable()
        road_cells = [(r, c) for r in range(CITY_ROWS) for c in range(CITY_COLS)
                      if self.grid[r, c] in passable
                      and (r, c) not in {self.fire_station, self.target_hosp}]
        trng = np.random.default_rng()
        trng.shuffle(road_cells)
        colors = C_CAR * 2
        self.cars = [TrafficCar(r, c, colors[i], self.grid, trng)
                     for i, (r, c) in enumerate(road_cells[:6])]

        # Ambulance starts visually at the centre of the big firestation block
        ext_rows = sorted(range(0, CITY_ROWS, BLOCK_SIZE)) + [CITY_ROWS]
        ext_cols = sorted(range(0, CITY_COLS, BLOCK_SIZE)) + [CITY_COLS]
        fs_bi, fs_ci = self.fs_block
        fs_bx, fs_by = _px(ext_rows[fs_bi] + 1, ext_cols[fs_ci] + 1)
        block_px = (BLOCK_SIZE - 1) * CELL_SIZE
        fs_cx = fs_bx + block_px // 2
        fs_cy = fs_by + block_px // 2

        # Ambulance state
        self.path_idx   = 0
        self.progress   = 0.0
        self.amb_pos    = (fs_cx, fs_cy)
        self.trail      = []          # list of pixel positions
        self.delivered  = False
        self.elapsed    = 0
        self.anim_frame = 0
        self.siren_on   = True
        self.siren_r    = 0
        self.siren_grow = True

    def _find_best_path(self):
        best_path, best_h = [], self.hospitals[0]
        for h in self.hospitals:
            p = city_astar(self.grid, self.fire_station, h)
            if p and (not best_path or len(p) < len(best_path)):
                best_path, best_h = p, h
        self.path        = [self.fire_station] + best_path
        self.target_hosp = best_h
        self.path_length = len(best_path)

    def _load_images(self):
        cs = CELL_SIZE
        self.img_amb       = _load("ambulance.png",  (cs, cs))
        block_px = (BLOCK_SIZE - 1) * cs
        self.block_px      = block_px
        self.img_hosp      = _load("hospital.png",    (block_px, block_px))
        self.img_firestation = _load("firestation.png", (block_px, block_px))
        # Load building images; filter out None so we always have valid images to cycle
        raw = [_load(f"building{i+1}.png", (block_px, block_px)) for i in range(10)]
        self.img_buildings = [img for img in raw if img is not None]
        if not self.img_buildings:
            self.img_buildings = None  # no building images available

    # ── Update ────────────────────────────────────────────────────────────────
    def update(self, dt):
        self.anim_frame += 1

        # Siren pulse
        if self.siren_grow:
            self.siren_r += 1
            if self.siren_r >= CELL_SIZE * 2: self.siren_grow = False
        else:
            self.siren_r -= 1
            if self.siren_r <= CELL_SIZE // 2: self.siren_grow = True

        occupied = {(car.r, car.c) for car in self.cars}
        for car in self.cars:
            other = occupied - {(car.r, car.c)}
            car.update(other)

        if self.delivered:
            return

        if self.path_idx >= len(self.path) - 1:
            self.delivered = True; return

        # Check if next cell is blocked by a car
        next_cell = self.path[self.path_idx + 1] if self.path_idx + 1 < len(self.path) else None
        car_blocking = next_cell and any(
            (car.r, car.c) == next_cell for car in self.cars
        )
        effective_speed = self.speed * 0.4 if car_blocking else self.speed

        self.progress += effective_speed * dt

        while self.progress >= 1.0 and self.path_idx < len(self.path) - 1:
            self.progress  -= 1.0
            self.path_idx  += 1
            self.elapsed   += 1
            # Store trail point
            self.trail.append(_centre(*self.path[self.path_idx]))
            if len(self.trail) > 50:
                self.trail.pop(0)

        if self.path_idx >= len(self.path) - 1:
            self.delivered = True
            self.amb_pos   = _centre(*self.path[-1])
            return

        r0, c0 = self.path[self.path_idx]
        r1, c1 = self.path[self.path_idx + 1]
        cx0, cy0 = _centre(r0, c0)
        cx1, cy1 = _centre(r1, c1)
        t = min(1.0, self.progress)
        self.amb_pos = (int(cx0 + (cx1-cx0)*t), int(cy0 + (cy1-cy0)*t))

    # ── Drawing ───────────────────────────────────────────────────────────────
    def draw(self):
        self.screen.fill(C_BG)
        self._draw_city()
        self._draw_building_sprites()
        self._draw_hospital_blocks()
        self._draw_trail()
        self._draw_path()
        self._draw_cars()
        self._draw_siren()
        self._draw_ambulance()
        self._draw_panel()
        if self.delivered:
            self._draw_banner()
        pygame.display.flip()

    def _draw_city(self):
        cs = CELL_SIZE
        road_rows_set = set(range(0, CITY_ROWS, BLOCK_SIZE))
        road_cols_set = set(range(0, CITY_COLS, BLOCK_SIZE))
        road_rows_list = sorted(road_rows_set)
        road_cols_list = sorted(road_cols_set)

        # Pass 1 — draw all cells (backgrounds, roads, etc.)
        for r in range(CITY_ROWS):
            for c in range(CITY_COLS):
                x, y = _px(r, c)
                cell = self.grid[r, c]

                if cell == BUILDING:
                    col = self.building_colors.get((r, c), (50, 50, 64))
                    pygame.draw.rect(self.screen, col, (x, y, cs, cs))

                elif cell == ROAD:
                    pygame.draw.rect(self.screen, C_ROAD, (x, y, cs, cs))
                    # Dashed centre line (horizontal roads)
                    if cs >= 10:
                        mx, my = x + cs//2, y + cs//2
                        if self.anim_frame % 2 == 0:  # static dashes
                            dash_len = max(3, cs // 4)
                            for i in range(0, cs, dash_len * 2):
                                pygame.draw.line(self.screen, C_ROAD_LINE,
                                                 (x + i, my), (x + i + dash_len, my), 1)

                elif cell == INTERSECTION:
                    pygame.draw.rect(self.screen, C_INTER, (x, y, cs, cs))
                    # Crosswalk stripes on edges
                    stripe_w = max(2, cs // 5)
                    for i in range(0, cs, stripe_w * 2):
                        pygame.draw.rect(self.screen, C_CROSS_WALK,
                                         (x + i, y, stripe_w, 3))
                        pygame.draw.rect(self.screen, C_CROSS_WALK,
                                         (x + i, y + cs - 3, stripe_w, 3))
                    # Road name (tiny)
                    name = self.road_names.get((r, c), "")
                    if name and cs >= 14:
                        parts = name.split(" / ")
                        for pi, part in enumerate(parts[:2]):
                            surf = F_TINY.render(part, True, C_NAME_TXT)
                            if surf.get_width() <= cs:
                                self.screen.blit(surf, (x + 1, y + 1 + pi * 8))

                elif cell == RIVER:
                    pygame.draw.rect(self.screen, C_RIVER, (x, y, cs, cs))
                    # Shimmer line
                    sy = y + cs // 2
                    for sx in range(x, x + cs, 4):
                        pygame.draw.line(self.screen, C_RIVER_SHINE,
                                         (sx, sy), (sx + 2, sy), 1)

                elif cell == BRIDGE:
                    pygame.draw.rect(self.screen, C_BRIDGE, (x, y, cs, cs))
                    # Plank lines
                    for bx in range(x + 2, x + cs - 1, max(3, cs//4)):
                        pygame.draw.line(self.screen, C_BRIDGE_PLANK,
                                         (bx, y), (bx, y + cs), 1)

                elif cell == FIRE_STATION:
                    pygame.draw.rect(self.screen, C_FIRE_ST, (x, y, cs, cs))
                    lbl = F_TINY.render("FS", True, C_FIRE_ST_TXT)
                    self.screen.blit(lbl, (x + 1, y + 1))

                elif cell == HOSPITAL:
                    pygame.draw.rect(self.screen, C_HOSP, (x, y, cs, cs))

    def _draw_building_sprites(self):
        """Pass 2 — draw building + firestation images over blocks."""
        cs = CELL_SIZE
        ext_rows = sorted(range(0, CITY_ROWS, BLOCK_SIZE)) + [CITY_ROWS]
        ext_cols = sorted(range(0, CITY_COLS, BLOCK_SIZE)) + [CITY_COLS]
        imgs = self.img_buildings  # already filtered — all entries are valid
        n_imgs = len(imgs) if imgs else 0
        for bi, r0 in enumerate(ext_rows[:-1]):
            for ci, c0 in enumerate(ext_cols[:-1]):
                sprite_idx = self.block_sprites.get((bi, ci), 0)
                x, y = _px(r0 + 1, c0 + 1)
                if sprite_idx == -1:
                    continue  # hospital — drawn in _draw_hospital_blocks
                elif sprite_idx == -2:
                    # Fire station big block
                    if self.img_firestation:
                        self.screen.blit(self.img_firestation, (x, y))
                elif n_imgs > 0:
                    # Cycle through available images so no block is ever empty
                    img = imgs[sprite_idx % n_imgs]
                    self.screen.blit(img, (x, y))

    def _draw_hospital_blocks(self):
        """Draw big hospital image + target highlight over hospital blocks."""
        cs = CELL_SIZE
        ext_rows = sorted(range(0, CITY_ROWS, BLOCK_SIZE)) + [CITY_ROWS]
        ext_cols = sorted(range(0, CITY_COLS, BLOCK_SIZE)) + [CITY_COLS]
        hosp_set = set(map(tuple, self.hospital_blocks))
        target_block = None
        # Find which hospital block corresponds to target_hosp
        for i, hpos in enumerate(self.hospitals):
            if hpos == self.target_hosp and i < len(self.hospital_blocks):
                target_block = tuple(self.hospital_blocks[i])
                break
        for bi, ci in self.hospital_blocks:
            r0 = ext_rows[bi]; c0 = ext_cols[ci]
            x, y = _px(r0 + 1, c0 + 1)
            bpx = self.block_px
            is_target = (bi, ci) == target_block
            if is_target:
                # Yellow highlight border around the block
                pygame.draw.rect(self.screen, C_HOSP_TARGET,
                                 (x - 3, y - 3, bpx + 6, bpx + 6), 3)
            if self.img_hosp:
                if not is_target:
                    dim = self.img_hosp.copy(); dim.set_alpha(160)
                    self.screen.blit(dim, (x, y))
                else:
                    self.screen.blit(self.img_hosp, (x, y))

    def _draw_trail(self):
        if len(self.trail) < 2:
            return
        surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        n = len(self.trail)
        for i in range(1, n):
            alpha = int(30 + 150 * i / n)
            col   = (200, 200, 200, alpha)
            pygame.draw.line(surf, col, self.trail[i-1], self.trail[i], 2)
        self.screen.blit(surf, (0, 0))

    def _draw_path(self):
        if len(self.path) < 2: return
        # Travelled — dim white
        for i in range(min(self.path_idx, len(self.path)-1)):
            pygame.draw.line(self.screen, C_PATH_DONE,
                             _centre(*self.path[i]), _centre(*self.path[i+1]), 2)
        # Upcoming — yellow dashes
        dash = True
        for i in range(self.path_idx, len(self.path)-1):
            if dash:
                pygame.draw.line(self.screen, C_PATH_AHEAD,
                                 _centre(*self.path[i]), _centre(*self.path[i+1]), 2)
            dash = not dash

    def _draw_cars(self):
        for car in self.cars:
            car.draw(self.screen)

    def _draw_siren(self):
        if self.delivered: return
        ax, ay = self.amb_pos
        # Alternating red / blue every 30 frames
        col = (220, 50, 50) if (self.anim_frame // 30) % 2 == 0 else (50, 80, 220)
        r   = self.siren_r
        if r > 0:
            surf = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            alpha = max(0, 120 - r * 2)
            pygame.draw.circle(surf, (*col, alpha), (r+1, r+1), r, 2)
            self.screen.blit(surf, (ax - r - 1, ay - r - 1))

    def _draw_ambulance(self):
        ax, ay = self.amb_pos
        hs = CELL_SIZE // 2
        if self.img_amb:
            self.screen.blit(self.img_amb, (ax - hs, ay - hs))
        else:
            pygame.draw.rect(self.screen, (230, 230, 230),
                             (ax-hs, ay-hs, CELL_SIZE, CELL_SIZE))

    def _draw_panel(self):
        pygame.draw.rect(self.screen, C_PANEL, (0, 0, PANEL_W, SCREEN_H))
        pygame.draw.line(self.screen, C_PANEL_LINE, (PANEL_W, 0), (PANEL_W, SCREEN_H), 1)
        y = 20

        def t(text, font, color, cx=False):
            nonlocal y
            s = font.render(text, True, color)
            xp = (PANEL_W - s.get_width()) // 2 if cx else 14
            self.screen.blit(s, (xp, y))
            y += s.get_height() + 4

        t("AMBULANCE", F_LARGE, C_TEXT, cx=True)
        t("DELIVERY",  F_LARGE, C_TEXT, cx=True)
        y += 8
        pygame.draw.line(self.screen, C_PANEL_LINE, (14, y), (PANEL_W-14, y), 1)
        y += 10

        status = "DELIVERED!" if self.delivered else "EN ROUTE..."
        t(status, F_MEDIUM, C_GREEN if self.delivered else C_GOLD, cx=True)
        y += 6

        for label, val in [
            ("Civilians rescued", str(self.rescued_count)),
            ("Route distance",    f"{self.path_length} cells"),
            ("Steps taken",       str(self.elapsed)),
            ("Hospitals on map",  str(len(self.hospitals))),
            ("Speed",             f"{self.speed:.1f}x"),
        ]:
            sl = F_SMALL.render(f"{label}:", True, C_TEXT_DIM)
            sv = F_SMALL.render(val, True, C_TEXT)
            self.screen.blit(sl, (14, y))
            self.screen.blit(sv, (PANEL_W - sv.get_width() - 14, y))
            y += 22

        y += 8
        pygame.draw.line(self.screen, C_PANEL_LINE, (14, y), (PANEL_W-14, y), 1)
        y += 10

        t("Legend", F_SMALL, C_TEXT_DIM)
        for col, lbl in [
            (C_ROAD,       "Road"),
            (C_INTER,      "Intersection"),
            ((52,52,68),   "Building"),
            (C_FIRE_ST,    "Fire station (start)"),
            (C_HOSP,       "Hospital (target)"),
            (C_RIVER,      "River (impassable)"),
            (C_BRIDGE,     "Bridge (crossable)"),
            (C_PATH_DONE,  "Travelled path"),
            (C_PATH_AHEAD, "Upcoming path"),
        ]:
            pygame.draw.rect(self.screen, col, (14, y+3, 11, 11))
            self.screen.blit(F_TINY.render(lbl, True, C_TEXT_DIM), (30, y+1))
            y += 17

        y += 10
        pygame.draw.line(self.screen, C_PANEL_LINE, (14, y), (PANEL_W-14, y), 1)
        y += 10
        for line in ["UP/DN  Speed", "R      New city", "ESC    Quit"]:
            self.screen.blit(F_TINY.render(line, True, C_TEXT_DIM), (14, y))
            y += 16

    def _draw_banner(self):
        if self.anim_frame % 60 >= 45: return
        bw, bh = 540, 72
        bx = PANEL_W + (SCREEN_W - PANEL_W - bw) // 2
        by = SCREEN_H // 2 - bh // 2
        pygame.draw.rect(self.screen, (16, 50, 24), (bx, by, bw, bh), border_radius=10)
        pygame.draw.rect(self.screen, C_GREEN,      (bx, by, bw, bh), 2, border_radius=10)
        l1 = F_LARGE.render(f"Delivered!  {self.rescued_count} civilians safe", True, C_GREEN)
        l2 = F_SMALL.render(f"Route: {self.path_length} cells     R = new city     ESC = quit", True, C_TEXT_DIM)
        self.screen.blit(l1, (bx + (bw - l1.get_width())//2, by + 8))
        self.screen.blit(l2, (bx + (bw - l2.get_width())//2, by + 48))

    # ── Events + loop ─────────────────────────────────────────────────────────
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_ESCAPE: return False
                elif k == pygame.K_r:      self._reset()
                elif k == pygame.K_UP:     self.speed = min(12.0, self.speed + 1.0)
                elif k == pygame.K_DOWN:   self.speed = max(1.0,  self.speed - 1.0)
        return True

    def run(self):
        prev = pygame.time.get_ticks()
        while True:
            now = pygame.time.get_ticks()
            dt  = (now - prev) / 1000.0
            prev = now
            if not self.handle_events(): break
            self.update(dt)
            self.draw()
            self.clock.tick(60)
        pygame.quit()
