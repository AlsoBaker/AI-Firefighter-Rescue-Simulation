# ambulance.py  —  Phase 3: ambulance drives from burning building to nearest hospital.
#
# Changes from previous version:
#   - Accepts 10-tuple city_data (new: traffic_lights field)
#   - Ambulance respects traffic lights (slows to 5% speed on red)
#   - 12 traffic cars instead of 6

import pygame
import numpy as np

from city_map import generate_city, get_passable, CITY_COLS, CITY_ROWS, BLOCK_SIZE
from city_phase_base import (
    BaseCityPhase, TrafficLight, TrafficCar, CityFireParticle, city_astar,
    SCREEN_W, SCREEN_H, PANEL_W, CELL_SIZE, OFFSET_X, OFFSET_Y,
    C_BG, C_PANEL, C_PANEL_LINE, C_TEXT, C_TEXT_DIM, C_GOLD, C_GREEN,
    C_PATH_DONE, C_PATH_AHEAD, C_CAR, C_ROAD, C_INTER, C_FIRE_ST,
    C_HOSP, C_RIVER, C_BRIDGE, C_ROAD_CLOSURE,
    F_LARGE, F_MEDIUM, F_SMALL, F_TINY,
    _px, _centre, _load,
)

NUM_CARS = 20   # civilian traffic cars on the city map


