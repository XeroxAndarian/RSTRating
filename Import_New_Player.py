import Rating
import Season
import Player

IMPORT_FILE = "import_players.csv"
IMPORT_PLAYERS = []

def import_players():
    R = open(IMPORT_FILE, "r")
    content = R.read()
    R_list = content.split("\n")
    max_id = len(Rating.PLAYERS_LIST)
    new_id = max_id + 1
    for player in R_list[1:]:
        info_list = player.split(",")
        IP = Player.Player(
                        new_id,
                        info_list[0],
                        info_list[1],
                        info_list[2], 
                        int(info_list[3]),
                        int(info_list[4]),
                        [int(info_list[6]), ""],
                        int(info_list[5]),
                        0,
                        Season.Season(new_id),
                        int(info_list[7]),
                        int(info_list[8]))
        IMPORT_PLAYERS.append(IP)
        new_id += 1
    return None

def add_player():
    max_id = len(Rating.PLAYERS_LIST)
    with open(Rating.RATINGS, "a") as f:
        for player in IMPORT_PLAYERS:
            f.write("Player ID: " + str(player.id) + "\n")  
            f.write("Name: " + player.name + "\n")
            f.write("Surname: " + player.sur + "\n")
            f.write("Nickname: " + player.nick + "\n")
            f.write("Goals: " + str(player.g) + "\n")
            f.write("Assists: " + str(player.a) + "\n")
            f.write("Autogoals: " + str(player.ag) + "\n")
            f.write("Wins: " + str(player.w) + "\n")
            f.write("Loses: " + str(player.l) + "\n")
            f.write("Draws: " + str(player.atn - player.w - player.l) + "\n")
            f.write("Attendences:" + "\n")
            f.write("- Total: " + str(player.atn) + "\n")
            f.write("- Last: " + player.atl + "\n" )
            f.write("MMR: " + str(round(player.get_mmr())) + "\n")
            f.write("Seasons Ratings: " + "\n")
            for i in range(Rating.Seasons):
                f.write("- Season " + str(i+1) + ": " + str(0) + "\n")
            f.write(30*"*" + "\n")
    with open("Seasons/Season_" + str(Rating.Seasons) + ".txt", "a") as f:
        for player in IMPORT_PLAYERS:
            f.write(30*"*" + "\n")
            f.write("Player ID: " + str(player.id) + "\n")  
            f.write("Name: " + player.name + "\n")
            f.write("Surname: " + player.sur + "\n")
            f.write("Nickname: " + player.nick + "\n")
            f.write("Goals: " + "0" + "\n")
            f.write("Assists: " + "0" + "\n")
            f.write("Autogoals: " + "0" + "\n")
            f.write("Wins: " + "0" + "\n")
            f.write("Consecutive Wins: " + "0" + "\n")
            f.write("Winstreak: " + "0" + "\n")
            f.write("Loses: " + "0" + "\n")
            f.write("Draws: " + "0" + "\n")
            f.write("Attendences:" + "\n")
            f.write("- Total: " + "0" + "\n")
            f.write("- Last: " + "0" + "\n" )
            f.write("SR: " + "0" + "\n")
            f.write("Position: " + "\n")
            f.write("- Current: " + "0" + "\n")
            f.write("- Previous: " + "0"  + "\n")
            f.write("Leap: " + "0" + "\n")
        f.write(30*"*" + "\n")

 
    return None

Rating.rating_in()
Rating.season_in(Rating.Seasons)
import_players()
add_player()
