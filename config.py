# config.py

ROWS = 20
COLS = 20
NUM_FLOORS = 3

EMPTY       = 0
PERSON      = 1
SHELTER     = 2       # legacy, kept for compat
FIRE        = 3
OBSTACLE    = 4
FIREFIGHTER = 5
PERSON_DANGER = 6
STAIRCASE   = 7
HOSPITAL    = 8

# --- HP ---
CIVILIAN_MAX_HP = 20   # was 15
FF_MAX_HP       = 35   # was 25

# --- Water ---
WATER_MAX       = 100  # full tank per firefighter
WATER_REFILL    = 20   # +water each hospital delivery
WATER_FIRE_STEP = 2    # drained per step standing on fire
WATER_EXTINGUISH= 10   # drained per extinguish action

# Staircase fixed positions
STAIR_ROW_START = ROWS // 2
STAIR_ROW_END   = ROWS // 2 + 1
STAIR_UP_COL    = 0
STAIR_DOWN_COL  = COLS - 1