class AmbulancePhase(BaseCityPhase):
    """
    Ambulance delivery phase.
    city_data  — 10-tuple from generate_city(); if None a fresh city is made.
    start_pos  — road cell (r,c) where ambulance begins; defaults to fire station.
    """

    def __init__(self, rescued_count=0, city_data=None, start_pos=None):
        self.rescued_count   = rescued_count
        self._init_city_data = city_data
        self._init_start_pos = start_pos
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
        pygame.display.set_caption("Ambulance Delivery Phase")
        self.clock  = pygame.time.Clock()
        self.speed  = 3.0
        self._reset()

    # ── Reset ─────────────────────────────────────────────────────────────────

    def _reset(self):
        if self._init_city_data is not None:
            result               = self._init_city_data
            self._init_city_data = None           # clear so R generates a new city
            (self.grid, self.fire_station, self.hospitals, self.hospital_blocks,
             self.fs_block, self.building_colors, self.road_names,
             self.river_row, self.block_sprites, tl_data) = result
            self.amb_start       = self._init_start_pos or self.fire_station
            self._init_start_pos = None
        else:
            rng    = np.random.default_rng()
            result = generate_city(seed=int(rng.integers(0, 99_999)))
            (self.grid, self.fire_station, self.hospitals, self.hospital_blocks,
             self.fs_block, self.building_colors, self.road_names,
             self.river_row, self.block_sprites, tl_data) = result
            self.amb_start = self.fire_station

        # Build TrafficLight objects from raw (r, c, phase) tuples
        self.traffic_lights = [TrafficLight(r, c, ph) for r, c, ph in tl_data]

        self._find_best_path()
        self._load_images()

        # Spawn 12 traffic cars on passable cells away from start/goal
        passable   = get_passable()
        road_cells = [(r, c)
                      for r in range(CITY_ROWS) for c in range(CITY_COLS)
                      if self.grid[r, c] in passable
                      and (r, c) not in {self.amb_start, self.target_hosp}]
        trng = np.random.default_rng()
        trng.shuffle(road_cells)
        colors    = C_CAR * 4
        self.cars = [TrafficCar(r, c, colors[i % len(C_CAR)], self.grid, trng, img_idx=i)
                     for i, (r, c) in enumerate(road_cells[:NUM_CARS])]

        # Ambulance state
        self.path_idx   = 0
        self.progress   = 0.0
        self.amb_pos    = _centre(*self.amb_start)
        self.trail      = []
        self.delivered  = False
        self.elapsed    = 0
        self.anim_frame = 0
        self.siren_r    = 0
        self.siren_grow = True

    # ── Pathfinding ───────────────────────────────────────────────────────────

    def _find_best_path(self):
        best_path, best_h = [], self.hospitals[0]
        for h in self.hospitals:
            p = city_astar(self.grid, self.amb_start, h)
            if p and (not best_path or len(p) < len(best_path)):
                best_path, best_h = p, h
        self.path        = [self.amb_start] + best_path
        self.target_hosp = best_h
        self.path_length = len(best_path)

    # ── Image loading ─────────────────────────────────────────────────────────

    def _load_images(self):
        self._load_city_images()
        self.img_amb = _load("ambulance.png", (CELL_SIZE, CELL_SIZE))

    # ── Traffic light check ───────────────────────────────────────────────────

    def _next_cell_red_light(self):
        """Return True if the next waypoint has a red traffic light."""
        if self.path_idx + 1 >= len(self.path):
            return False
        nr, nc = self.path[self.path_idx + 1]
        for tl in self.traffic_lights:
            if tl.r == nr and tl.c == nc and tl.is_red(self.anim_frame):
                return True
        return False

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

        # Traffic cars
        occupied = {(car.r, car.c) for car in self.cars}
        for car in self.cars:
            car.update(occupied - {(car.r, car.c)})

        if self.delivered:
            return
        if self.path_idx >= len(self.path) - 1:
            self.delivered = True
            return

        # Speed: respect red lights; slow behind cars
        red_light    = self._next_cell_red_light()
        next_cell    = self.path[self.path_idx + 1] if self.path_idx + 1 < len(self.path) else None
        car_blocking = next_cell and any((c.r, c.c) == next_cell for c in self.cars)

        if red_light:
            eff_speed = self.speed * 0.05   # nearly stopped at red
        elif car_blocking:
            eff_speed = self.speed * 0.4
        else:
            eff_speed = self.speed

        self.progress += eff_speed * dt

        while self.progress >= 1.0 and self.path_idx < len(self.path) - 1:
            self.progress -= 1.0
            self.path_idx += 1
            self.elapsed  += 1
            self.trail.append(_centre(*self.path[self.path_idx]))
            if len(self.trail) > 50:
                self.trail.pop(0)

        if self.path_idx >= len(self.path) - 1:
            self.delivered = True
            self.amb_pos   = _centre(*self.path[-1])
            return

        r0, c0   = self.path[self.path_idx]
        r1, c1   = self.path[self.path_idx + 1]
        cx0, cy0 = _centre(r0, c0)
        cx1, cy1 = _centre(r1, c1)
        t        = min(1.0, self.progress)
        self.amb_pos = (int(cx0 + (cx1-cx0)*t), int(cy0 + (cy1-cy0)*t))

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self):
        self.screen.fill(C_BG)
        self._draw_city()
        self._draw_traffic_lights()
        self._draw_building_sprites()
        self._draw_hospital_blocks(target_hosp=self.target_hosp)
        self._draw_trail()
        self._draw_path()
        self._draw_cars()
        self._draw_siren()
        self._draw_ambulance()
        self._draw_panel()
        if self.delivered:
            self._draw_banner()
        pygame.display.flip()

    def _draw_trail(self):
        if len(self.trail) < 2: return
        surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        n = len(self.trail)
        for i in range(1, n):
            alpha = int(30 + 150 * i / n)
            pygame.draw.line(surf, (200, 200, 200, alpha),
                             self.trail[i-1], self.trail[i], 2)
        self.screen.blit(surf, (0, 0))

    def _draw_path(self):
        if len(self.path) < 2: return
        for i in range(min(self.path_idx, len(self.path)-1)):
            pygame.draw.line(self.screen, C_PATH_DONE,
                             _centre(*self.path[i]), _centre(*self.path[i+1]), 2)
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
        col = (220,50,50) if (self.anim_frame//30)%2==0 else (50,80,220)
        r   = self.siren_r
        if r > 0:
            surf = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*col, max(0, 120-r*2)), (r+1, r+1), r, 2)
            self.screen.blit(surf, (ax-r-1, ay-r-1))

    def _draw_ambulance(self):
        ax, ay = self.amb_pos
        hs     = CELL_SIZE // 2
        if self.img_amb:
            self.screen.blit(self.img_amb, (ax-hs, ay-hs))
        else:
            pygame.draw.rect(self.screen, (230, 230, 230),
                             (ax-hs, ay-hs, CELL_SIZE, CELL_SIZE))

    def _draw_panel(self):
        pygame.draw.rect(self.screen, C_PANEL, (0, 0, PANEL_W, SCREEN_H))
        pygame.draw.line(self.screen, C_PANEL_LINE, (PANEL_W,0), (PANEL_W,SCREEN_H), 1)
        y = 20

        def txt(text, font, color, cx=False):
            nonlocal y
            s  = font.render(text, True, color)
            xp = (PANEL_W - s.get_width())//2 if cx else 14
            self.screen.blit(s, (xp, y))
            y += s.get_height() + 4

        def div():
            nonlocal y
            y += 6
            pygame.draw.line(self.screen, C_PANEL_LINE, (14,y), (PANEL_W-14,y), 1)
            y += 10

        txt("AMBULANCE", F_LARGE(), C_TEXT, cx=True)
        txt("DELIVERY",  F_LARGE(), C_TEXT, cx=True)
        div()

        status = "DELIVERED!" if self.delivered else "EN ROUTE..."
        txt(status, F_MEDIUM(), C_GREEN if self.delivered else C_GOLD, cx=True)
        y += 6

        for label, val in [
            ("Civilians rescued", str(self.rescued_count)),
            ("Route distance",    f"{self.path_length} cells"),
            ("Steps taken",       str(self.elapsed)),
            ("Hospitals on map",  str(len(self.hospitals))),
            ("Traffic lights",    str(len(self.traffic_lights))),
            ("Speed",             f"{self.speed:.1f}x"),
        ]:
            sl = F_SMALL().render(f"{label}:", True, C_TEXT_DIM)
            sv = F_SMALL().render(val,          True, C_TEXT)
            self.screen.blit(sl, (14, y))
            self.screen.blit(sv, (PANEL_W - sv.get_width() - 14, y))
            y += 22

        div()
        txt("Legend", F_SMALL(), C_TEXT_DIM)
        for col, lbl in [
            (C_ROAD,         "Road"),
            (C_INTER,        "Intersection"),
            ((52,52,68),     "Building"),
            (C_FIRE_ST,      "Fire station"),
            (C_HOSP,         "Hospital (target)"),
            (C_ROAD_CLOSURE, "Road closure"),
            (C_RIVER,        "River (impassable)"),
            (C_BRIDGE,       "Bridge (crossable)"),
            ((40,200,40),    "Traffic light – green"),
            ((220,40,40),    "Traffic light – red"),
            (C_PATH_DONE,    "Travelled path"),
            (C_PATH_AHEAD,   "Upcoming path"),
        ]:
            pygame.draw.rect(self.screen, col, (14, y+3, 11, 11))
            self.screen.blit(F_TINY().render(lbl, True, C_TEXT_DIM), (30, y+1))
            y += 17

        div()
        for line in ["UP/DN  Speed", "R      New Simulation", "ESC    Quit"]:
            self.screen.blit(F_TINY().render(line, True, C_TEXT_DIM), (14, y))
            y += 16

    def _draw_banner(self):
        if self.anim_frame % 60 >= 45: return
        bw, bh = 540, 72
        bx = PANEL_W + (SCREEN_W - PANEL_W - bw)//2
        by = SCREEN_H//2 - bh//2
        pygame.draw.rect(self.screen, (16,50,24),  (bx,by,bw,bh), border_radius=10)
        pygame.draw.rect(self.screen, C_GREEN,      (bx,by,bw,bh), 2, border_radius=10)
        l1 = F_LARGE().render(f"Delivered!  {self.rescued_count} civilians safe", True, C_GREEN)
        l2 = F_SMALL().render(
            f"Route: {self.path_length} cells     R = New Simulation     ESC = quit",
            True, C_TEXT_DIM)
        self.screen.blit(l1, (bx+(bw-l1.get_width())//2, by+8))
        self.screen.blit(l2, (bx+(bw-l2.get_width())//2, by+48))

    # ── Events + loop ─────────────────────────────────────────────────────────

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_ESCAPE: return False
                elif k == pygame.K_r:      return "restart"
                elif k == pygame.K_UP:     self.speed = min(12.0, self.speed+1.0)
                elif k == pygame.K_DOWN:   self.speed = max(1.0,  self.speed-1.0)
        return True

    def run(self):
        prev = pygame.time.get_ticks()
        while True:
            now  = pygame.time.get_ticks()
            dt   = (now - prev) / 1000.0
            prev = now
            result = self.handle_events()
            if result == "restart":
                return "restart"
            if not result:
                return None
            self.update(dt)
            self.draw()
            self.clock.tick(60)