# main.py

import sys
import pygame
import numpy as np

from config import *
from environment import create_all_floors
from visualize import run_simulation
from firetruck import FiretruckPhase


def main():
    num_firefighters = 1
    max_steps        = 300
    algorithm        = "astar"
    seed             = None

    args = sys.argv[1:]
    i    = 0
    while i < len(args):
        a = args[i]
        if   a == '--firefighters' and i + 1 < len(args):
            num_firefighters = int(args[i + 1]); i += 2
        elif a == '--steps'        and i + 1 < len(args):
            max_steps = int(args[i + 1]); i += 2
        elif a == '--algorithm'    and i + 1 < len(args):
            algorithm = args[i + 1]; i += 2
        elif a == '--seed'         and i + 1 < len(args):
            seed = int(args[i + 1]); i += 2
        else:
            i += 1

    valid_algos = ("astar", "bfs", "dijkstra", "dstar_lite")
    if algorithm not in valid_algos:
        print(f"[warn] Unknown algorithm '{algorithm}'. Defaulting to astar.")
        algorithm = "astar"

    if seed is not None:
        np.random.seed(seed)
        print(f"  Seed: {seed}  (run is reproducible)")

    print("=" * 60)
    print("  AI FIREFIGHTER RESCUE SIMULATION")
    print("=" * 60)
    print(f"  Firefighters : {num_firefighters}")
    print(f"  Floors       : {NUM_FLOORS}")
    print(f"  Max steps    : {max_steps}")
    print(f"  Algorithm    : {algorithm.upper()}")
    print("=" * 60)
    print()
    print("Phase 1 — Dispatch")
    print("  Click any building on the city map to report a fire.")
    print("  The firetruck will drive to the scene, then firefighters")
    print("  will enter the building.")
    print()
    print("Phase 2 — Rescue sim controls")
    print("  SPACE       Pause / resume")
    print("  UP / DOWN   Speed")
    print("  1 / 2 / 3   View floor")
    print("  R           Reset")
    print("  ESC         Quit")
    print()
    print("CLI options:")
    print("  --firefighters N   (1–8)")
    print("  --steps N          (default 300)")
    print("  --algorithm        astar | bfs | dijkstra | dstar_lite")
    print("  --seed N")
    print()

    # ── Main loop — restart re-enters here ───────────────────────────────────
    while True:
        # Flush any stale font objects from a previous pygame.quit() so that
        # city_phase_base lazy fonts are recreated fresh this iteration.
        import city_phase_base as _cpb
        _cpb._invalidate_fonts()
        pygame.init()
        pygame.event.clear()   # discard any stale events from previous phase

        # Phase 1: city map + firetruck dispatch
        ft_phase  = FiretruckPhase()
        ft_result = ft_phase.run()

        if ft_result is None:
            # Player quit during dispatch
            pygame.quit()
            return None

        city_data, burning_road_pos = ft_result
        pygame.event.clear()   # discard events accumulated during firetruck phase

        # Phase 2 + 3: rescue sim → ambulance
        grids   = create_all_floors()
        result  = run_simulation(
            grids,
            num_firefighters = num_firefighters,
            max_steps        = max_steps,
            algorithm        = algorithm,
            city_data        = city_data,
            burning_road_pos = burning_road_pos,
        )

        if result == 'restart':
            # R pressed in ambulance phase — restart entire pipeline
            continue
        return result


if __name__ == "__main__":
    main()