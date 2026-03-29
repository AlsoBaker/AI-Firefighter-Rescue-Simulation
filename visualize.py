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

F_LARGE  = pygame.font.Font(None, 38)
F_MEDIUM = pygame.font.Font(None, 26)
F_SMALL  = pygame.font.Font(None, 20)
F_TINY   = pygame.font.Font(None, 15)

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


class PygameSimulation:

    def __init__(self, grids, num_firefighters=1, max_steps=300, algorithm="astar"):

        self.grids            = grids
        self.num_firefighters = num_firefighters
        self.max_steps        = max_steps
        self.algorithm        = algorithm

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
        self.speed             = 1.0
        self.simulation_active = True
        self.end_reason        = ""
        self.active_floor      = 0
        self.show_end_screen   = False
        self.leaderboard_rank  = None  # rank if made top 10
        self.leaderboard_data  = []

        self.fire_particles = []
        self.anim_frame     = 0

        self.screen = pygame.display.set_mode(
            (SCREEN_W, SCREEN_H), pygame.FULLSCREEN
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
                elif k == pygame.K_1:       self.active_floor = 0
                elif k == pygame.K_2 and NUM_FLOORS > 1: self.active_floor = 1
                elif k == pygame.K_3 and NUM_FLOORS > 2: self.active_floor = 2
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_click(event.pos)
        return True

    def _handle_click(self, pos):
        tab_w, tab_gap = 100, 8
        for i in range(NUM_FLOORS):
            tx = GRID_X + i * (tab_w + tab_gap)
            ty = MARGIN
            if tx <= pos[0] <= tx + tab_w and ty <= pos[1] <= ty + TAB_H - 4:
                self.active_floor = i

    # ----------------------------------------------------------
    # Update
    # ----------------------------------------------------------

    def update(self):
        if not self.simulation_active or self.paused:
            self.fire_particles = [p for p in self.fire_particles if p.update()]
            self.anim_frame += 1
            return

        if self.anim_frame % max(1, int(10 / self.speed)) != 0:
            self.fire_particles = [p for p in self.fire_particles if p.update()]
            self.anim_frame += 1
            return

        self.step += 1

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

        self.grids = move_firefighter(self.grids)

        ff_stats = get_firefighter_stats()
        stats    = self.metrics.update(self.grids, ff_stats)

        for pos in np.argwhere(self.grids[self.active_floor] == FIRE):
            if np.random.random() < 0.18:
                px = GRID_X + pos[1] * CELL_SIZE + CELL_SIZE // 2
                py = GRID_Y + pos[0] * CELL_SIZE + CELL_SIZE // 2
                self.fire_particles.append(FireParticle(px, py))

        if stats['safe'] == 0 and stats['danger'] == 0:
            self.simulation_active = False
            self.end_reason        = "All people rescued or lost!"
            self._finish()
        elif self.step >= self.max_steps:
            self.simulation_active = False
            self.end_reason        = "Max steps reached"
            self._finish()

        self.fire_particles = [p for p in self.fire_particles if p.update()]
        self.anim_frame += 1

    def _finish(self):
        """Save score and prep leaderboard data."""
        ff_stats = get_firefighter_stats()
        # Civilians being carried at sim end are counted as rescued —
        # the firefighter already saved them, just never reached the hospital.
        carried  = ff_stats.get('carrying', 0)
        rescued  = ff_stats.get('rescued', 0) + carried
        self.metrics.people_rescued = rescued
        score    = self.metrics.calculate_score(self.total_people)
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
        grid = self.grids[self.active_floor]

        for r in range(ROWS):
            for c in range(COLS):
                x    = GRID_X + c * CELL_SIZE
                y    = GRID_Y + r * CELL_SIZE
                cell = int(grid[r, c])

                if cell == STAIRCASE:
                    continue

                if   cell == FIRE:        bg = C_FIRE[self.anim_frame % 3]
                elif cell == OBSTACLE:    bg = C_OBSTACLE
                elif cell == HOSPITAL:    bg = C_HOSP_BG
                elif cell == PERSON:      bg = C_PERSON_BG
                elif cell == PERSON_DANGER: bg = C_DANGER_BG
                elif cell == FIREFIGHTER: bg = C_FF_BG
                else:                     bg = C_EMPTY

                pygame.draw.rect(self.screen, bg,     (x, y, CELL_SIZE, CELL_SIZE))
                pygame.draw.rect(self.screen, C_GRID, (x, y, CELL_SIZE, CELL_SIZE), 1)

                if   cell == PERSON        and self.img_civilian:  self.screen.blit(self.img_civilian, (x, y))
                elif cell == PERSON_DANGER and self.img_danger:    self.screen.blit(self.img_danger,   (x, y))
                elif cell == FIREFIGHTER   and self.img_ff:        self.screen.blit(self.img_ff,       (x, y))
                elif cell == HOSPITAL      and self.img_hospital:  self.screen.blit(self.img_hospital, (x, y))

                # HP bars for civilians
                if cell in (PERSON, PERSON_DANGER):
                    hp = self.health.get(self.active_floor, r, c)
                    self._draw_hp_bar(x, y, hp, CIVILIAN_MAX_HP)

                # HP + water bars for firefighters
                elif cell == FIREFIGHTER and self.ff_manager:
                    for ff in self.ff_manager.firefighters:
                        if ff.pos == (r, c) and ff.current_floor == self.active_floor:
                            self._draw_hp_bar(x, y, ff.hp, FF_MAX_HP, has_water_bar=True)
                            self._draw_water_bar(x, y, ff.water)
                            break

        # Staircase cells (1x1)
        for c in (STAIR_UP_COL, STAIR_DOWN_COL):
            for r in (STAIR_ROW_START, STAIR_ROW_END):
                if int(grid[r, c]) != STAIRCASE:
                    continue
                x = GRID_X + c * CELL_SIZE
                y = GRID_Y + r * CELL_SIZE
                pygame.draw.rect(self.screen, C_STAIR_BG,  (x, y, CELL_SIZE, CELL_SIZE))
                pygame.draw.rect(self.screen, C_GRID,      (x, y, CELL_SIZE, CELL_SIZE), 1)
                arrow = "^" if c == STAIR_UP_COL else "v"
                lbl   = F_TINY.render(arrow, True, (160, 200, 255))
                self.screen.blit(lbl, (x + CELL_SIZE - lbl.get_width() - 2, y + 2))
                if self.img_staircase:
                    self.screen.blit(self.img_staircase, (x, y))

        # FFs standing on staircase
        if self.ff_manager:
            for ff in self.ff_manager.firefighters:
                if ff.current_floor != self.active_floor:
                    continue
                r, c = ff.pos
                if int(grid[r, c]) == STAIRCASE:
                    x = GRID_X + c * CELL_SIZE
                    y = GRID_Y + r * CELL_SIZE
                    if self.img_ff: self.screen.blit(self.img_ff, (x, y))
                    self._draw_hp_bar(x, y, ff.hp, FF_MAX_HP, has_water_bar=True)
                    self._draw_water_bar(x, y, ff.water)

        pygame.draw.rect(self.screen, C_PANEL_LINE,
                         (GRID_X - 1, GRID_Y - 1, GRID_W + 2, GRID_H + 2), 1)

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
            self._draw_text(f"Floor {i+1}", F_SMALL, C_TEXT, tx + tab_w//2, ty + 4,  center=True)
            self._draw_text(f"P:{people}  F:{fire}", F_TINY, C_TEXT_DIM, tx + tab_w//2, ty + 22, center=True)

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

        self._draw_text("SIMULATION", F_LARGE, C_TEXT, 14, y); y += 44

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
            self._draw_text(f"{label}:", F_SMALL, C_TEXT_DIM, 14, y)
            v = F_SMALL.render(val, True, C_TEXT)
            self.screen.blit(v, (PANEL_W - v.get_width() - 14, y))
            y += 22

        y += 8
        self._draw_text("Firefighters", F_SMALL, C_TEXT_DIM, 14, y); y += 18

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
                    F_TINY, C_TEXT_DIM, bx, y + 14
                )
                y += 30

        y += 8
        self._draw_text("Legend", F_SMALL, C_TEXT_DIM, 14, y); y += 18
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
            self._draw_text(label, F_TINY, C_TEXT_DIM, 30, y + 1)
            y += 17

        y += 8
        for line in ["SPACE  Pause/resume","UP/DN  Speed","1 2 3  Floor","R  Reset","ESC  Quit"]:
            self._draw_text(line, F_TINY, C_TEXT_DIM, 14, y); y += 15

        if self.end_reason:
            msg = F_SMALL.render(self.end_reason, True, C_GOLD)
            self.screen.blit(msg, (14, SCREEN_H - 36))

    # ----------------------------------------------------------
    # End screen (graph + leaderboard)
    # ----------------------------------------------------------

    def _draw_end_screen(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((10, 10, 10, 220))
        self.screen.blit(overlay, (0, 0))

        score    = self.metrics.calculate_score(self.total_people)
        rank_txt = f"   Rank #{self.leaderboard_rank}" if self.leaderboard_rank else ""

        # ── Title bar (full width, own zone) ──────────────────────────
        pygame.draw.rect(self.screen, (28, 28, 28), (0, 0, SCREEN_W, 64))
        pygame.draw.line(self.screen, (55, 55, 55), (0, 64), (SCREEN_W, 64), 1)
        self._draw_text("SIMULATION RESULTS", F_LARGE, C_TEXT,
                        SCREEN_W // 2, 14, center=True)
        self._draw_text(f"Score: {score:.0f} / 2000{rank_txt}",
                        F_LARGE, C_GOLD, SCREEN_W // 2, 38, center=True)

        # ── Layout: content starts below title bar ─────────────────────
        PAD     = 24
        top_y   = 80                             # below title bar + gap
        bot_y   = SCREEN_H - 56                  # above footer
        ch      = bot_y - top_y                  # content height

        mid_x   = SCREEN_W // 2
        gx      = PAD                            # graph left edge
        gw      = mid_x - PAD * 2               # graph width
        gh      = ch - 36                        # graph height (room for stats below)
        bx      = mid_x + PAD                    # leaderboard left edge
        bw      = SCREEN_W - bx - PAD            # leaderboard width

        # ── Section labels ─────────────────────────────────────────────
        self._draw_text("Performance graph", F_SMALL, C_TEXT_DIM, gx, top_y)
        self._draw_text("Top 10 scores",     F_SMALL, C_TEXT_DIM, bx, top_y)

        graph_y = top_y + 22

        # ── Graph background ───────────────────────────────────────────
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

        # graph legend (top-left inside graph)
        ly = graph_y + 8
        for color, lbl in [((215,55,55),"Fire"),((50,200,50),"Rescued"),
                            ((225,150,20),"Danger"),((100,180,255),"FF HP")]:
            pygame.draw.line(self.screen, color, (gx+8, ly+6), (gx+30, ly+6), 2)
            self._draw_text(lbl, F_TINY, C_TEXT_DIM, gx+36, ly)
            ly += 17

        # stat summary below graph
        sy  = graph_y + gh + 10
        sx  = gx
        for text, color in [
            (f"Rescued: {self.metrics.people_rescued}/{self.total_people}", (50, 200, 50)),
            (f"Burned: {self.metrics.people_burned}",  (215, 55, 55)),
            (f"Steps: {self.step}",                    C_TEXT_DIM),
        ]:
            self._draw_text(text, F_SMALL, color, sx, sy)
            sx += F_SMALL.size(text)[0] + 28

        # ── Leaderboard table ──────────────────────────────────────────
        board_y = top_y + 22
        row_h   = 22

        # header row
        pygame.draw.rect(self.screen, (40, 40, 40), (bx, board_y, bw, row_h))
        for txt, ox in [("#",6),("Score",26),("Rescued",96),("Steps",162),("Algo",216),("Date",268)]:
            self._draw_text(txt, F_TINY, C_TEXT_DIM, bx+ox, board_y+5)

        ry = board_y + row_h
        for i, entry in enumerate(self.leaderboard_data):
            is_cur = (self.leaderboard_rank == i + 1)
            bg     = (50, 45, 10) if is_cur else ((30,30,30) if i%2==0 else (25,25,25))
            pygame.draw.rect(self.screen, bg, (bx, ry, bw, row_h))
            tc = C_GOLD if is_cur else C_TEXT
            dc = C_GOLD if is_cur else C_TEXT_DIM
            rstr = f"{entry['rescued']}/{entry['total']}"
            for txt, ox, col in [
                (str(i+1),               6,   dc),
                (f"{entry['score']:.0f}", 26, tc),
                (rstr,                   96,  dc),
                (str(entry['steps']),   162, dc),
                (entry['algorithm'][:4],216, dc),
                (entry['date'][5:],     268, dc),
            ]:
                self._draw_text(txt, F_TINY, col, bx+ox, ry+5)
            ry += row_h

        # ── Footer ─────────────────────────────────────────────────────
        pygame.draw.line(self.screen, (45,45,45), (0, bot_y+4), (SCREEN_W, bot_y+4), 1)
        self._draw_text("R   restart          A   ambulance phase          ESC   quit",
                        F_MEDIUM, C_TEXT_DIM, SCREEN_W//2, bot_y+16, center=True)

    # ----------------------------------------------------------
    # Main draw
    # ----------------------------------------------------------

    def draw(self):
        self.screen.fill(C_BG)
        self._draw_floor_tabs()
        self._draw_grid()
        for p in self.fire_particles:
            p.draw(self.screen)
        self._draw_panel()
        if self.show_end_screen:
            self._draw_end_screen()
        pygame.display.flip()

    # ----------------------------------------------------------
    # Run loop
    # ----------------------------------------------------------

    def run(self):
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
        self.metrics.print_report(self.total_people, ff_stats)
        return self.metrics


# ============================================================

def run_simulation(grids, num_firefighters=1, max_steps=300, algorithm="astar"):
    from environment import create_all_floors
    while True:
        sim    = PygameSimulation(grids, num_firefighters, max_steps,
                                  algorithm)
        result = sim.run()
        if result == 'reset':
            grids = create_all_floors()
        elif isinstance(result, tuple) and result[0] == 'ambulance':
            rescued = result[1]
            AmbulancePhase(rescued_count=rescued).run()
            pygame.quit()
            return result[1]   # exit simulation entirely after ambulance
        else:
            return result