# visualize.py

import os
import numpy as np
import pygame

from config import *
from fire import spread_fire
from firefighter import move_firefighter, initialize_firefighters, get_firefighter_stats
from health import HealthSystem
from floors import FloorManager
from metrics import SimulationMetrics
from leaderboard import save_score, get_top_scores
from ambulance import AmbulancePhase

pygame.init()

_info     = pygame.display.Info()
SCREEN_W  = _info.current_w
SCREEN_H  = _info.current_h

PANEL_W   = 270
TAB_H     = 44
MARGIN    = 16

_avail_w  = SCREEN_W - PANEL_W - MARGIN * 3
_avail_h  = SCREEN_H - TAB_H   - MARGIN * 3
CELL_SIZE = max(28, min(52, min(_avail_w // COLS, _avail_h // ROWS)))

GRID_W    = COLS * CELL_SIZE
GRID_H    = ROWS * CELL_SIZE
GRID_X    = PANEL_W + MARGIN * 2
GRID_Y    = TAB_H   + MARGIN * 2

# --- Colours ---
C_BG         = (18, 18, 18)
C_PANEL      = (24, 24, 24)
C_PANEL_LINE = (45, 45, 45)
C_GRID       = (35, 35, 35)
C_EMPTY      = (42, 42, 42)
C_OBSTACLE   = (65, 65, 65)
C_FIRE       = [(255, 48, 48), (255, 110, 0), (255, 165, 0)]
C_STAIR_BG   = (30, 55, 80)
C_HOSP_BG    = (35, 35, 55)
C_PERSON_BG  = (30, 70, 30)
C_DANGER_BG  = (80, 40, 10)
C_FF_BG      = (70, 50, 10)
C_TEXT       = (215, 215, 215)
C_TEXT_DIM   = (110, 110, 110)
C_TAB_ON     = (55, 80, 120)
C_TAB_OFF    = (32, 32, 32)
C_HP_HIGH    = (45, 200, 45)
C_HP_MED     = (225, 165, 20)
C_HP_LOW     = (215, 55, 55)
C_WATER_HIGH = (30, 140, 255)
C_WATER_LOW  = (80, 80, 180)
C_BAR_BG     = (28, 28, 28)
C_GOLD       = (255, 200, 50)

_viz_fonts = {}

def _font(size):
    """Return a cached pygame.Font of the given size, creating it if needed."""
    if size not in _viz_fonts:
        pygame.font.init()
        _viz_fonts[size] = pygame.font.Font(None, size)
    return _viz_fonts[size]

def _invalidate_fonts():
    """Call after pygame.quit() so fonts are recreated on next use."""
    _viz_fonts.clear()

def F_LARGE():  return _font(38)
def F_MEDIUM(): return _font(26)
def F_SMALL():  return _font(20)
def F_TINY():   return _font(15)

ASSETS = "assets"


def _load(filename, size):
    path = os.path.join(ASSETS, filename)
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size)
    except Exception as exc:
        print(f"[warn] could not load {path}: {exc}")
        return None


def _tinted(surface, rgba):
    if surface is None:
        return None
    copy  = surface.copy()
    layer = pygame.Surface(copy.get_size(), pygame.SRCALPHA)
    layer.fill(rgba)
    copy.blit(layer, (0, 0))
    return copy


class FireParticle:
    def __init__(self, x, y):
        self.x     = x + np.random.uniform(-4, 4)
        self.y     = y + np.random.uniform(-4, 4)
        self.vx    = np.random.uniform(-0.6, 0.6)
        self.vy    = np.random.uniform(-1.6, -0.4)
        self.life  = 255
        self.decay = np.random.uniform(5, 10)

    def update(self):
        self.x    += self.vx
        self.y    += self.vy
        self.life -= self.decay
        return self.life > 0

    def draw(self, screen):
        if self.life > 0:
            pygame.draw.circle(screen, (255, min(255, int(self.life)//2), 0),
                               (int(self.x), int(self.y)), 2)


class SmokeParticle:
    """Grey smoke rising from fire cells."""
    def __init__(self, x, y):
        self.x     = x + np.random.uniform(-6, 6)
        self.y     = y
        self.vx    = np.random.uniform(-0.3, 0.3)
        self.vy    = np.random.uniform(-0.8, -0.3)
        self.life  = np.random.randint(160, 230)
        self.decay = np.random.uniform(2, 5)
        self.r     = np.random.randint(3, 6)

    def update(self):
        self.x    += self.vx
        self.y    += self.vy
        self.life -= self.decay
        self.vx   *= 0.98
        return self.life > 0

    def draw(self, screen):
        if self.life > 0:
            alpha = int(self.life * 0.6)
            grey  = min(200, int(self.life))
            surf  = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (grey, grey, grey, alpha),
                               (self.r, self.r), self.r)
            screen.blit(surf, (int(self.x) - self.r, int(self.y) - self.r))


class PygameSimulation:

    def __init__(self, grids, num_firefighters=1, max_steps=300, algorithm="astar",
                 tick_mode="continuous"):

        self.grids            = grids
        self.num_firefighters = num_firefighters
        self.max_steps        = max_steps
        self.algorithm        = algorithm
        # Movement mode: 'continuous' or 'tick'
        # tick mode uses a slow default speed so each step is clearly visible.
        self.tick_mode        = tick_mode

        self.floor_manager = FloorManager(grids)
        self.health        = HealthSystem()
        self.health.register_all(grids)

        initialize_firefighters(grids, num_firefighters, algorithm,
                                floor_manager=self.floor_manager)
        from firefighter import _manager as _mgr
        self.ff_manager = _mgr

        self.metrics      = SimulationMetrics()
        self.total_people = sum(
            int(np.sum(g == PERSON)) + int(np.sum(g == PERSON_DANGER))
            for g in grids
        )
        self.metrics.initial_people_count = self.total_people
        self.metrics._prev_total_alive    = self.total_people

        self.step              = 0
        self.paused            = False
        # Both modes start at 1.0x; continuous feels faster due to smooth glide
        self.speed             = 1.0
        self.simulation_active = True
        self.end_reason        = ""
        self.active_floor      = 0
        self.show_end_screen   = False
        self.leaderboard_rank  = None  # rank if made top 10
        self.leaderboard_data  = []

        self.fire_particles  = []
        self.smoke_particles = []
        self.anim_frame      = 0
        self.show_paths      = False   # V key toggles path visualisation
        # Continuous mode: per-FF interpolation state
        # {ff_id: {'from': (px,py), 'to': (px,py), 'progress': float}}
        self._ff_interp      = {}
        self._interp_speed   = 4.0    # cells per second at 60fps

        self.screen = pygame.display.set_mode(
            (SCREEN_W, SCREEN_H)
        )
        pygame.display.set_caption("AI Firefighter Rescue Simulation")
        self.clock = pygame.time.Clock()
        self._load_images()

    # ----------------------------------------------------------

    def _load_images(self):
        cs = CELL_SIZE
        self.img_civilian  = _load("civilian.png",    (cs, cs))
        self.img_danger    = _tinted(self.img_civilian, (255, 80, 0, 120))
        self.img_ff        = _load("firefighter.png", (cs, cs))
        self.img_hospital  = _load("shelter.png",     (cs, cs))
        self.img_staircase = _load("exit.png",        (cs, cs))

    # ----------------------------------------------------------
    # Events
    # ----------------------------------------------------------

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_ESCAPE:                           return False
                elif k == pygame.K_SPACE:   self.paused = not self.paused
                elif k == pygame.K_UP:      self.speed = min(3.0, self.speed + 0.5)
                elif k == pygame.K_DOWN:    self.speed = max(0.5, self.speed - 0.5)
                elif k == pygame.K_r:       return 'reset'
                elif k == pygame.K_a and self.show_end_screen: return 'ambulance'
                elif k == pygame.K_v:       self.show_paths = not self.show_paths
                elif k == pygame.K_m:
                    if self.tick_mode == "continuous":
                        self.tick_mode = "tick"
                    else:
                        self.tick_mode = "continuous"
                        self._ff_interp = {}   # clear stale interp on switch
                elif k == pygame.K_1:       self.active_floor = 0
                elif k == pygame.K_2 and NUM_FLOORS > 1: self.active_floor = 1
                elif k == pygame.K_3 and NUM_FLOORS > 2: self.active_floor = 2
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_click(event.pos, event.button)
        return True

    def _handle_click(self, pos, button=1):
        # ── Floor tab switching (any button) ──────────────────────────────
        tab_w, tab_gap = 100, 8
        for i in range(NUM_FLOORS):
            tx = GRID_X + i * (tab_w + tab_gap)
            ty = MARGIN
            if tx <= pos[0] <= tx + tab_w and ty <= pos[1] <= ty + TAB_H - 4:
                self.active_floor = i
                return

        # ── Fire placement / removal (only when paused) ───────────────────
        if not self.paused:
            return
        if self.show_end_screen:
            return

        # Convert pixel to grid cell
        mx, my = pos
        c = (mx - GRID_X) // CELL_SIZE
        r = (my - GRID_Y) // CELL_SIZE

        # Bounds check — must be inside the grid
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return

        grid = self.grids[self.active_floor]
        cell = int(grid[r, c])

        if button == 1:                       # Left click — place fire
            if cell == EMPTY:
                grid[r, c] = FIRE
        elif button == 3:                     # Right click — remove fire
            if cell == FIRE:
                grid[r, c] = EMPTY

    # ----------------------------------------------------------
    # Update
    # ----------------------------------------------------------

    def update(self):
        if not self.simulation_active or self.paused:
            self.fire_particles  = [p for p in self.fire_particles  if p.update()]
            self.smoke_particles = [p for p in self.smoke_particles if p.update()]
            self.anim_frame += 1
            return

        # In continuous mode, advance interpolations every frame and only
        # fire the next sim tick when all FFs have finished their glide.
        if self.tick_mode == "continuous":
            all_done = self._advance_interp()
            self.fire_particles  = [p for p in self.fire_particles  if p.update()]
            self.smoke_particles = [p for p in self.smoke_particles if p.update()]
            self.anim_frame += 1
            if not all_done:
                return   # still animating — don't fire next tick yet
        else:
            # Tick-by-tick: original frame-throttle behaviour
            if self.anim_frame % max(1, int(10 / self.speed)) != 0:
                self.fire_particles  = [p for p in self.fire_particles  if p.update()]
                self.smoke_particles = [p for p in self.smoke_particles if p.update()]
                self.anim_frame += 1
                return

        self.step += 1

        # Fire spreads every 4 steps; skip the call entirely on other steps
        # to avoid copying all floor arrays for no effect.
        if self.step % 4 == 0:
            for i in range(NUM_FLOORS):
                self.grids[i] = spread_fire(self.grids[i], self.step, floor_idx=i)

        if self.step % 4 == 0:
            dead = self.health.tick_civilian_damage(self.grids)
            for floor_idx, r, c in dead:
                self.grids[floor_idx][r, c] = EMPTY
                self.health.remove(floor_idx, r, c)
                # people_burned is tracked in metrics.update() via _prev_total_alive

            if self.ff_manager:
                self.health.tick_ff_damage(self.ff_manager.firefighters, self.grids)

        # Snapshot positions BEFORE move for interpolation start points
        if self.tick_mode == "continuous" and self.ff_manager:
            pre_pos = {id(ff): (GRID_X + ff.pos[1]*CELL_SIZE,
                                GRID_Y + ff.pos[0]*CELL_SIZE)
                       for ff in self.ff_manager.firefighters}
        else:
            pre_pos = {}

        self.grids = move_firefighter(self.grids)

        # Record interpolation from old pixel → new pixel for each FF
        if self.tick_mode == "continuous" and self.ff_manager:
            self._ff_interp = {}
            for ff in self.ff_manager.firefighters:
                fid   = id(ff)
                start = pre_pos.get(fid, (GRID_X + ff.pos[1]*CELL_SIZE,
                                          GRID_Y + ff.pos[0]*CELL_SIZE))
                end   = (GRID_X + ff.pos[1]*CELL_SIZE,
                         GRID_Y + ff.pos[0]*CELL_SIZE)
                # Only interpolate if the FF actually moved
                prog  = 0.0 if start != end else 1.0
                self._ff_interp[fid] = {'from': start, 'to': end, 'progress': prog}

        ff_stats = get_firefighter_stats()
        stats    = self.metrics.update(self.grids, ff_stats)

        for pos in np.argwhere(self.grids[self.active_floor] == FIRE):
            px = GRID_X + pos[1] * CELL_SIZE + CELL_SIZE // 2
            py = GRID_Y + pos[0] * CELL_SIZE + CELL_SIZE // 2
            if np.random.random() < 0.18:
                self.fire_particles.append(FireParticle(px, py))
            if np.random.random() < 0.12:
                self.smoke_particles.append(SmokeParticle(px, py))

        if stats['safe'] == 0 and stats['danger'] == 0:
            self.simulation_active = False
            self.end_reason        = "All people rescued or lost!"
            self._finish()
        elif self.step >= self.max_steps:
            self.simulation_active = False
            self.end_reason        = "Max steps reached"
            self._finish()

        self.fire_particles  = [p for p in self.fire_particles  if p.update()]
        self.smoke_particles = [p for p in self.smoke_particles if p.update()]
        self.anim_frame += 1

    def _finish(self):
        """Save score and prep leaderboard data."""
        ff_stats = get_firefighter_stats()
        # Civilians being carried at sim end are counted as rescued —
        # the firefighter already saved them, just never reached the hospital.
        carried  = ff_stats.get('carrying', 0)
        rescued  = ff_stats.get('rescued', 0) + carried
        self.metrics.people_rescued = rescued
        score    = self.metrics.calculate_score(self.total_people, self.max_steps)
        self.leaderboard_rank = save_score(
            score, rescued, self.total_people,
            self.step, self.algorithm, NUM_FLOORS
        )
        self.leaderboard_data = get_top_scores()
        self.show_end_screen  = True

    # ----------------------------------------------------------
    # Drawing helpers
    # ----------------------------------------------------------

    def _hp_color(self, ratio):
        if ratio > 0.6:  return C_HP_HIGH
        if ratio > 0.3:  return C_HP_MED
        return C_HP_LOW

    def _water_color(self, ratio):
        return C_WATER_HIGH if ratio > 0.3 else C_WATER_LOW

    def _draw_hp_bar(self, x, y, hp, max_hp, has_water_bar=False):
        """Draw HP bar. If has_water_bar, shift up to leave room for water bar below."""
        bw  = CELL_SIZE - 4
        bh  = 4
        bx  = x + 2
        by  = y - (16 if has_water_bar else 7)
        pygame.draw.rect(self.screen, C_BAR_BG, (bx, by, bw, bh))
        fill = int(bw * max(0, hp / max_hp))
        if fill > 0:
            pygame.draw.rect(self.screen, self._hp_color(hp / max_hp), (bx, by, fill, bh))

    def _draw_water_bar(self, x, y, water, max_water=WATER_MAX):
        bw   = CELL_SIZE - 4
        bh   = 4
        bx   = x + 2
        by   = y - 9
        pygame.draw.rect(self.screen, C_BAR_BG, (bx, by, bw, bh))
        fill = int(bw * max(0, water / max_water))
        if fill > 0:
            pygame.draw.rect(self.screen, self._water_color(water / max_water),
                             (bx, by, fill, bh))

    def _draw_text(self, text, font, color, x, y, center=False):
        surf = font.render(text, True, color)
        if center:
            x -= surf.get_width() // 2
        self.screen.blit(surf, (x, y))

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------

    def _draw_grid(self):
        grid      = self.grids[self.active_floor]
        cs        = CELL_SIZE
        frame     = self.anim_frame
        floor_idx = self.active_floor

        # Per-floor subtle floor tint: ground floor warmer, top floor cooler
        floor_tints = [(52, 46, 40), (44, 44, 48), (38, 42, 50)]
        floor_tile  = floor_tints[min(floor_idx, 2)]

        # ── Pass 1: backgrounds + details (skip STAIRCASE) ───────────────────
        for r in range(ROWS):
            for c in range(COLS):
                x    = GRID_X + c * CELL_SIZE
                y    = GRID_Y + r * CELL_SIZE
                cell = int(grid[r, c])

                if cell == STAIRCASE:
                    continue

                # ── Floor tile (EMPTY) ────────────────────────────────────────
                if cell == EMPTY:
                    pygame.draw.rect(self.screen, floor_tile, (x, y, cs, cs))
                    # Subtle grout lines every cell
                    gc = (floor_tile[0]+8, floor_tile[1]+8, floor_tile[2]+8)
                    pygame.draw.line(self.screen, gc, (x, y), (x+cs-1, y), 1)
                    pygame.draw.line(self.screen, gc, (x, y), (x, y+cs-1), 1)
                    # Checkerboard micro-variation
                    if (r + c) % 2 == 0:
                        sl = (floor_tile[0]+4, floor_tile[1]+4, floor_tile[2]+4)
                        pygame.draw.rect(self.screen, sl, (x+1, y+1, cs-2, cs-2))

                # ── Wall / obstacle (3D bevel) ────────────────────────────────
                elif cell == OBSTACLE:
                    base   = (72, 68, 64)
                    hilit  = (105, 100, 94)   # top-left highlight
                    shadow = (38, 35, 32)      # bottom-right shadow
                    pygame.draw.rect(self.screen, base,   (x,    y,    cs,   cs))
                    # Bevel: top + left bright
                    pygame.draw.line(self.screen, hilit, (x, y),      (x+cs-1, y),      2)
                    pygame.draw.line(self.screen, hilit, (x, y),      (x,      y+cs-1), 2)
                    # Bevel: bottom + right dark
                    pygame.draw.line(self.screen, shadow, (x, y+cs-1),(x+cs-1, y+cs-1), 2)
                    pygame.draw.line(self.screen, shadow, (x+cs-1, y),(x+cs-1, y+cs-1), 2)
                    # Inner cross-hatch for brick texture
                    if cs >= 16:
                        ht = (58, 54, 50)
                        mid = cs // 2
                        pygame.draw.line(self.screen, ht, (x+4, y+mid), (x+cs-4, y+mid), 1)
                        pygame.draw.line(self.screen, ht, (x+mid, y+4), (x+mid, y+cs-4), 1)

                # ── Fire (original animated colour cycle) ────────────────
                elif cell == FIRE:
                    bg = C_FIRE[frame % 3]
                    pygame.draw.rect(self.screen, bg, (x, y, cs, cs))

                # ── Hospital (green border + cross) ───────────────────────────
                elif cell == HOSPITAL:
                    pygame.draw.rect(self.screen, (28, 44, 52), (x, y, cs, cs))
                    # Green border
                    pygame.draw.rect(self.screen, (30, 140, 80),
                                     (x, y, cs, cs), 2)
                    # White cross
                    cw = max(2, cs // 5)
                    ch = max(6, cs * 2 // 3)
                    mx, my = x + cs // 2, y + cs // 2
                    pygame.draw.rect(self.screen, (220, 240, 225),
                                     (mx - cw//2, my - ch//2, cw, ch))
                    pygame.draw.rect(self.screen, (220, 240, 225),
                                     (mx - ch//2, my - cw//2, ch, cw))
                    if self.img_hospital:
                        self.screen.blit(self.img_hospital, (x, y))

                # ── Person (safe — soft green background) ─────────────────────
                elif cell == PERSON:
                    pygame.draw.rect(self.screen, (26, 60, 30), (x, y, cs, cs))
                    pygame.draw.rect(self.screen, (40, 120, 55),
                                     (x, y, cs, cs), 1)
                    if self.img_civilian:
                        self.screen.blit(self.img_civilian, (x, y))

                # ── Person danger (pulsing orange glow) ───────────────────────
                elif cell == PERSON_DANGER:
                    pulse = abs(np.sin(frame * 0.15))
                    rb    = int(90 + 50 * pulse)
                    pygame.draw.rect(self.screen, (rb, 35, 5), (x, y, cs, cs))
                    # Pulsing border
                    bc = (255, int(120 + 80 * pulse), 0)
                    pygame.draw.rect(self.screen, bc, (x, y, cs, cs), 2)
                    if self.img_danger:
                        self.screen.blit(self.img_danger, (x, y))

                # ── Firefighter ───────────────────────────────────────────────
                elif cell == FIREFIGHTER:
                    if self.tick_mode == "continuous":
                        # Draw floor tile only — sprite drawn in Pass 5 at interpolated pos
                        pygame.draw.rect(self.screen, floor_tile, (x, y, cs, cs))
                        gc = (floor_tile[0]+8, floor_tile[1]+8, floor_tile[2]+8)
                        pygame.draw.line(self.screen, gc, (x, y), (x+cs-1, y), 1)
                        pygame.draw.line(self.screen, gc, (x, y), (x, y+cs-1), 1)
                    else:
                        pygame.draw.rect(self.screen, (65, 48, 10), (x, y, cs, cs))
                        pygame.draw.rect(self.screen, (180, 130, 30),
                                         (x, y, cs, cs), 1)
                        if self.img_ff:
                            self.screen.blit(self.img_ff, (x, y))
                        # Carrying indicator (tick mode only — drawn in Pass 5 for continuous)
                        if self.ff_manager:
                            for ff in self.ff_manager.firefighters:
                                if ff.pos == (r, c) and ff.current_floor == self.active_floor:
                                    if ff.carrying_person and self.img_civilian:
                                        icon_sz = max(10, cs // 3)
                                        icon    = pygame.transform.smoothscale(
                                                    self.img_civilian, (icon_sz, icon_sz))
                                        pygame.draw.rect(self.screen, (230, 230, 230),
                                                         (x + cs - icon_sz - 1,
                                                          y + 1, icon_sz, icon_sz),
                                                         border_radius=2)
                                        self.screen.blit(icon,
                                                         (x + cs - icon_sz - 1, y + 1))
                                    break

                else:
                    pygame.draw.rect(self.screen, floor_tile, (x, y, cs, cs))

                # Grid line
                pygame.draw.rect(self.screen, C_GRID, (x, y, cs, cs), 1)

                # HP bars for civilians
                if cell in (PERSON, PERSON_DANGER):
                    hp = self.health.get(self.active_floor, r, c)
                    self._draw_hp_bar(x, y, hp, CIVILIAN_MAX_HP)

                # HP + water bars for firefighters (tick mode — continuous drawn in Pass 5)
                elif cell == FIREFIGHTER and self.ff_manager and self.tick_mode != "continuous":
                    for ff in self.ff_manager.firefighters:
                        if ff.pos == (r, c) and ff.current_floor == self.active_floor:
                            self._draw_hp_bar(x, y, ff.hp, FF_MAX_HP, has_water_bar=True)
                            self._draw_water_bar(x, y, ff.water)
                            break

        # ── Pass 2: staircase cells ───────────────────────────────────────────
        for col in (STAIR_UP_COL, STAIR_DOWN_COL):
            for row in (STAIR_ROW_START, STAIR_ROW_END):
                if int(grid[row, col]) != STAIRCASE:
                    continue
                x = GRID_X + col * CELL_SIZE
                y = GRID_Y + row * CELL_SIZE
                # Background
                pygame.draw.rect(self.screen, (22, 48, 72), (x, y, cs, cs))
                # Step lines
                step_col = (50, 90, 130)
                n_steps  = max(3, cs // 8)
                for si in range(n_steps):
                    sy = y + int(cs * si / n_steps)
                    pygame.draw.line(self.screen, step_col,
                                     (x + 2, sy), (x + cs - 2, sy), 1)
                # Direction arrow text
                arrow = "▲" if col == STAIR_UP_COL else "▼"
                lbl   = F_TINY().render(arrow, True, (140, 190, 255))
                self.screen.blit(lbl, (x + cs - lbl.get_width() - 2, y + 2))
                # Border
                pygame.draw.rect(self.screen, (60, 110, 170), (x, y, cs, cs), 1)
                if self.img_staircase:
                    self.screen.blit(self.img_staircase, (x, y))

        # ── Pass 3: FFs standing on staircases ───────────────────────────────
        if self.ff_manager:
            for ff in self.ff_manager.firefighters:
                if ff.current_floor != self.active_floor:
                    continue
                r, c = ff.pos
                if int(grid[r, c]) == STAIRCASE:
                    x = GRID_X + c * CELL_SIZE
                    y = GRID_Y + r * CELL_SIZE
                    if self.img_ff:
                        self.screen.blit(self.img_ff, (x, y))
                    self._draw_hp_bar(x, y, ff.hp, FF_MAX_HP, has_water_bar=True)
                    self._draw_water_bar(x, y, ff.water)

        # ── Pass 4: path visualisation (V key toggle) ────────────────────────
        if self.show_paths and self.ff_manager:
            PATH_COLOURS = [
                (80, 200, 255), (255, 200, 80), (80, 255, 160),
                (255, 100, 200),(160, 100, 255),(255, 160, 80),
                (80, 255, 255), (200, 255, 80),
            ]
            dot_r = max(2, cs // 8)
            for fi, ff in enumerate(self.ff_manager.firefighters):
                if ff.current_floor != self.active_floor:
                    continue
                if not ff.current_path:
                    continue
                col = PATH_COLOURS[fi % len(PATH_COLOURS)]
                if len(ff.current_path) >= 2:
                    pts = [(GRID_X + pc*cs + cs//2, GRID_Y + pr*cs + cs//2)
                           for pr, pc in ff.current_path]
                    line_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    pygame.draw.lines(line_surf, (*col, 60), False, pts, 1)
                    self.screen.blit(line_surf, (0, 0))
                for step_i, (pr, pc) in enumerate(ff.current_path):
                    px = GRID_X + pc * cs + cs // 2
                    py = GRID_Y + pr * cs + cs // 2
                    alpha = max(60, 200 - step_i * 8)
                    surf  = pygame.Surface((dot_r*2+2, dot_r*2+2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (*col, alpha), (dot_r+1, dot_r+1), dot_r)
                    self.screen.blit(surf, (px - dot_r - 1, py - dot_r - 1))

        # ── Pass 5: continuous-mode FF sprites at interpolated positions ────
        if self.tick_mode == "continuous" and self.ff_manager:
            for ff in self.ff_manager.firefighters:
                if ff.current_floor != self.active_floor:
                    continue
                px, py = self._get_ff_pixel(ff)
                # Gold background at interpolated position
                pygame.draw.rect(self.screen, (65, 48, 10),
                                 (px, py, cs, cs))
                pygame.draw.rect(self.screen, (180, 130, 30),
                                 (px, py, cs, cs), 1)
                if self.img_ff:
                    self.screen.blit(self.img_ff, (px, py))
                # Carrying indicator
                if ff.carrying_person and self.img_civilian:
                    icon_sz = max(10, cs // 3)
                    icon    = pygame.transform.smoothscale(
                                self.img_civilian, (icon_sz, icon_sz))
                    pygame.draw.rect(self.screen, (230, 230, 230),
                                     (px + cs - icon_sz - 1,
                                      py + 1, icon_sz, icon_sz),
                                     border_radius=2)
                    self.screen.blit(icon, (px + cs - icon_sz - 1, py + 1))
                # HP + water bars
                self._draw_hp_bar(px, py, ff.hp, FF_MAX_HP, has_water_bar=True)
                self._draw_water_bar(px, py, ff.water)

        # ── Room frame ───────────────────────────────────────────────────────
        # Thick outer border to suggest building walls
        pygame.draw.rect(self.screen, (55, 50, 45),
                         (GRID_X - 3, GRID_Y - 3, GRID_W + 6, GRID_H + 6), 3)
        pygame.draw.rect(self.screen, (30, 27, 24),
                         (GRID_X - 6, GRID_Y - 6, GRID_W + 12, GRID_H + 12), 3)


    # ----------------------------------------------------------
    # Floor tabs
    # ----------------------------------------------------------

    def _draw_floor_tabs(self):
        tab_w, tab_gap = 100, 8
        for i in range(NUM_FLOORS):
            tx    = GRID_X + i * (tab_w + tab_gap)
            ty    = MARGIN
            th    = TAB_H - 4
            color = C_TAB_ON if i == self.active_floor else C_TAB_OFF
            pygame.draw.rect(self.screen, color, (tx, ty, tab_w, th), border_radius=6)
            g      = self.grids[i]
            people = int(np.sum(g == PERSON)) + int(np.sum(g == PERSON_DANGER))
            fire   = int(np.sum(g == FIRE))
            self._draw_text(f"Floor {i+1}", F_SMALL(), C_TEXT, tx + tab_w//2, ty + 4,  center=True)
            self._draw_text(f"P:{people}  F:{fire}", F_TINY(), C_TEXT_DIM, tx + tab_w//2, ty + 22, center=True)

    # ----------------------------------------------------------
    # Left panel
    # ----------------------------------------------------------

    def _draw_panel(self):
        pygame.draw.rect(self.screen, C_PANEL, (0, 0, PANEL_W, SCREEN_H))
        pygame.draw.line(self.screen, C_PANEL_LINE, (PANEL_W, 0), (PANEL_W, SCREEN_H), 1)

        y          = 18
        ff_stats   = get_firefighter_stats()
        n_ff       = len(self.ff_manager.firefighters) if self.ff_manager else 0
        total_fire = sum(int(np.sum(g == FIRE)) for g in self.grids)

        self._draw_text("SIMULATION", F_LARGE(), C_TEXT, 14, y); y += 44

        rows = [
            ("Step",         f"{self.step}/{self.max_steps}"),
            ("Rescued",      f"{self.metrics.people_rescued}/{self.total_people}"),
            ("Burned",       f"{self.metrics.people_burned}"),
            ("Fire cells",   f"{total_fire}"),
            ("Firefighters", f"{n_ff}"),
            ("Speed",        f"{self.speed:.1f}x"),
            ("Status",       "PAUSED" if self.paused else "RUNNING"),
        ]
        for label, val in rows:
            self._draw_text(f"{label}:", F_SMALL(), C_TEXT_DIM, 14, y)
            v = F_SMALL().render(val, True, C_TEXT)
            self.screen.blit(v, (PANEL_W - v.get_width() - 14, y))
            y += 22

        y += 8
        self._draw_text("Firefighters", F_SMALL(), C_TEXT_DIM, 14, y); y += 18

        if self.ff_manager:
            for idx, ff in enumerate(self.ff_manager.firefighters):
                bw = PANEL_W - 30
                bx = 14

                # HP bar
                pygame.draw.rect(self.screen, C_BAR_BG, (bx, y, bw, 6))
                fill = int(bw * ff.hp / FF_MAX_HP)
                if fill > 0:
                    pygame.draw.rect(self.screen, self._hp_color(ff.hp / FF_MAX_HP), (bx, y, fill, 6))

                # Water bar (blue, just below HP bar)
                pygame.draw.rect(self.screen, C_BAR_BG, (bx, y + 8, bw, 4))
                wfill = int(bw * ff.water / WATER_MAX)
                if wfill > 0:
                    pygame.draw.rect(self.screen, self._water_color(ff.water / WATER_MAX),
                                     (bx, y + 8, wfill, 4))

                self._draw_text(
                    f"FF{idx+1} F{ff.current_floor+1}  {ff.hp}HP  {ff.water}W",
                    F_TINY(), C_TEXT_DIM, bx, y + 14
                )
                y += 30

        y += 8
        self._draw_text("Legend", F_SMALL(), C_TEXT_DIM, 14, y); y += 18
        for color, label in [
            ((45, 180, 45),  "Civilian"),
            ((200, 100, 0),  "In danger"),
            ((220, 50, 50),  "Fire"),
            ((65, 65, 65),   "Obstacle"),
            ((30, 55, 80),   "Staircase"),
            ((35, 35, 55),   "Hospital"),
            ((200, 140, 20), "Firefighter"),
        ]:
            pygame.draw.rect(self.screen, color, (14, y + 2, 11, 11))
            self._draw_text(label, F_TINY(), C_TEXT_DIM, 30, y + 1)
            y += 17

        y += 8
        path_state = "ON" if self.show_paths else "OFF"
        mode_label = "TICK" if self.tick_mode == "tick" else "CONT"
        for line in ["SPACE  Pause/resume","UP/DN  Speed","1 2 3  Floor",
                     f"V      Paths [{path_state}]",
                     f"M      Mode  [{mode_label}]",
                     "R  Reset","ESC  Quit","",
                     "LClick  Place fire*","RClick  Remove fire*","*paused only"]:
            self._draw_text(line, F_TINY(), C_TEXT_DIM, 14, y); y += 15

        if self.end_reason:
            msg = F_SMALL().render(self.end_reason, True, C_GOLD)
            self.screen.blit(msg, (14, SCREEN_H - 36))

    # ----------------------------------------------------------
    # Continuous mode interpolation
    # ----------------------------------------------------------

    def _advance_interp(self):
        """
        Advance all FF interpolations by one frame.
        Returns True when every FF has finished its glide (next tick can fire).
        Speed controls how fast the glide completes:
          interp_speed = self.speed * 6.0  cells-per-second equivalent
          At 60 fps, progress += speed*6/60 per frame.
          speed=0.5 → ~20 frames per cell; speed=3.0 → ~3 frames per cell.
        """
        if not self._ff_interp:
            return True
        dt_progress = self.speed * 6.0 / 60.0
        all_done = True
        for fid, state in self._ff_interp.items():
            if state['progress'] < 1.0:
                state['progress'] = min(1.0, state['progress'] + dt_progress)
            if state['progress'] < 1.0:
                all_done = False
        return all_done

    def _get_ff_pixel(self, ff):
        """Return the current draw pixel (top-left) for a FF, interpolated if in continuous mode."""
        if self.tick_mode != "continuous":
            return (GRID_X + ff.pos[1] * CELL_SIZE,
                    GRID_Y + ff.pos[0] * CELL_SIZE)
        state = self._ff_interp.get(id(ff))
        if state is None:
            return (GRID_X + ff.pos[1] * CELL_SIZE,
                    GRID_Y + ff.pos[0] * CELL_SIZE)
        t   = state['progress']
        fx, fy = state['from']
        tx, ty = state['to']
        return (int(fx + (tx - fx) * t), int(fy + (ty - fy) * t))

    # ----------------------------------------------------------
    # Minimap — right of the grid, always visible during sim
    # ----------------------------------------------------------

    def _draw_minimap(self):
        """
        Three floor thumbnails drawn to the right of the active grid.
        Space available: from (GRID_X + GRID_W + MARGIN) to SCREEN_W.
        Each floor = COLS x ROWS cells at mm_cell px each, stacked vertically.
        Active floor gets a bright border; others are dimmed.
        """
        right_x   = GRID_X + GRID_W + MARGIN
        avail_w   = SCREEN_W - right_x - MARGIN
        avail_h   = GRID_H

        if avail_w < 20:   # not enough space — skip
            return

        mm_gap    = 6
        # Fit all 3 floors stacked vertically with gaps
        mm_cell   = max(2, min(
            avail_w // COLS,
            (avail_h - mm_gap * (NUM_FLOORS - 1)) // (ROWS * NUM_FLOORS)
        ))
        mm_w      = mm_cell * COLS
        mm_h      = mm_cell * ROWS
        total_h   = mm_h * NUM_FLOORS + mm_gap * (NUM_FLOORS - 1)
        mm_x      = right_x + (avail_w - mm_w) // 2
        mm_y0     = GRID_Y + (avail_h - total_h) // 2

        MM_COL = {
            EMPTY:         (38, 36, 32),
            OBSTACLE:      (72, 68, 64),
            FIRE:          C_FIRE[self.anim_frame % 3],
            PERSON:        (40, 160, 50),
            PERSON_DANGER: (200, 100, 10),
            FIREFIGHTER:   (220, 170, 30),
            HOSPITAL:      (30, 100, 140),
            STAIRCASE:     (40, 80, 130),
        }

        # Label above the whole minimap
        lbl = F_TINY().render("ALL FLOORS", True, C_TEXT_DIM)
        self.screen.blit(lbl, (mm_x + (mm_w - lbl.get_width()) // 2, mm_y0 - 14))

        for fi in range(NUM_FLOORS - 1, -1, -1):   # draw top floor first (F3 at top)
            display_order = NUM_FLOORS - 1 - fi     # 0 = F3, 1 = F2, 2 = F1
            fy    = mm_y0 + display_order * (mm_h + mm_gap)
            fgrid = self.grids[fi]
            active = (fi == self.active_floor)

            # Dim non-active floors slightly
            base_alpha = 255 if active else 140

            # Background
            pygame.draw.rect(self.screen, (18, 16, 14),
                             (mm_x - 1, fy - 1, mm_w + 2, mm_h + 2))

            # Draw cells
            surf = pygame.Surface((mm_w, mm_h))
            for r in range(ROWS):
                for c in range(COLS):
                    col = MM_COL.get(int(fgrid[r, c]), (38, 36, 32))
                    pygame.draw.rect(surf, col,
                                     (c * mm_cell, r * mm_cell, mm_cell, mm_cell))

            if not active:
                surf.set_alpha(base_alpha)
            self.screen.blit(surf, (mm_x, fy))

            # Border
            border_col = (100, 160, 255) if active else (45, 42, 38)
            border_w   = 2 if active else 1
            pygame.draw.rect(self.screen, border_col,
                             (mm_x - 1, fy - 1, mm_w + 2, mm_h + 2), border_w)

            # Floor label
            fl = F_TINY().render(f"F{fi + 1}", True,
                               (150, 190, 255) if active else (70, 68, 60))
            self.screen.blit(fl, (mm_x + mm_w + 3, fy + mm_h // 2 - fl.get_height() // 2))

    # ----------------------------------------------------------
    # End screen (graph + leaderboard)
    # ----------------------------------------------------------

    def _draw_end_screen(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((10, 10, 10, 220))
        self.screen.blit(overlay, (0, 0))

        score    = self.metrics.calculate_score(self.total_people, self.max_steps)
        rank_txt = f"   Rank #{self.leaderboard_rank}" if self.leaderboard_rank else ""

        # ── Title bar (full width, own zone) ──────────────────────────
        pygame.draw.rect(self.screen, (28, 28, 28), (0, 0, SCREEN_W, 64))
        pygame.draw.line(self.screen, (55, 55, 55), (0, 64), (SCREEN_W, 64), 1)
        self._draw_text("SIMULATION RESULTS", F_LARGE(), C_TEXT,
                        SCREEN_W // 2, 14, center=True)
        self._draw_text(f"Score: {score:.0f} / 2000{rank_txt}",
                        F_LARGE(), C_GOLD, SCREEN_W // 2, 38, center=True)

        # ── Layout ────────────────────────────────────────────────────
        PAD     = 24
        top_y   = 80
        bot_y   = SCREEN_H - 56
        ch      = bot_y - top_y

        # Left half: graph (full height)
        # Right half: leaderboard (top ~55%) + incident report (bottom ~45%)
        mid_x   = SCREEN_W // 2
        gx      = PAD
        gw      = mid_x - PAD * 2
        gh      = ch - 4                    # graph uses full left column height
        bx      = mid_x + PAD
        bw      = SCREEN_W - bx - PAD

        # Right column split
        board_rows   = 11                   # header + 10 entries
        board_row_h  = 22
        board_h      = board_rows * board_row_h
        # ir_gap must be large enough to fit the "Incident Report" section label
        # (F_SMALL height ~18px) plus a small margin above the card.
        ir_gap       = 28
        ir_y         = top_y + 22 + board_h + ir_gap
        ir_h         = bot_y - ir_y - 4

        # ── Section labels ─────────────────────────────────────────────
        self._draw_text("Performance graph", F_SMALL(), C_TEXT_DIM, gx, top_y)
        self._draw_text("Top 10 scores",     F_SMALL(), C_TEXT_DIM, bx, top_y)
        # Label sits in the gap between leaderboard and incident report card
        self._draw_text("Incident Report",   F_SMALL(), C_TEXT_DIM, bx, ir_y - 20)

        graph_y = top_y + 22

        # ── Graph ──────────────────────────────────────────────────────
        pygame.draw.rect(self.screen, (22, 22, 22), (gx, graph_y, gw, gh))
        pygame.draw.rect(self.screen, (50, 50, 50), (gx, graph_y, gw, gh), 1)

        data = self.metrics.get_graph_data()

        def _line(series, color, max_val):
            if len(series) < 2 or max_val <= 0: return
            pts = []
            for i, v in enumerate(series):
                px = gx + int(i / max(len(series)-1, 1) * gw)
                py = graph_y + gh - int(v / max_val * gh)
                pts.append((max(gx, min(gx+gw, px)),
                             max(graph_y+2, min(graph_y+gh-2, py))))
            if len(pts) >= 2:
                pygame.draw.lines(self.screen, color, False, pts, 2)

        _line(data['fire'],    (215, 55, 55),  max(data['fire'])    or 1)
        _line(data['rescued'], (50, 200, 50),  self.total_people    or 1)
        _line(data['danger'],  (225, 150, 20), self.total_people    or 1)
        if data.get('ff_hp'):
            _line(data['ff_hp'], (100, 180, 255), FF_MAX_HP)

        ly = graph_y + 8
        for color, lbl in [((215,55,55),"Fire"),((50,200,50),"Rescued"),
                            ((225,150,20),"Danger"),((100,180,255),"FF HP")]:
            pygame.draw.line(self.screen, color, (gx+8, ly+6), (gx+30, ly+6), 2)
            self._draw_text(lbl, F_TINY(), C_TEXT_DIM, gx+36, ly)
            ly += 17

        # ── Leaderboard table (right column, top) ──────────────────────
        board_y = top_y + 22
        pygame.draw.rect(self.screen, (40, 40, 40), (bx, board_y, bw, board_row_h))
        for txt, ox in [("#",6),("Score",26),("Rescued",96),("Steps",152),("Algo",206),("Date",256)]:
            self._draw_text(txt, F_TINY(), C_TEXT_DIM, bx+ox, board_y+5)

        ry = board_y + board_row_h
        for i, entry in enumerate(self.leaderboard_data):
            is_cur = (self.leaderboard_rank == i + 1)
            bg     = (50, 45, 10) if is_cur else ((30,30,30) if i%2==0 else (25,25,25))
            pygame.draw.rect(self.screen, bg, (bx, ry, bw, board_row_h))
            tc = C_GOLD if is_cur else C_TEXT
            dc = C_GOLD if is_cur else C_TEXT_DIM
            rstr = f"{entry['rescued']}/{entry['total']}"
            for txt, ox, col in [
                (str(i+1),                6,   dc),
                (f"{entry['score']:.0f}", 26,  tc),
                (rstr,                    96,  dc),
                (str(entry['steps']),    152,  dc),
                (entry['algorithm'][:4], 206,  dc),
                (entry['date'][5:],      256,  dc),
            ]:
                self._draw_text(txt, F_TINY(), col, bx+ox, ry+5)
            ry += board_row_h

        # ── Incident Report Card (right column, below leaderboard) ──────
        if ir_h > 30:
            pygame.draw.rect(self.screen, (18, 16, 14),
                             (bx, ir_y, bw, ir_h), border_radius=6)
            pygame.draw.rect(self.screen, (80, 60, 20),
                             (bx, ir_y, bw, ir_h), 1, border_radius=6)

            # Amber header strip
            pygame.draw.rect(self.screen, (30, 22, 8),
                             (bx, ir_y, bw, 18), border_radius=6)
            hdr = F_TINY().render("▌ INCIDENT REPORT  —  FIRE DEPT. SIMULATION CITY",
                                 True, (180, 140, 50))
            self.screen.blit(hdr, (bx + 8, ir_y + 3))

            rescue_pct   = (self.metrics.people_rescued / self.total_people * 100
                            if self.total_people > 0 else 0)
            ff_count     = len(self.ff_manager.firefighters) if self.ff_manager else 0
            extinguished = self.metrics.fires_extinguished
            score_val    = self.metrics.calculate_score(self.total_people, self.max_steps)
            rank_disp    = f"#{self.leaderboard_rank}" if self.leaderboard_rank else "—"

            # Two-column layout inside the card
            col_w  = bw // 2 - 8
            lx     = bx + 8
            rx     = bx + bw // 2 + 4
            iy     = ir_y + 22
            row_h2 = 15

            def ir_row(label, val, col_x, colour=C_TEXT):
                nonlocal iy
                ls = F_TINY().render(label,    True, (110, 100, 70))
                vs = F_TINY().render(str(val), True, colour)
                self.screen.blit(ls, (col_x, iy))
                self.screen.blit(vs, (col_x + col_w - vs.get_width() - 4, iy))
                iy += row_h2

            iy_l = ir_y + 22
            iy   = iy_l
            ir_row("Incident #",  f"{self.step:04d}-SIM",       lx)
            ir_row("Algorithm",   self.algorithm.upper(),        lx)
            ir_row("Floors",      NUM_FLOORS,                    lx)
            ir_row("Active FFs",  ff_count,                      lx)
            ir_row("Civilians",   self.total_people,             lx)
            ir_row("Rescued",     self.metrics.people_rescued,   lx, (80, 220, 80))
            ir_row("Casualty",    self.metrics.people_burned,    lx, (220, 70, 70))
            rescue_col = ((80,220,80) if rescue_pct >= 80 else
                          (220,180,40) if rescue_pct >= 50 else (220,70,70))
            ir_row("Rescue rate", f"{rescue_pct:.0f}%",          lx, rescue_col)

            iy = iy_l
            ir_row("Steps taken", self.step,                      rx)
            ir_row("Max steps",   self.max_steps,                 rx)
            ir_row("Fires out",   extinguished,                   rx, (100,180,255))
            ir_row("Peak fire",   self.metrics.max_fire_spread,   rx, (255,120,50))
            ir_row("Phase",       self.metrics.current_phase.upper(), rx)
            ir_row("Score",       f"{score_val:.0f}/2000",        rx, C_GOLD)
            ir_row("Rank",        rank_disp, rx,
                   C_GOLD if self.leaderboard_rank else C_TEXT_DIM)

        # ── Footer ─────────────────────────────────────────────────────
        pygame.draw.line(self.screen, (45,45,45), (0, bot_y+4), (SCREEN_W, bot_y+4), 1)
        self._draw_text("R   restart          A   ambulance phase          ESC   quit",
                        F_MEDIUM(), C_TEXT_DIM, SCREEN_W//2, bot_y+16, center=True)

    # ----------------------------------------------------------
    # Main draw
    # ----------------------------------------------------------

    def draw(self):
        self.screen.fill(C_BG)
        self._draw_floor_tabs()
        self._draw_grid()
        self._draw_minimap()
        for p in self.fire_particles:
            p.draw(self.screen)
        for p in self.smoke_particles:
            p.draw(self.screen)
        self._draw_panel()
        if self.show_end_screen:
            self._draw_end_screen()
        pygame.display.flip()

    # ----------------------------------------------------------
    # Run loop
    # ----------------------------------------------------------

    def run(self):
        # Flush stale events from previous phases so the sim never exits
        # on its first frame due to a leftover keypress or display event.
        pygame.event.clear()
        running = True
        while running:
            result = self.handle_events()
            if result == 'reset':
                return 'reset'
            if result == 'ambulance':
                return ('ambulance', self.metrics.people_rescued)
            if not result:
                break
            self.update()
            self.draw()
            self.clock.tick(60)

        pygame.quit()
        ff_stats = get_firefighter_stats()
        self.metrics.print_report(self.total_people, ff_stats, self.max_steps)
        return self.metrics


# ============================================================

def run_simulation(grids, num_firefighters=1, max_steps=300, algorithm="astar",
                   city_data=None, burning_road_pos=None, tick_mode="continuous"):
    from environment import create_all_floors
    while True:
        sim    = PygameSimulation(grids, num_firefighters, max_steps, algorithm,
                                  tick_mode=tick_mode)
        result = sim.run()
        if result == 'reset':
            grids = create_all_floors()
        elif isinstance(result, tuple) and result[0] == 'ambulance':
            rescued    = result[1]
            amb_result = AmbulancePhase(rescued_count=rescued,
                                        city_data=city_data,
                                        start_pos=burning_road_pos).run()
            if amb_result == 'restart':
                # R pressed in ambulance — restart the whole pipeline.
                # Do NOT call pygame.quit() here; fonts would be invalidated.
                return 'restart'
            pygame.quit()
            return result[1]
        else:
            return result