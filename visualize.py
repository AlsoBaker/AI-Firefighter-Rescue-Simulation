# visualize.py

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import numpy as np

from fire import spread_fire
from firefighter import move_firefighter, initialize_firefighters, get_firefighter_stats
from metrics import SimulationMetrics
from config import *


def get_fire_cmap(frame):
    """Animated fire colormap with flicker effect"""
    fire_phase = frame % 3
    fire_colors = ["#ff2b2b", "#ff6b00", "#ffd000"]
    fire_color = fire_colors[fire_phase]
    
    colors = [
        "#2e2e2e",  # EMPTY
        "#00ff88",  # PERSON
        "#00e5ff",  # SHELTER
        fire_color, # FIRE (animated)
        "#111111",  # OBSTACLE
        "#ff9f1c",  # FIREFIGHTER
        "#b266ff"   # PERSON_DANGER
    ]
    return ListedColormap(colors)


def run_simulation(grid, num_firefighters=1, max_steps=300, algorithm="astar", use_extinguishing=True, use_zones=True):
    """Enhanced simulation runner with metrics"""
    
    # Initialize firefighters
    grid = initialize_firefighters(grid, num_firefighters, algorithm=algorithm)
    
    # Metrics tracking
    metrics = SimulationMetrics()
    total_people = np.sum(grid == PERSON) + np.sum(grid == PERSON_DANGER)
    metrics.initial_people_count = total_people
    
    # Setup figure with improved layout
    fig = plt.figure(figsize=(16, 8))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

    # Main grid visualization (top left, large)
    ax_grid = fig.add_subplot(gs[0:2, 0])
    cmap = get_fire_cmap(0)
    img = ax_grid.imshow(grid, cmap=cmap, vmin=0, vmax=6)
    ax_grid.set_title("AI Firefighter Rescue Simulation", fontsize=14, fontweight='bold')
    ax_grid.set_xticks([])
    ax_grid.set_yticks([])

    # Legend
    legend_items = [
        mpatches.Patch(color="#2e2e2e", label="Empty"),
        mpatches.Patch(color="#00ff88", label="Person (Safe)"),
        mpatches.Patch(color="#b266ff", label="Person in Danger"),
        mpatches.Patch(color="#00e5ff", label="Shelter"),
        mpatches.Patch(color="#ff2b2b", label="Fire"),
        mpatches.Patch(color="#111111", label="Obstacle"),
        mpatches.Patch(color="#ff9f1c", label="Firefighter"),
    ]
    ax_grid.legend(handles=legend_items, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9)

    # Metrics panel (top right)
    ax_stats = fig.add_subplot(gs[0, 1])
    ax_stats.axis('off')

    # Status text
    status_text = ax_stats.text(
        0.05, 0.95, "", transform=ax_stats.transAxes,
        fontsize=10, verticalalignment="top", fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3)
    )

    # Fire spread graph (bottom right, top)
    ax_fire = fig.add_subplot(gs[1, 1])
    ax_fire.set_title("Fire Spread Over Time", fontsize=11, fontweight='bold')
    ax_fire.set_ylabel("Fire Cells")
    ax_fire.set_xlabel("Steps")
    fire_line, = ax_fire.plot([], [], color='red', linewidth=2, label='Fire')
    ax_fire.set_ylim(0, ROWS*COLS*0.5)
    ax_fire.grid(True, alpha=0.3)
    ax_fire.legend()

    # Rescue graph (not visible but for future use)
    rescue_line = None
    danger_line = None
    
    step = 0
    simulation_active = True
    end_reason = ""
    
    # ------ UPDATE LOOP ------
    def update(frame):
        nonlocal grid, step, simulation_active, end_reason
        
        if not simulation_active:
            return [img, status_text]
        
        step += 1
        
        # Spread fire
        grid = spread_fire(grid, step)
        
        # Move firefighters
        grid = move_firefighter(grid)
        
        # Update metrics
        stats = metrics.update(grid)
        
        # Visual update
        img.set_cmap(get_fire_cmap(step))
        img.set_data(grid)
        
        # Check end conditions
        people_safe = stats['safe']
        people_danger = stats['danger']
        fire_cells = stats['fire']

        # All rescued
        if people_safe == 0 and people_danger == 0:
            metrics.people_rescued = total_people
            simulation_active = False
            end_reason = "✅ All people rescued!"
        
        # Max steps reached
        if step >= max_steps:
            metrics.people_burned = people_safe + people_danger
            simulation_active = False
            end_reason = "⏱️  Max steps reached"
        
        # Prepare status text
        ff_stats = get_firefighter_stats(grid)
        
        status_str = (
            f"SIMULATION STATUS\n"
            f"{'─'*30}\n"
            f"Step: {step}/{max_steps}\n"
            f"Safe People: {people_safe}\n"
            f"In Danger: {people_danger}\n"
            f"Fire Cells: {fire_cells}\n"
            f"{'─'*30}\n"
            f"Total Rescued: {ff_stats.get('rescued', 0)}\n"
            f"Firefighters: {ff_stats.get('firefighters', 1)}\n"
        )
        
        if not simulation_active:
            status_str += (
                f"{'─'*30}\n"
                f"{end_reason}\n"
                f"Final Rescue Rate: {(metrics.people_rescued/total_people*100):.1f}%\n"
                f"Score: {metrics.calculate_score(total_people):.0f}/1500"
            )
        
        status_text.set_text(status_str)
        
        # Update graphs
        graph_data = metrics.get_graph_data()
        if graph_data['fire']:
            fire_line.set_data(graph_data['steps'], graph_data['fire'])
            ax_fire.set_xlim(0, max(len(graph_data['steps']), max_steps))
        
        return [img, status_text]
    
    # Create animation
    ani = FuncAnimation(
        fig, update,
        frames=max_steps,
        interval=200,
        repeat=False,
        blit=False
    )
    
    plt.tight_layout()
    plt.show()
    
    # Print final report
    metrics.print_report(total_people, get_firefighter_stats(grid))
    
    return metrics
