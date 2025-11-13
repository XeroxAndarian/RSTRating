import pandas as pd
import numpy as np
import string

np.random.seed(42)  # reproducible randomness

# Define leagues and players
leagues = {
    "I": list("ABCDEFGH"),      # 8 players
    "II": list("DEFGHIJKLMNOP"),# 12 players
    "III": list("GHIJKLMNOPQRS")# 13 players
}

# Generate random scores between 2 and 13 for each league
rows = []
for league, players in leagues.items():
    for player in players:
        score = np.random.randint(1200, 1800)
        rows.append({"league": league, "player": player, "score": score})

df = pd.DataFrame(rows)

# Save to CSV
df.to_csv("Version2.0\PyFiles\MMR 2.0\sample_league_data.csv", index=False)

print(df)

