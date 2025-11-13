import numpy as np
import pandas as pd
import csv
from scipy.stats import norm

# -------------------------------
# Step 0: load your player data
# -------------------------------
import Load

players = []
Players = Load.load()
for player in Players:
    if type(Players[player]) != dict:
        continue
    stats = {}
    stats["id"] = Players[player]["id"]
    stats["name"] = Players[player]["name"] + " " + Players[player]["surname"]
    stats["winrate"] = Players[player]["winrate"]
    stats["goals"] = Players[player]["goal average"]
    stats["assists"] = Players[player]["assist average"]
    stats["own_goals"] = Players[player]["auto goal average"]
    stats["league"] = Players[player].get("league", "DefaultLeague")
    players.append(stats)

# -------------------------------
# Step 1: compute weighted score
# -------------------------------
weights = {"winrate": 6, "goals": 2, "assists": 1, "own_goals": 1}

for player in players:
    # Ensure all stats are numeric
    for key in ["winrate", "goals", "assists", "own_goals"]:
        if not isinstance(player[key], (int, float)):
            player[key] = 0
    player["score"] = (
        player["winrate"] * weights["winrate"] +
        player["goals"] * weights["goals"] +
        player["assists"] * weights["assists"] -
        player["own_goals"] * weights["own_goals"]
    )

# Step 1.2: rank players by score
players_sorted = sorted(players, key=lambda x: x["score"])

n = len(players_sorted)

# Step 1.3: convert rank to percentile and map to normal
mu_target = 1500  # target mean for rating
sigma_target = 50  # target standard deviation for rating

for idx, player in enumerate(players_sorted, start=1):
    percentile = idx / (n + 1)  # avoid 0 or 1
    z_score = norm.ppf(percentile)  # map to standard normal
    rating = mu_target + sigma_target * z_score
    player["score"] = round(rating)



# -------------------------------
# Step 2: export CSV for hierarchical model
# -------------------------------
csv_file = "Version2.0\PyFiles\MMR 2.0\league_data.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["league", "player", "score"])
    writer.writeheader()
    for player in players:
        writer.writerow({
            "league": player["league"],
            "player": player["name"],
            "score": player["score"]
        })

print(f"CSV exported for hierarchical model: {csv_file}")

# -------------------------------
# Step 3: load CSV and clean data
# -------------------------------
from hierarchical_rating_model import fit_hierarchical_map

data = pd.read_csv(csv_file)

# Remove NaNs/Infs in score
data = data.replace([np.inf, -np.inf], np.nan)
data = data.dropna(subset=["score"]).reset_index(drop=True)

# Map leagues to numeric IDs
league_to_id = {name: i for i, name in enumerate(data["league"].unique())}
league_idx = data["league"].map(league_to_id).values
y = data["score"].values

# -------------------------------
# Step 4: compute sigmas safely
# -------------------------------
sigma_obs = np.std(y)/2 + 1e-6
sigma_player = np.std(y)/1.5 + 1e-6
sigma_league = np.std([data[data["league"]==l]["score"].mean() for l in data["league"].unique()]) + 1e-6

# -------------------------------
# Step 5: fit hierarchical model
# -------------------------------
fit = fit_hierarchical_map(
    y, league_idx,
    mu_global=np.mean(y),
    sigma_obs=sigma_obs,
    sigma_player=sigma_player,
    sigma_league=sigma_league
)

# -------------------------------
# Step 6: attach global ratings
# -------------------------------
data["global_rating"] = fit["theta_map"]
data["rating_std"] = fit["theta_std"]

# -------------------------------
# Step 7: save final CSVs
# -------------------------------
data.to_csv("Version2.0\PyFiles\MMR 2.0\player_ratings.csv", index=False)
pd.DataFrame({
    "league": list(fit["mu_map_by_label"].keys()),
    "league_mu": list(fit["mu_map_by_label"].values()),
    "league_mu_std": list(fit["mu_std_by_label"].values())
}).to_csv("league_ratings.csv", index=False)

print("Final CSVs saved:")
print("  - player_ratings.csv (global ratings)")
print("  - league_ratings.csv (league strength estimates)")

# Optional: print top 10 players globally
print("\nTop 10 players by global rating:")
top10 = data.sort_values("global_rating", ascending=False).head(10)
all = data.sort_values("global_rating", ascending=False)
print(all[["player", "league", "score", "global_rating"]])


