# firetruck.py  —  Phase 1: player clicks a building, firetruck drives to it, cutscene plays.
#
# The firetruck is an emergency vehicle — it ignores traffic lights (drives through red).
# Traffic lights are still drawn for visual consistency with the ambulance phase.

import math, pygame
import numpy as np

from city_map import (
    generate_city, BUILDING,
    CITY_COLS, CITY_ROWS, BLOCK_SIZE,
)
from city_phase_base import (
    BaseCityPhase, TrafficLight, CityFireParticle, city_astar,
    SCREEN_W, SCREEN_H, PANEL_W, CELL_SIZE, OFFSET_X, OFFSET_Y,
    C_BG, C_PANEL, C_PANEL_LINE, C_TEXT, C_TEXT_DIM, C_GOLD,
    C_PATH_DONE, C_PATH_AHEAD,
    F_LARGE, F_MEDIUM, F_SMALL, F_TINY,
    _px, _centre, _load,
)

C_FIRE_BORDER = (255, 50, 0)
C_FIRETRUCK   = (210, 50, 30)   # fallback rect colour when no sprite


class FiretruckPhase(BaseCityPhase):
    """
    City overview phase.
    States: 'selecting' → 'driving' → 'cutscene' → 'done'
    run() returns (city_data_10tuple, burning_road_pos) or None if player quit.
    """

    CUTSCENE_DURATION = 3.5

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
        pygame.display.set_caption("Emergency Dispatch — Click a building to report a fire")
        self.clock  = pygame.time.Clock()
        self._reset()

    # ── Reset / init ──────────────────────────────────────────────────────────

    def _reset(self):
        rng    = np.random.default_rng()
        result = generate_city(seed=int(rng.integers(0, 99_999)))
        # 10-tuple unpack
        (self.grid, self.fire_station, self.hospitals, self.hospital_blocks,
         self.fs_block, self.building_colors, self.road_names,
         self.river_row, self.block_sprites, tl_data) = result
        self.city_data = result          # stored to pass back to main.py

        # Build TrafficLight objects (drawn for visual parity with ambulance phase)
        self.traffic_lights = [TrafficLight(r, c, ph) for r, c, ph in tl_data]

        self._load_city_images()
        self.img_firetruck = _load("firetruck.png", (CELL_SIZE, CELL_SIZE))

        # Block boundary lists for hover / geometry helpers
        self._ext_rows  = sorted(range(0, CITY_ROWS, BLOCK_SIZE)) + [CITY_ROWS]
        self._ext_cols  = sorted(range(0, CITY_COLS, BLOCK_SIZE)) + [CITY_COLS]
        self._road_rows = list(range(0, CITY_ROWS, BLOCK_SIZE))
        self._road_cols = list(range(0, CITY_COLS, BLOCK_SIZE))

        # Phase state
        self.state            = 'selecting'
        self.burning_block    = None
        self.burning_road_pos = None
        self.hovered_block    = None

        # Firetruck movement
        self.path      = []
        self.path_idx  = 0
        self.progress  = 0.0
        self.speed     = 4.0
        self.ft_pos    = _centre(*self.fire_station)

        # Cutscene
        self.cutscene_t = 0.0

        # Animation + particles
        self.anim_frame     = 0
        self.fire_particles = []

    # ── Block geometry helpers ────────────────────────────────────────────────

    def _pixel_to_cell(self, mx, my):
        c = (mx - OFFSET_X) // CELL_SIZE
        r = (my - OFFSET_Y) // CELL_SIZE
        return (r, c) if (0 <= r < CITY_ROWS and 0 <= c < CITY_COLS) else None

    def _cell_to_block(self, r, c):
        er, ec = self._ext_rows, self._ext_cols
        for bi in range(len(er)-1):
            for ci in range(len(ec)-1):
                if er[bi] < r < er[bi+1] and ec[ci] < c < ec[ci+1]:
                    return bi, ci
        return None

    def _block_road_pos(self, bi, ci):
        rr, rc = self._road_rows, self._road_cols
        return rr[min(bi, len(rr)-1)], rc[min(ci, len(rc)-1)]

    def _block_centre_px(self, bi, ci):
        er, ec = self._ext_rows, self._ext_cols
        r_mid  = (er[bi] + 1 + er[bi+1]) // 2
        c_mid  = (ec[ci] + 1 + ec[ci+1]) // 2
        return _centre(r_mid, c_mid)

    def _block_topleft_px(self, bi, ci):
        return _px(self._ext_rows[bi]+1, self._ext_cols[ci]+1)

    def _block_pixel_size(self, bi, ci):
        er, ec = self._ext_rows, self._ext_cols
        w = (ec[ci+1] - ec[ci] - 1) * CELL_SIZE
        h = (er[bi+1] - er[bi] - 1) * CELL_SIZE
        return w, h

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_events(self):
        mx, my = pygame.mouse.get_pos()

        if self.state == 'selecting':
            rc = self._pixel_to_cell(mx, my)
            if rc:
                r, c = rc
                if self.grid[r, c] == BUILDING:
                    blk = self._cell_to_block(r, c)
                    if blk:
                        bi, ci = blk
                        if self.block_sprites.get((bi, ci), 0) >= 0:
                            self.hovered_block = blk
                        else:
                            self.hovered_block = None
                    else:
                        self.hovered_block = None
                else:
                    self.hovered_block = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_ESCAPE:
                    return False
                elif k == pygame.K_r:
                    self._reset()
                elif k == pygame.K_UP   and self.state == 'driving':
                    self.speed = min(12.0, self.speed + 1.0)
                elif k == pygame.K_DOWN and self.state == 'driving':
                    self.speed = max(1.0,  self.speed - 1.0)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == 'selecting' and self.hovered_block:
                    self._select_building(self.hovered_block)

        return True

    def _select_building(self, block):
        bi, ci   = block
        road_pos = self._block_road_pos(bi, ci)
        path     = city_astar(self.grid, self.fire_station, road_pos)
        if not path:
            return   # unreachable — silently ignore

        self.burning_block    = block
        self.burning_road_pos = road_pos
        self.hovered_block    = None
        self.path      = [self.fire_station] + path
        self.path_idx  = 0
        self.progress  = 0.0
        self.ft_pos    = _centre(*self.fire_station)
        self.state     = 'driving'

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self.anim_frame += 1

        if self.state == 'driving':
            self._update_drive(dt)
        elif self.state == 'cutscene':
            self.cutscene_t += dt
            if self.cutscene_t >= self.CUTSCENE_DURATION:
                self.state = 'done'

        if self.burning_block and self.state in ('driving', 'cutscene'):
            self._spawn_fire_particles()
        self.fire_particles = [p for p in self.fire_particles if p.update()]

    def _update_drive(self, dt):
        # Firetruck ignores traffic lights — it's an emergency vehicle.
        if self.path_idx >= len(self.path) - 1:
            self.ft_pos     = _centre(*self.path[-1])
            self.state      = 'cutscene'
            self.cutscene_t = 0.0
            return

        self.progress += self.speed * dt

        while self.progress >= 1.0 and self.path_idx < len(self.path) - 1:
            self.progress -= 1.0
            self.path_idx += 1

        if self.path_idx >= len(self.path) - 1:
            self.ft_pos     = _centre(*self.path[-1])
            self.state      = 'cutscene'
            self.cutscene_t = 0.0
            return

        r0, c0   = self.path[self.path_idx]
        r1, c1   = self.path[self.path_idx + 1]
        cx0, cy0 = _centre(r0, c0)
        cx1, cy1 = _centre(r1, c1)
        t = min(1.0, self.progress)
        self.ft_pos = (int(cx0 + (cx1-cx0)*t), int(cy0 + (cy1-cy0)*t))

    def _spawn_fire_particles(self):
        bi, ci    = self.burning_block
        bx, by    = self._block_topleft_px(bi, ci)
        bw, _     = self._block_pixel_size(bi, ci)
        if bw > 0 and np.random.random() < 0.45:
            px = bx + np.random.randint(0, bw)
            self.fire_particles.append(CityFireParticle(px, by))

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self):
        if self.state == 'cutscene':
            self._draw_cutscene()
        else:
            self.screen.fill(C_BG)
            self._draw_city()
            self._draw_traffic_lights()       # visual parity; firetruck ignores them
            self._draw_building_sprites()
            self._draw_hospital_blocks()

            if self.burning_block:
                self._draw_burning_building()
            for p in self.fire_particles:
                p.draw(self.screen)
            if self.hovered_block and self.state == 'selecting':
                self._draw_hover_highlight()
            if self.state == 'driving':
                self._draw_ft_path()
                self._draw_firetruck()

            self._draw_panel()

        pygame.display.flip()

    def _draw_hover_highlight(self):
        bi, ci = self.hovered_block
        bx, by = self._block_topleft_px(bi, ci)
        bpx    = self.block_px
        pulse  = abs(math.sin(self.anim_frame * 0.12))
        col    = (255, int(180 + 75 * pulse), 0)
        pygame.draw.rect(self.screen, col, (bx-3, by-3, bpx+6, bpx+6), 3, border_radius=2)
        surf = pygame.Surface((bpx, bpx), pygame.SRCALPHA)
        surf.fill((255, 200, 0, 40))
        self.screen.blit(surf, (bx, by))

    def _draw_burning_building(self):
        bi, ci = self.burning_block
        bx, by = self._block_topleft_px(bi, ci)
        bpx    = self.block_px
        alpha  = int(70 + 90 * abs(math.sin(self.anim_frame * 0.08)))
        surf   = pygame.Surface((bpx, bpx), pygame.SRCALPHA)
        surf.fill((255, 60, 0, alpha))
        self.screen.blit(surf, (bx, by))
        pygame.draw.rect(self.screen, C_FIRE_BORDER, (bx-2, by-2, bpx+4, bpx+4), 3)

    def _draw_ft_path(self):
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

    def _draw_firetruck(self):
        ax, ay = self.ft_pos
        hs     = CELL_SIZE // 2
        if self.img_firetruck:
            self.screen.blit(self.img_firetruck, (ax-hs, ay-hs))
        else:
            pygame.draw.rect(self.screen, C_FIRETRUCK,
                             (ax-hs, ay-hs, CELL_SIZE, CELL_SIZE), border_radius=3)

    # ── Cutscene ──────────────────────────────────────────────────────────────

    def _render_to_surface(self):
        surf        = pygame.Surface((SCREEN_W, SCREEN_H))
        surf.fill(C_BG)
        orig        = self.screen
        self.screen = surf
        self._draw_city()
        self._draw_traffic_lights()
        self._draw_building_sprites()
        self._draw_hospital_blocks()
        if self.burning_block:
            self._draw_burning_building()
        for p in self.fire_particles:
            p.draw(self.screen)
        self.screen = orig
        return surf

    def _draw_cutscene(self):
        t = self.cutscene_t
        D = self.CUTSCENE_DURATION

        city_surf = self._render_to_surface()
        zoom      = 1.0 + min(t / 1.5, 1.0) * 2.5

        cx, cy = self._block_centre_px(*self.burning_block)
        w  = max(1, int(SCREEN_W / zoom))
        h  = max(1, int(SCREEN_H / zoom))
        sx = max(0, min(SCREEN_W - w, cx - w // 2))
        sy = max(0, min(SCREEN_H - h, cy - h // 2))

        try:
            cropped = city_surf.subsurface(pygame.Rect(sx, sy, w, h))
            scaled  = pygame.transform.scale(cropped, (SCREEN_W, SCREEN_H))
            self.screen.blit(scaled, (0, 0))
        except Exception:
            self.screen.blit(city_surf, (0, 0))

        if 1.5 <= t <= 2.0:
            ratio = 1.0 - (t - 1.5) / 0.5
            fs    = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            fs.fill((255, 160, 50, int(255 * ratio)))
            self.screen.blit(fs, (0, 0))

        if t >= 2.0:
            alpha    = min(255, int((t - 2.0) / 0.35 * 255))
            box_h    = 72
            box_surf = pygame.Surface((SCREEN_W, box_h), pygame.SRCALPHA)
            box_surf.fill((0, 0, 0, 190))
            txt = F_LARGE().render("ENTERING BUILDING", True, (255, 220, 80))
            box_surf.blit(txt, ((SCREEN_W - txt.get_width())//2,
                                (box_h - txt.get_height())//2))
            box_surf.set_alpha(alpha)
            self.screen.blit(box_surf, (0, SCREEN_H//2 - box_h//2))

        fade_start = D - 0.6
        if t >= fade_start:
            fade_alpha = min(255, int((t - fade_start) / 0.6 * 255))
            fs = pygame.Surface((SCREEN_W, SCREEN_H))
            fs.fill((0, 0, 0))
            fs.set_alpha(fade_alpha)
            self.screen.blit(fs, (0, 0))

    # ── Panel ─────────────────────────────────────────────────────────────────

    def _draw_panel(self):
        pygame.draw.rect(self.screen, C_PANEL, (0, 0, PANEL_W, SCREEN_H))
        pygame.draw.line(self.screen, C_PANEL_LINE,
                         (PANEL_W, 0), (PANEL_W, SCREEN_H), 1)
        y = 20

        def row(text, font, color, center=False):
            nonlocal y
            s  = font.render(text, True, color)
            xp = (PANEL_W - s.get_width())//2 if center else 14
            self.screen.blit(s, (xp, y))
            y += s.get_height() + 5

        def div():
            nonlocal y
            y += 6
            pygame.draw.line(self.screen, C_PANEL_LINE, (14,y), (PANEL_W-14,y), 1)
            y += 10

        row("EMERGENCY",  F_LARGE(), C_TEXT, center=True)
        row("DISPATCH",   F_LARGE(), C_TEXT, center=True)
        div()

        if self.state == 'selecting':
            row("AWAITING CALL", F_MEDIUM(), C_GOLD, center=True)
            y += 8
            for line in ["Click any building", "on the map to", "report a fire."]:
                row(line, F_SMALL(), C_TEXT_DIM, center=True)
        elif self.state == 'driving':
            row("EN ROUTE", F_MEDIUM(), (255, 120, 30), center=True)
            y += 6
            remaining = max(0, len(self.path) - self.path_idx - 1)
            for label, val in [("Distance left", f"{remaining} cells"),
                                ("Speed", f"{self.speed:.0f}x")]:
                sl = F_SMALL().render(f"{label}:", True, C_TEXT_DIM)
                sv = F_SMALL().render(val, True, C_TEXT)
                self.screen.blit(sl, (14, y))
                self.screen.blit(sv, (PANEL_W - sv.get_width() - 14, y))
                y += 22

        div()
        for line in (["UP/DN  Speed"] if self.state == 'driving' else []) + \
                    ["R      New city", "ESC    Quit"]:
            self.screen.blit(F_TINY().render(line, True, C_TEXT_DIM), (14, y))
            y += 16

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        """Returns (city_data, burning_road_pos) or None on quit."""
        prev = pygame.time.get_ticks()
        while True:
            now  = pygame.time.get_ticks()
            dt   = (now - prev) / 1000.0
            prev = now

            if not self.handle_events():
                return None

            self.update(dt)
            self.draw()

            if self.state == 'done':
                return self.city_data, self.burning_road_pos

            self.clock.tick(60)
