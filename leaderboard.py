# leaderboard.py

import json
import os
from datetime import datetime

SCORES_FILE = "scores.json"
MAX_ENTRIES = 10


def load_scores():
    if not os.path.exists(SCORES_FILE):
        return []
    try:
        with open(SCORES_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def save_score(score, rescued, total_people, steps, algorithm, num_floors):
    """
    Saves entry, keeps top MAX_ENTRIES sorted by score.
    Returns 1-based rank if it made the board, else None.
    """
    entry = {
        "score":     round(float(score), 1),
        "rescued":   int(rescued),
        "total":     int(total_people),
        "steps":     int(steps),
        "algorithm": str(algorithm).upper(),
        "floors":    int(num_floors),
        "date":      datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    scores = load_scores()
    scores.append(entry)
    scores.sort(key=lambda e: e["score"], reverse=True)
    scores = scores[:MAX_ENTRIES]

    try:
        with open(SCORES_FILE, "w") as f:
            json.dump(scores, f, indent=2)
    except IOError as exc:
        print(f"[leaderboard] could not save: {exc}")

    for i, e in enumerate(scores):
        if (e["score"] == entry["score"] and
                e["date"] == entry["date"] and
                e["steps"] == entry["steps"]):
            return i + 1
    return None


def get_top_scores():
    return load_scores()
