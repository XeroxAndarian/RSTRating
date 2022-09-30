import re


def match_analysis(team, comp, score):
    if team not in comp:
        return None
    else:
        Ana = {}
        Teams = [comp[0], comp[2]]
        Score = score.split(":")
        Ana[Teams[0]] = {}
        Ana[Teams[1]] = {}
        Ana[Teams[0]]["score"] = int(Score[0])
        Ana[Teams[1]]["score"] = int(Score[1])
        if team == Teams[0]:
            other = Teams[1]
        if team == Teams[1]:
            other = Teams[0]
        for t in Teams:
            if team == t:
                if Ana[team]["score"] > Ana[other]["score"]:
                    return 1
                    
                if Ana[team]["score"] == Ana[other]["score"]:
                    return 0
                    
                if Ana[team]["score"] < Ana[other]["score"]:
                    return -1
                    



a = match_analysis("2", "1:2", "2:3")
b = match_analysis("1", "1:2", "2:3")
c = match_analysis("1", "1:2", "2:2")
d = match_analysis("2", "1:2", "2:2")