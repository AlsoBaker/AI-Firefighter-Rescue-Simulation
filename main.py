# main.py

from environment import create_environment
from visualize import run_simulation
import sys


def main():
    """
    Enhanced main with full configuration options
    
    Usage:
        python main.py                                    # default
        python main.py --firefighters 2                   # 2 firefighters
        python main.py --steps 500                        # 500 steps
        python main.py --algorithm astar --firefighters 3 # Algorithm selection
        python main.py --no-extinguish                    # Disable features
        python main.py --no-zones                         # Disable zones
    """
    
    # Default configuration
    num_firefighters = 1
    max_steps = 300
    algorithm = "astar"  # NEW: default algorithm
    use_extinguishing = True  # NEW: feature flags
    use_zones = True
    
    # Parse command line arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--firefighters' and i + 1 < len(args):
            num_firefighters = int(args[i + 1])
            i += 2
        elif args[i] == '--steps' and i + 1 < len(args):
            max_steps = int(args[i + 1])
            i += 2
        elif args[i] == '--algorithm' and i + 1 < len(args):  # NEW
            algorithm = args[i + 1]
            i += 2
        elif args[i] == '--no-extinguish':  # NEW
            use_extinguishing = False
            i += 1
        elif args[i] == '--no-zones':  # NEW
            use_zones = False
            i += 1
        else:
            i += 1
    
    print("="*60)
    print("🚒 FIREFIGHTER RESCUE SIMULATION 🔥")
    print("="*60)
    print(f"Configuration:")
    print(f"  Firefighters: {num_firefighters}")
    print(f"  Max Steps: {max_steps}")
    print(f"  Algorithm: {algorithm.upper()}")
    print(f"  Fire Extinguishing: {'ENABLED' if use_extinguishing else 'DISABLED'}")
    print(f"  Evacuation Zones: {'ENABLED' if use_zones else 'DISABLED'}")
    print("="*60 + "\n")
    
    # Create environment and run simulation
    grid = create_environment()
    metrics = run_simulation(
        grid, 
        num_firefighters=num_firefighters, 
        max_steps=max_steps,
        algorithm=algorithm,
        use_extinguishing=use_extinguishing,
        use_zones=use_zones
    )
    
    return metrics


if __name__ == "__main__":
    main()