# main.py

import sys
import numpy as np

from config import *
from environment import create_all_floors
from visualize import run_simulation


def main():
    num_firefighters  = 1
    max_steps         = 300
    algorithm         = "astar"
    seed              = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--firefighters' and i + 1 < len(args):
            num_firefighters = int(args[i + 1]); i += 2
        elif a == '--steps' and i + 1 < len(args):
            max_steps = int(args[i + 1]); i += 2
        elif a == '--algorithm' and i + 1 < len(args):
            algorithm = args[i + 1]; i += 2
        elif a == '--seed' and i + 1 < len(args):
            seed = int(args[i + 1]); i += 2

        else:
            i += 1

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
    print("Controls:")
    print("  SPACE    Pause / resume")
    print("  UP / DOWN   Speed")
    print("  1 / 2 / 3   View floor")
    print("  R        Reset")
    print("  ESC      Quit")
    print()

    grids   = create_all_floors()
    metrics = run_simulation(
        grids,
        num_firefighters  = num_firefighters,
        max_steps         = max_steps,
        algorithm         = algorithm,

    )
    return metrics


if __name__ == "__main__":
    main()