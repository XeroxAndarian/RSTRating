
import Player
from datetime import date, datetime
from datetime import time 
# from TeamCalculatorVerisons import TeamCalculator


RATINGS = "Ratings.txt"
CALENDAR = "Calendar.txt"
LAST_MATCH = ""
LATEST_RESULTS = "Last.csv"
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
    for line in R_list[4:-1]:
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
    global LAST_MATCH
    LAST_MATCH = R_list[2]    
    R.close()
    return None

def extract_from_dict(id, str):
    return PLAYERS_DICT.get(id).get(str)

def update_players():

    for player in PLAYERS_LIST:
        id = player.id
        player.name = extract_from_dict(id, "Name")
        player.sur = extract_from_dict(id, "Surname")
        player.nick = extract_from_dict(id, "Nickname")
        player.g = int(extract_from_dict(id, "Goals"))
        player.a = int(extract_from_dict(id, "Assists"))
        player.w = int(extract_from_dict(id, "Wins"))
        player.l = int(extract_from_dict(id, "Loses"))
        player.atn = int(extract_from_dict(id, "- Total"))
        player.atl = extract_from_dict(id, "- Last")
        player.ag = int(extract_from_dict(id, "Autogoals"))
        player.mmr = round(player.get_mmr())

        list = []
        for i in range(Seasons):
            list.append(int(extract_from_dict(id, "- Season " + str(i+1))))
        player.sr = list
    return None

def update_last_match():
    R = open(LATEST_RESULTS, "r")
    content = R.read()
    R_list = content.split("\n")

    last_date = (R_list[1].split(","))[0]
    match_type = (R_list[0].split(","))[0]
    won = ""
    lost = ""
    draw = False
    def teams():
        teams = {}
        team_list = []
        team_name = ""
        for line in R_list[2:]:
            line_list = line.split(",")
            if line_list[0] != "":
                team_name = line_list[0]
                team_list = []
            team_list.append(find_id(line_list[1]))
            teams[team_name] = team_list
        return teams
    
    def match_result():
        results = {}
        team_score = 0
        team_name = ""
        for line in R_list[2:]:
            line_list= line.split(",")
            if line_list[0] != "":
                team_name = line_list[0]
                team_score = 0
            team_score += len(line_list[2])
            results[team_name] = team_score
        if match_type == "Match":
            won = max(results, key=results.get)
            lost =  min(results, key=results.get)
            if won == lost:
                draw = True
        return results, won, lost


    def duplicate_safety():
        global LAST_MATCH
        if (last_date != LAST_MATCH):
            LAST_MATCH = last_date
            return True
        else:
            return False

    
    if duplicate_safety():        
        for line in R_list[2:]:
            line_list = line.split(",")
            id = find_id(line_list[1])
            player = PLAYERS_LIST[id - 1]
            goals = len(line_list[2])
            assists = len(line_list[3])
            auto_goals = len(line_list[4])
            player.g += goals
            player.a += assists
            player.ag += auto_goals
            player.atl = last_date
            player.atn += 1
            if not draw:
                if player.id in teams().get(match_result()[1]):
                    player.w += 1
                else: 
                    player.l += 1
            
            

    return None

def find_id(str):
    for player in PLAYERS_LIST:
        if ((player.name == str) or (player.nick == str)):
            return int(player.id)
    


def ratings_out():
    with open(RATINGS, "w") as f:
        f.write("Player Base\n")
        f.write("" + str(datetime.now()) + "\n")
        f.write(LAST_MATCH + "\n")
        f.write("Current Season: " + str(Seasons) + "\n")
        for player in PLAYERS_LIST:
            f.write(30*"*" + "\n")
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
            f.write("MMR: " + str(player.mmr) + "\n")
            f.write("Seasons Ratings: " + "\n")
            for i in range(Seasons):
                f.write("- Season " + str(i+1) + ": " + str(player.sr[i]) + "\n")
        f.write(30*"*" + "\n")
    return None

rating_in()
update_players()
update_last_match()
ratings_out()
