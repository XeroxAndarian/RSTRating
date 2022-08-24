import datetime as dt
import os.path
import Find




def previous_match_stats():
    PMI = {}
    Teams = {}
    Results = {}

    # find csv from previous match
    exsists = False
    k=0
    while exsists == False:
        date = dt.date.today() - dt.timedelta(days=k)
        file_name = "Version2.0\Data\Match History\\" +  str(date) + ".csv"
        exsists = os.path.exists(file_name)
        k+=1
        if k > 10000:
            break
        
    file = open(file_name, "r")
    last = file.read()
    Last = last.split("\n")
    match_type = Last[0].split(",")[0]
    last_date = Last[1].split(",")[0]
    team = 0
    for i in range(len(Last) - 2):
        line = Last[i + 2].split(",")
        if line[0] != "":
            team +=1
            Teams[str(team)] = []
            Results[str(team)] = 0        

        player_info = {}
        id = str(Find.find(line[1])[0])
        player_info["goal"] = len(line[2])
        player_info["ass"] = len(line[3])
        player_info["ag"] = len(line[4])
        PMI[id] = player_info
        Teams[str(team)].append(id)
        Results[str(team)] += player_info["goal"]

    if team == 2:
        if Results["1"] > Results["2"]:
            Results["Win"] = "1"
            Results["Loss"] = "2"
        elif Results["1"] < Results["2"]:
            Results["Win"] = "2"
            Results["Loss"] = "1"
        else:
            Results["Win"] = "0"
            Results["Loss"] = "0"

    return [PMI, Teams, str(date), Results]

