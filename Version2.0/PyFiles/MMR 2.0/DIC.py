import pandas as pd

# -------------------------------
# Step 1: load the final CSV
# -------------------------------
data = pd.read_csv("Version2.0\PyFiles\MMR 2.0\player_ratings.csv")

# -------------------------------
# Step 2: create dictionary
# -------------------------------

# player_dict = dict(zip(data["player"], data["score"])) # league_rating
player_dict = dict(zip(data["player"], data["score"])) # global_rating


# -------------------------------
# Step 3: write dictionary to a .txt file
# -------------------------------
# output_file = "Version2.0\PyFiles\MMR 2.0\player_league_ratings.txt"
output_file = "Version2.0\PyFiles\MMR 2.0\player_global_ratings.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write("{\n")
    for i, (player, rating) in enumerate(player_dict.items()):
        comma = "," if i < len(player_dict)-1 else ""
        f.write(f'#    "{player}": {round(rating,2)}{comma}\n')
    f.write("}\n")

print(f"Dictionary saved to {output_file}")
