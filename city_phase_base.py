# city_phase_base.py
# Shared constants, helpers, and base rendering for all city-map phases.

import heapq, os, math, pygame
import numpy as np

from city_map import (
    generate_city, get_passable,
    ROAD, BUILDING, INTERSECTION, FIRE_STATION, HOSPITAL,
    ROAD_CLOSURE, RIVER, BRIDGE,
    CITY_COLS, CITY_ROWS, BLOCK_SIZE,
    TL_CYCLE, TL_GREEN,
)

pygame.init()

_info    = pygame.display.Info()
SCREEN_W = _info.current_w
SCREEN_H = _info.current_h

PANEL_W   = 280
MAP_W     = SCREEN_W - PANEL_W
CELL_SIZE = min(MAP_W // CITY_COLS, SCREEN_H // CITY_ROWS)
OFFSET_X  = PANEL_W + (MAP_W  - CELL_SIZE * CITY_COLS) // 2
OFFSET_Y  = (SCREEN_H - CELL_SIZE * CITY_ROWS) // 2

ASSETS = "assets"

# ── Colours ───────────────────────────────────────────────────────────────────
C_BG            = (12, 14, 18)
C_ROAD          = (68, 70, 78)
C_ROAD_LINE     = (90, 88, 50)
C_INTER         = (78, 76, 58)
C_CROSS_WALK    = (200, 200, 195)
C_ROAD_CLOSURE  = (210, 140, 20)
C_CLOSURE_STRIP = (40, 40, 40)
C_RIVER         = (30, 70, 130)
C_RIVER_SHINE   = (50, 100, 170)
C_BRIDGE        = (120, 100, 70)
C_BRIDGE_PLANK  = (100, 82, 55)
C_FIRE_ST       = (170, 70, 20)
C_FIRE_ST_TXT   = (255, 210, 170)
C_HOSP          = (30, 110, 55)
C_HOSP_TARGET   = (255, 240, 80)
C_PATH_DONE     = (140, 140, 140)
C_PATH_AHEAD    = (255, 210, 40)
C_PANEL         = (16, 18, 24)
C_PANEL_LINE    = (40, 42, 52)
C_TEXT          = (210, 212, 220)
C_TEXT_DIM      = (100, 104, 116)
C_GOLD          = (255, 200, 50)
C_GREEN         = (50, 200, 80)
C_NAME_TXT      = (160, 158, 120)
C_CAR           = [(220, 60, 60), (60, 140, 220), (240, 200, 50),
                   (80, 200, 100), (200, 80, 200), (220, 140, 50)]

# Fonts are created lazily so they survive pygame.quit() + reinit cycles.
# (Module-level Font objects become invalid after pygame.quit().)
_fonts = {}

def _font(size):
    """Return a cached pygame.Font of the given size, creating it if needed."""
    if size not in _fonts:
        pygame.font.init()
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]

def _invalidate_fonts():
    """Call this after pygame.quit() so fonts are recreated on next use."""
    _fonts.clear()

# Convenience accessors — use these everywhere instead of bare F_* variables.
def F_LARGE():  return _font(42)
def F_MEDIUM(): return _font(28)
def F_SMALL():  return _font(22)
def F_TINY():   return _font(15)


# ── Helpers ───────────────────────────────────────────────────────────────────
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
    except Exception:
        return None


# ── City A* ───────────────────────────────────────────────────────────────────
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
            if ng < g.get((nr, nc), 1e9):
                came_from[(nr, nc)] = cur
                g[(nr, nc)] = ng
                heapq.heappush(open_set,
                               (ng + abs(nr-goal[0]) + abs(nc-goal[1]), (nr, nc)))
    return []


