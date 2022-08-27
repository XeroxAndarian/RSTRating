


def match_analysis(team, comp, score):
    if team not in comp:
        return None
    else:
        Ana = {}
        Teams = [comp[0], comp[2]]
        Ana[Teams[0]] = {}
        Ana[Teams[1]] = {}
        Ana[Teams[0]]["score"] = int(score[0])
        Ana[Teams[1]]["score"] = int(score[2])

        for t in Teams:
            if team == t:
                if Ana[Teams[0]]["score"] > Ana[Teams[1]]["score"]:
                    return 1
                    
                if Ana[Teams[0]]["score"] == Ana[Teams[1]]["score"]:
                    return 0
                    
                if Ana[Teams[0]]["score"] < Ana[Teams[1]]["score"]:
                    return -1
                    



a = match_analysis("2", "1:2", "2:3")