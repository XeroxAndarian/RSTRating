import pandas as pd
from hierarchical_rating_model import fit_hierarchical_map


# 1. Load your test data
data = pd.read_csv("Version2.0\PyFiles\MMR 2.0\sample_league_data.csv")
# data = pd.read_csv("Version2.0\PyFiles\MMR 2.0\league_data.csv")

# 2. Prepare the input arrays
y = data["score"].values
# map league names to numeric ids
league_to_id = {name: i for i, name in enumerate(data["league"].unique())}
league_idx = data["league"].map(league_to_id).values

# 3. Fit the model
fit = fit_hierarchical_map(y, league_idx,
                           mu_global=1500,          
                           sigma_obs=50,
                           sigma_player=200,
                           sigma_league=100)

# 4. Merge results back into your data
data["adjusted_score"] = fit["theta_map"]
data["score_std"] = fit["theta_std"]

# 5. Show results
print("\nAdjusted player scores:")
print(data.sort_values("adjusted_score", ascending=False).head(10))

print("\nEstimated league means:")
for league, mu in fit["mu_map_by_label"].items():
    print(f"  League {league}: {mu:.2f} ± {fit['mu_std_by_label'][league]:.2f}")

# 6. Save output CSVs
data.to_csv("Version2.0\PyFiles\MMR 2.0\player_ratings.csv", index=False)
pd.DataFrame({
    "league": list(fit["mu_map_by_label"].keys()),
    "league_mu": list(fit["mu_map_by_label"].values()),
    "league_mu_std": list(fit["mu_std_by_label"].values())
}).to_csv("Version2.0\PyFiles\MMR 2.0\league_ratings.csv", index=False)

print("\nSaved results:")
print("  player_ratings.csv")
print("  league_ratings.csv")
