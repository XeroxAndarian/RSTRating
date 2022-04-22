
import Player
from datetime import date, datetime
from datetime import time 
# from TeamCalculatorVerisons import TeamCalculator


RATINGS = "Ratings.txt"
PLAYERS_DICT = {}
PLAYERS_LIST = []
Seasons = 0

def rating_in():
    '''Fills up PLAYERS_DICT dictionary and PLAYERS_LIST with Ratings until the last update.'''
    global Seasons
    R = open(RATINGS, "r")
    content = R.read()
    R_list = content.split("\n")
    id = 0
    pl = {}
    for line in R_list[2:]:
        if line == 30*"*":
            if id > 0:
                PLAYERS_DICT[id] = pl.copy()
                PLAYERS_LIST.append(Player.Player(id))
            id += 1
            continue
        else:
            sublist = line.split(":")
            info = sublist[0]
            if "Season" in info:
                season_number_extractor = info.split(" ")
                if season_number_extractor[0] == "-":
                    Seasons = int(season_number_extractor[2])   
            value = sublist[1].replace(" ", "")
            pl[info] = value
    R.close()
    return None

def update_players():

    def extract_from_dict(id, str):
        return PLAYERS_DICT.get(id).get(str)

    for player in PLAYERS_LIST:
        id = player.id
        player.name = extract_from_dict(id, "Name")
        player.sur = extract_from_dict(id, "Surname")
        player.nick = extract_from_dict(id, "Nickname")
        player.g = extract_from_dict(id, "Goals")
        player.a = extract_from_dict(id, "Assists")
        player.atn = extract_from_dict(id, "- Total")
        player.atl = extract_from_dict(id, "- Last")
        player.ag = extract_from_dict(id, "Autogoals")
        player.mmr = extract_from_dict(id, "MMR")

        list = []
        for i in range(Seasons):
            list.append(extract_from_dict(id, "- Season " + str(i+1)))
        player.sr = list
    return None

def ratings_out():
    with open(RATINGS, "w") as f:
        f.write("Player Base\n")
        f.write("" + str(datetime.now()) + "\n")
        for player in PLAYERS_LIST:
            f.write(30*"*" + "\n")
            f.write("Player ID: " + str(player.id) + "\n")  
            f.write("Name: " + player.name + "\n")
            f.write("Surname: " + player.sur + "\n")
            f.write("Nickname: " + player.nick + "\n")
            f.write("Goals: " + player.g + "\n")
            f.write("Assists: " + player.a + "\n")
            f.write("Autogoals: " + player.ag + "\n")
            f.write("Attendences:" + "\n")
            f.write("- Total: " + player.atn + "\n")
            f.write("- Last: " + player.atl + "\n" )
            f.write("MMR: " + player.mmr + "\n")
            f.write("Seasons Ratings: " + "\n")
            for i in range(Seasons):
                f.write("- Season " + str(i+1) + ": " + player.sr[i] + "\n")
        f.write(30*"*")
        

rating_in()
update_players()
ratings_out()