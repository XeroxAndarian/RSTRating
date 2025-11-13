import numpy as np
from scipy.stats import norm

import Load
players = []
Players = Load.load()
for player in Players:
    if type(Players[player]) != dict:
        continue
    stats = {}
    stats["id"] = Players[player]["id"]
    stats["name"] = Players[player]["name"] + Players[player]["surname"]
    stats["winrate"] = Players[player]["winrate"]
    stats["goals"] = Players[player]["goal average"]
    stats["assists"] = Players[player]["assist average"]
    stats["own_goals"] = Players[player]["auto goal average"]
    players.append(stats)


# Example player data
# players = [
#     {"id": "Alice", "winrate": 0.8, "goals": 10, "assists": 5, "own_goals": 1},
#     {"id": "Bob", "winrate": 0.6, "goals": 8, "assists": 3, "own_goals": 0},
#     {"id": "Charlie", "winrate": 0.9, "goals": 15, "assists": 7, "own_goals": 2},
#     {"id": "David", "winrate": 0.5, "goals": 5, "assists": 2, "own_goals": 1},
#     {"id": "Eve", "winrate": 0.7, "goals": 9, "assists": 4, "own_goals": 0},
# ]

# Step 1: compute combined score (weighted sum)
weights = {"winrate": 6, "goals": 2, "assists": 1, "own_goals": 1}  # example weights

for player in players:
    player["score"] = (
        player["winrate"] * weights["winrate"] +
        player["goals"] * weights["goals"] +
        player["assists"] * weights["assists"] -
        player["own_goals"] * weights["own_goals"]
    )

# Step 2: rank players by score
players_sorted = sorted(players, key=lambda x: x["score"])

n = len(players_sorted)

# Step 3: convert rank to percentile and map to normal
mu_target = 1000   # target mean for rating
sigma_target = 50  # target standard deviation for rating

for idx, player in enumerate(players_sorted, start=1):
    percentile = idx / (n + 1)  # avoid 0 or 1
    z_score = norm.ppf(percentile)  # map to standard normal
    rating = mu_target + sigma_target * z_score
    player["rating"] = round(rating)

# Step 4: print results
print("Player Ratings:")
for player in sorted(players_sorted, key=lambda x: -x["rating"]):
    print(f"{player['id']}: {player['rating']} (score: {player['score']})")
