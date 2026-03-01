# visualize.py

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import numpy as np

from fire import spread_fire
from firefighter import move_firefighter
from config import *


# --------------------------------------------------
# 🔥 Animated Fire Colormap
# --------------------------------------------------
def get_fire_cmap(frame):

    # fire flicker animation
    fire_phase = frame % 3

    fire_colors = [
        "#ff2b2b",  # deep red
        "#ff6b00",  # orange
        "#ffd000"   # yellow glow
    ]

    fire_color = fire_colors[fire_phase]

    colors = [
        "#2e2e2e",  # EMPTY
        "#00ff88",  # PERSON
        "#00e5ff",  # SHELTER
        fire_color, # FIRE (animated)
        "#111111",  # OBSTACLE
        "#ff9f1c",  # FIREFIGHTER
        "#b266ff"   # PERSON IN DANGER
    ]

    return ListedColormap(colors)


# --------------------------------------------------
# 🚒 Simulation Runner
# --------------------------------------------------
def run_simulation(grid):

    fig, ax = plt.subplots(figsize=(7, 6))

    # initial colormap
    cmap = get_fire_cmap(0)

    img = ax.imshow(grid, cmap=cmap, vmin=0, vmax=6)
    ax.set_title("AI Firefighter Rescue Simulation")

    # ---------- LEGEND ----------
    legend_items = [
        mpatches.Patch(color="#2e2e2e", label="Empty Area"),
        mpatches.Patch(color="#00ff88", label="Person (Safe)"),
        mpatches.Patch(color="#b266ff", label="Person in Danger"),
        mpatches.Patch(color="#00e5ff", label="Shelter / Exit"),
        mpatches.Patch(color="#ff2b2b", label="Fire"),
        mpatches.Patch(color="#111111", label="Obstacle"),
        mpatches.Patch(color="#ff9f1c", label="Firefighter"),
    ]

    ax.legend(handles=legend_items,
              bbox_to_anchor=(1.05, 1),
              loc="upper left")

    # ---------- STATUS PANEL ----------
    status_text = ax.text(
        1.05,
        0.5,
        "",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
    )

    step = 0

    # --------------------------------------------------
    # UPDATE LOOP
    # --------------------------------------------------
    def update(frame):
        nonlocal grid, step

        step += 1

        # 🔥 fire spreads slowly
        grid = spread_fire(grid, step)

        # 🚒 firefighter acts
        grid = move_firefighter(grid)

        # 🔥 APPLY FIRE FLICKER
        img.set_cmap(get_fire_cmap(step))
        img.set_data(grid)

        # ---------- LIVE STATISTICS ----------
        people_safe = np.sum(grid == PERSON)
        people_danger = np.sum(grid == PERSON_DANGER)
        fire_cells = np.sum(grid == FIRE)

        status_text.set_text(
            f"Step: {step}\n"
            f"Safe People: {people_safe}\n"
            f"People in Danger: {people_danger}\n"
            f"Fire Cells: {fire_cells}"
        )

        return [img, status_text]

    # ---------- ANIMATION ----------
    ani = FuncAnimation(
        fig,
        update,
        frames=300,
        interval=400,
        repeat=False,
    )

    plt.show()