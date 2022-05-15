import Rating
import Player
from datetime import date, datetime
from datetime import time 

def player_out(id):
    ## We makin' solo exports at the end
    file_name = "Player Stats\\" + str(id) + "_player_stats.txt"
    max_id = len(Rating.PLAYERS_LIST)
    if (id < 0) or (id > max_id):
        print("Please choose a valid id, between 0 and " + str(max_id))
    else:
        player = Rating.PLAYERS_LIST[id - 1]
        with open(file_name, "w") as f:
            f.write("Player Stats\n")
            f.write("" + str(datetime.now()) + "\n")
            f.write(30*"*" + "\n")
            f.write("Player ID: " + str(player.id) + "\n")  
            f.write("Name: " + player.name + "\n")
            f.write("Surname: " + player.sur + "\n")
            f.write("Nickname: " + player.nick + "\n")
            f.write(30*"-" + "\n")
            f.write("Goals: " + str(player.g) + "\n")
            f.write("Average Goals per match: " + str(player.g_avg()) + "\n")
            f.write("Assists: " + str(player.a) + "\n")
            f.write("Autogoals: " + str(player.ag) + "\n")
            f.write("Wins: " + str(player.w) + "\n")
            f.write("Loses: " + str(player.l) + "\n")
            f.write("Draws: " + str(player.atn - player.w - player.l) + "\n")
            f.write("Attendences:" + "\n")
            f.write("- Total: " + str(player.atn) + "\n")
            f.write("- Last: " + player.atl + "\n" )
            f.write("MMR: " + str(player.mmr) + "\n")
            f.write("Seasons Ratings: " + "\n")
            for i in range(Rating.Seasons):
                f.write("- Season " + str(i+1) + ": " + str(player.sr[i]) + "\n")
            f.write(30*"*")
        return None
def player_out_all():
    max_id = len(Rating.PLAYERS_LIST)
    for id in range(max_id):
        player_out(id + 1)

print("Welcome to player stats export. Please choose number before the preffered option:")
print("1 - Print stats for all players in database.")
print("2 - Print specific player's stats.")
a = input("Choose your preffered option (1 or 2): ")
if a == "1":
    player_out_all()
elif a == "2":
    player_out(int(input("Type an id of wanted player: ")))
else:
    print("Please choose 1 or 2. Relaunch report creator and this time, try to follow instructions... :) ")