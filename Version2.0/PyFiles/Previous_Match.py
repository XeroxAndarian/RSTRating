import datetime as dt
import os.path
import Find



def determine_winner(key, value):
    team_1 = key[0]
    team_2 = key[2]
    score_team_1 = value[0]
    score_team_2 = value[2]
    if score_team_1 > score_team_2:
        team_1 = True
        team_2 = False
    if score_team_1 == score_team_2:
        team_1 = team_2 = None
    if score_team_2 > score_team_1:
        team_2 = True
        team_1 = False
    return team_1, team_2    

def tournament_winner():
    Points = {"1":0, "2":0, "3":0, "4":0}
    Standings = {"1": [0, 0], "2": [0, 0], "3": [0, 0], "4": [0, 0] }
    for team in previous_match_stats()[1]: 
        Points[team] += 3 * previous_match_stats()[3][team]["win"]
        Points[team] +=  previous_match_stats()[3][team]["tie"]
    
    for team in Points:
        if Points[team] > Standings["1"][1]:
            Standings["1"] = [team, Points[team]]
        elif Points[team] == Standings["1"][1]:
            Standings["1"] += [team, Points[team]]
        elif Points[team] > Standings["2"][1]:
            Standings["2"] = [team, Points[team]]
        elif Points[team] == Standings["2"][1]:
            Standings["2"] += [team, Points[team]]
        elif Points[team] > Standings["3"][1]:
            Standings["3"] = [team, Points[team]]
        elif Points[team] == Standings["3"][1]:
            Standings["3"] += [team, Points[team]]
        else: 
            Standings["4"] = [team, Points[team]]
    
    for standing in Standings:
        for e in Standings[standing]:
            if type(e) != str:
                Standings[standing].remove(e)
    
    if len(Standings["1"]) == 1:
        return Standings["1"][0]
    else:
        return "" 



def previous_match_stats():
    PMI = {}
    Teams = {}
    Results = {}
    Results["separate"] = {}

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
        
    file = open(file_name, "r",encoding="utf-8")
    last = file.read()
    Last = last.split("\n")
    match_type = Last[0].split(",")[0]
    
    last_date = Last[1].split(",")[0]
    if match_type == "Match":
        team = 0
        team_score = 0
        Results["separate"] = {"1:2" : ""}  
        for i in range(len(Last) - 2):
            line = Last[i + 2].split(",")
            if line[0] != "":
                team +=1
                Teams[str(team)] = []
                Results[str(team)] = {"win": 0, "loss": 0, "tie": 0}   
                if team == 2:
                    Results["separate"]["1:2"] += str(team_score)
                    Results["separate"]["1:2"] += ":"     
                team_score = 0

            if line[1] == "":
                continue
            player_info = {}
            id = str(Find.find(line[1])[0])
            player_info["goal"] = len(line[2])
            player_info["ass"] = len(line[3])
            player_info["ag"] = len(line[4])
            PMI[id] = player_info
            Teams[str(team)].append(id)
            team_score += int(player_info["goal"])
            team_score -= int(player_info["ag"])
        
        Results["separate"]["1:2"] += str(team_score)
    
        for team in list(Results.keys()):
            if team != "separate":
                for match in list(Results["separate"].keys()):
                    outcome = determine_winner(match, Results["separate"][match])

                    if team == match[0]:
                        if outcome[0] == None:
                            Results[team]["tie"] += 1
                        elif outcome[0]:
                            Results[team]["win"] += 1
                        else:
                            Results[team]["loss"] += 1

                    if team == match[2]:
                        if outcome[1] == None:
                            Results[team]["tie"] += 1
                        elif outcome[1]:
                            Results[team]["win"] += 1
                        else:
                            Results[team]["loss"] += 1

    if match_type == "Tournament":
        team = 0
        i = 2
        while Last[i].split(",")[0] != "*":
            Pl = True
            line = Last[i].split(",")
            if (team == 3) & (line[4] == ""):
                break
            if line[4] == "":
                Pl = False
            if line[0] != "":
                team +=1
                Teams[str(team)] = []
                Results[str(team)] = {"win": 0, "loss": 0, "tie": 0}

            if Pl:
                player_info = {}
                id = str(Find.find(line[4])[0])
                player_info["goal"] = len(line[5])
                player_info["ass"] = len(line[6])
                player_info["ag"] = len(line[7])
                PMI[id] = player_info
                Teams[str(team)].append(id)
            i += 1
        teams = 4
        if Last[22].split(",")[6] == "":
            teams = 3


        if teams == 3:
            Results["separate"]["1:2"] = Last[24].split(",")[3]
            Results["separate"]["1:3"] = Last[25].split(",")[3]
            Results["separate"]["2:3"] = Last[26].split(",")[3]
        if teams == 4:
            Results["separate"] = {}
            Results["separate"]["1:2"] = Last[22].split(",")[6]
            Results["separate"]["1:3"] = Last[23].split(",")[6]
            Results["separate"]["1:4"] = Last[24].split(",")[6]
            Results["separate"]["2:3"] = Last[25].split(",")[6]
            Results["separate"]["2:4"] = Last[26].split(",")[6]
            Results["separate"]["3:4"] = Last[27].split(",")[6]
        
        for team in list(Results.keys()):
            if team != "separate":
                for match in list(Results["separate"].keys()):
                    outcome = determine_winner(match, Results["separate"][match])

                    if team == match[0]:
                        if outcome[0] == None:
                            Results[team]["tie"] += 1
                        elif outcome[0]:
                            Results[team]["win"] += 1
                        else:
                            Results[team]["loss"] += 1

                    if team == match[2]:
                        if outcome[1] == None:
                            Results[team]["tie"] += 1
                        elif outcome[1]:
                            Results[team]["win"] += 1
                        else:
                            Results[team]["loss"] += 1
   

    return [PMI, Teams, str(date), Results, match_type]
print(previous_match_stats())