# main.py

from environment import create_environment
from visualize import run_simulation

def main():

    grid = create_environment()
    run_simulation(grid)

if __name__ == "__main__":
    main()