# ── Traffic light ─────────────────────────────────────────────────────────────
class TrafficLight:
    """
    Traffic light at a city intersection.
    Cycle: TL_GREEN frames green → (TL_CYCLE - TL_GREEN) frames red.
    phase_offset staggers adjacent lights so they don't all change at once.
    """
    def __init__(self, r, c, phase_offset=0):
        self.r            = r
        self.c            = c
        self.phase_offset = phase_offset

    def is_red(self, frame):
        return (frame + self.phase_offset) % TL_CYCLE >= TL_GREEN

    def draw(self, screen, frame):
        x, y = _px(self.r, self.c)
        cs   = CELL_SIZE
        if cs < 6:
            return
        red   = self.is_red(frame)
        color = (220, 40, 40) if red else (40, 200, 40)
        cx = x + cs - max(3, cs // 4)
        cy = y + max(3, cs // 4)
        r  = max(2, cs // 6)
        pygame.draw.circle(screen, (20, 20, 20), (cx, cy), r + 1)
        pygame.draw.circle(screen, color,        (cx, cy), r)


# ── Traffic car ───────────────────────────────────────────────────────────────
# Car images loaded once at module level (car1.png … car10.png in assets/).
# Falls back to coloured rectangles if no images are found.
_car_images = None

def _get_car_images():
    """Lazy-load car sprites. Called on first TrafficCar draw."""
    global _car_images
    if _car_images is None:
        imgs = []
        for i in range(1, 11):
            img = _load(f"car{i}.png", (CELL_SIZE, CELL_SIZE))
            if img is not None:
                imgs.append(img)
        _car_images = imgs   # empty list = no images available
    return _car_images


class TrafficCar:
    DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    def __init__(self, r, c, color, grid, rng, img_idx=0):
        self.r, self.c = r, c
        self.color     = color
        self.img_idx   = img_idx   # index into _car_images (cycles if fewer images than cars)
        self.dir       = list(rng.choice(self.DIRS))
        self.timer     = 0
        self.interval  = int(rng.integers(30, 60))
        self._grid     = grid
        self._passable = get_passable()

    def update(self, occupied):
        self.timer += 1
        if self.timer < self.interval: return
        self.timer = 0
        nr = self.r + self.dir[0]
        nc = self.c + self.dir[1]
        if (0 <= nr < CITY_ROWS and 0 <= nc < CITY_COLS
                and self._grid[nr, nc] in self._passable
                and (nr, nc) not in occupied):
            self.r, self.c = nr, nc
        else:
            self.dir = [-self.dir[0], -self.dir[1]]

    def draw(self, screen):
        x, y  = _px(self.r, self.c)
        imgs  = _get_car_images()
        if imgs:
            img = imgs[self.img_idx % len(imgs)]
            screen.blit(img, (x, y))
        else:
            pad = CELL_SIZE // 5
            pygame.draw.rect(screen, self.color,
                             (x+pad, y+pad, CELL_SIZE-pad*2, CELL_SIZE-pad*2),
                             border_radius=2)


# ── City fire particles ───────────────────────────────────────────────────────
class CityFireParticle:
    def __init__(self, x, y):
        self.x     = x + np.random.uniform(-6, 6)
        self.y     = y + np.random.uniform(-4, 4)
        self.vx    = np.random.uniform(-0.7, 0.7)
        self.vy    = np.random.uniform(-2.2, -0.9)
        self.life  = 255
        self.decay = np.random.uniform(4, 9)

    def update(self):
        self.x += self.vx; self.y += self.vy; self.life -= self.decay
        return self.life > 0

    def draw(self, screen):
        if self.life > 0:
            pygame.draw.circle(screen, (255, min(255, int(self.life)//2), 0),
                               (int(self.x), int(self.y)), 2)


# ── Base city renderer ────────────────────────────────────────────────────────
class BaseCityPhase:
    """
    Mixin providing shared city-drawing for FiretruckPhase and AmbulancePhase.

    Required subclass attributes:
        self.screen, self.grid, self.building_colors, self.road_names,
        self.block_sprites, self.hospital_blocks, self.hospitals,
        self.img_buildings, self.img_firestation, self.img_hosp,
        self.block_px, self.anim_frame, self.traffic_lights (list[TrafficLight])
    """

    def _load_city_images(self):
        cs       = CELL_SIZE
        block_px = (BLOCK_SIZE - 1) * cs
        self.block_px        = block_px
        self.img_hosp        = _load("hospital.png",    (block_px, block_px))
        self.img_firestation = _load("firestation.png", (block_px, block_px))
        raw = [_load(f"building{i+1}.png", (block_px, block_px)) for i in range(10)]
        self.img_buildings = [img for img in raw if img is not None] or None

    def _draw_city(self):
        cs = CELL_SIZE
        for r in range(CITY_ROWS):
            for c in range(CITY_COLS):
                x, y = _px(r, c)
                cell = self.grid[r, c]

                if cell == BUILDING:
                    col = self.building_colors.get((r, c), (50, 50, 64))
                    pygame.draw.rect(self.screen, col, (x, y, cs, cs))

                elif cell == ROAD:
                    pygame.draw.rect(self.screen, C_ROAD, (x, y, cs, cs))
                    if cs >= 10:
                        my_  = y + cs // 2
                        dash = max(3, cs // 4)
                        for i in range(0, cs, dash * 2):
                            pygame.draw.line(self.screen, C_ROAD_LINE,
                                             (x+i, my_), (x+i+dash, my_), 1)

                elif cell == INTERSECTION:
                    pygame.draw.rect(self.screen, C_INTER, (x, y, cs, cs))
                    sw = max(2, cs // 5)
                    for i in range(0, cs, sw * 2):
                        pygame.draw.rect(self.screen, C_CROSS_WALK, (x+i, y, sw, 3))
                        pygame.draw.rect(self.screen, C_CROSS_WALK, (x+i, y+cs-3, sw, 3))
                    name = self.road_names.get((r, c), "")
                    if name and cs >= 14:
                        for pi, part in enumerate(name.split(" / ")[:2]):
                            surf = F_TINY().render(part, True, C_NAME_TXT)
                            if surf.get_width() <= cs:
                                self.screen.blit(surf, (x+1, y+1+pi*8))

                elif cell == ROAD_CLOSURE:
                    # Amber background + dark diagonal stripes = construction barrier
                    pygame.draw.rect(self.screen, C_ROAD_CLOSURE, (x, y, cs, cs))
                    stripe_w = max(2, cs // 4)
                    for offset in range(-cs, cs * 2, stripe_w * 2):
                        pts = [(x + offset + dy, y + dy)
                               for dy in range(cs + 1)
                               if 0 <= offset + dy < cs]
                        if len(pts) >= 2:
                            pygame.draw.lines(self.screen, C_CLOSURE_STRIP,
                                              False, pts, max(1, stripe_w // 2))
                    if cs >= 12:
                        lbl = F_TINY().render("X", True, (30, 30, 30))
                        self.screen.blit(lbl, (x + (cs - lbl.get_width()) // 2,
                                               y + (cs - lbl.get_height()) // 2))

                elif cell == RIVER:
                    pygame.draw.rect(self.screen, C_RIVER, (x, y, cs, cs))
                    sy = y + cs // 2
                    for sx in range(x, x + cs, 4):
                        pygame.draw.line(self.screen, C_RIVER_SHINE,
                                         (sx, sy), (sx+2, sy), 1)

                elif cell == BRIDGE:
                    pygame.draw.rect(self.screen, C_BRIDGE, (x, y, cs, cs))
                    for bxi in range(x+2, x+cs-1, max(3, cs//4)):
                        pygame.draw.line(self.screen, C_BRIDGE_PLANK,
                                         (bxi, y), (bxi, y+cs), 1)

                elif cell == FIRE_STATION:
                    pygame.draw.rect(self.screen, C_FIRE_ST, (x, y, cs, cs))
                    lbl = F_TINY().render("FS", True, C_FIRE_ST_TXT)
                    self.screen.blit(lbl, (x+1, y+1))

                elif cell == HOSPITAL:
                    pygame.draw.rect(self.screen, C_HOSP, (x, y, cs, cs))

    def _draw_traffic_lights(self):
        for tl in getattr(self, 'traffic_lights', []):
            tl.draw(self.screen, self.anim_frame)

    def _draw_building_sprites(self):
        ext_rows = sorted(range(0, CITY_ROWS, BLOCK_SIZE)) + [CITY_ROWS]
        ext_cols = sorted(range(0, CITY_COLS, BLOCK_SIZE)) + [CITY_COLS]
        imgs   = self.img_buildings
        n_imgs = len(imgs) if imgs else 0
        for bi, r0 in enumerate(ext_rows[:-1]):
            for ci, c0 in enumerate(ext_cols[:-1]):
                idx  = self.block_sprites.get((bi, ci), 0)
                x, y = _px(r0+1, c0+1)
                if idx == -1:
                    continue
                elif idx == -2:
                    if self.img_firestation:
                        self.screen.blit(self.img_firestation, (x, y))
                elif n_imgs > 0:
                    self.screen.blit(imgs[idx % n_imgs], (x, y))

    def _draw_hospital_blocks(self, target_hosp=None):
        ext_rows = sorted(range(0, CITY_ROWS, BLOCK_SIZE)) + [CITY_ROWS]
        ext_cols = sorted(range(0, CITY_COLS, BLOCK_SIZE)) + [CITY_COLS]

        target_block = None
        if target_hosp is not None:
            for i, hpos in enumerate(self.hospitals):
                if hpos == target_hosp and i < len(self.hospital_blocks):
                    target_block = tuple(self.hospital_blocks[i])
                    break

        for bi, ci in self.hospital_blocks:
            r0   = ext_rows[bi]; c0 = ext_cols[ci]
            x, y = _px(r0+1, c0+1)
            bpx  = self.block_px
            is_target = (target_block is not None and (bi, ci) == target_block)
            if is_target:
                pygame.draw.rect(self.screen, C_HOSP_TARGET,
                                 (x-3, y-3, bpx+6, bpx+6), 3)
            if self.img_hosp:
                if not is_target and target_block is not None:
                    dim = self.img_hosp.copy(); dim.set_alpha(160)
                    self.screen.blit(dim, (x, y))
                else:
                    self.screen.blit(self.img_hosp, (x, y))
