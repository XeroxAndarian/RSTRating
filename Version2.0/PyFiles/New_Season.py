import Load
import Save


Players = Load.load()
Previous_Season = Players["season"]
New_Season = Previous_Season + 1
SEASON = "season " + str(New_Season)

Season_Template = {}
Season_Template["SR"] = 999
Season_Template["rank SR"] = 0
Season_Template["rank"] = "Unranked"
Season_Template["goals"] = 0
Season_Template["rank goals"] = 0
Season_Template["assists"] = 0
Season_Template["rank assists"] = 0
Season_Template["auto goals"] = 0
Season_Template["rank auto goals"] = 0
Season_Template["attendance"] = 0
Season_Template["rank attendance"] = 0
Season_Template["wins"] = 0
Season_Template["rank wins"] = 0
Season_Template["losses"] = 0
Season_Template["rank losses"] = 0
Season_Template["ties"] = 0
Season_Template["rank ties"] = 0
Season_Template["winrate"] = 0
Season_Template["rank winrate"] = 0
Season_Template["goal average"] = 0
Season_Template["rank goal average"] = 0
Season_Template["assist average"] = 0
Season_Template["rank assist average"] = 0
Season_Template["auto goal average"] = 0
Season_Template["rank auto goal average"] = 0
Season_Template["matches played"] = 0
Season_Template["rank matches played"] = 0
Season_Template["MVP goal"] = 0
Season_Template["rank MVP goal"] = 0
Season_Template["MVP assist"] = 0
Season_Template["rank MVP assist"] = 0
Season_Template["teammates plays"] = {} 
Season_Template["teammates wins"] = {}
Season_Template["teammates losses"] = {}
Season_Template["teammates ties"] = {}
Season_Template["title"] = []
Season_Template["highest SR"] = 0
Season_Template["tournaments won"] = 0
Season_Template["rank tournaments won"] = 0
Season_Template["weeks on top"] = 0
Season_Template["rank weeks on top"] = 0
Season_Template["consecutive weeks on top"] = 0

for player in Players:
    if player == "update":
        pass
    elif  player == "season":
        pass
    else:
        Players[player][SEASON] = Season_Template


for player in list(Players.keys()):
    if player == "update" or player == "season":
            continue
    for another in list(Players.keys()):
        if another == "update" or another == "season":
            continue
        if another != player:

            Players[another][SEASON]["teammates plays"][player] = 0
            Players[player][SEASON]["teammates plays"][another] = 0
            Players[another][SEASON]["teammates wins"][player] = 0
            Players[player][SEASON]["teammates wins"][another] = 0
            Players[another][SEASON]["teammates ties"][player] = 0
            Players[player][SEASON]["teammates ties"][another] = 0
            Players[another][SEASON]["teammates losses"][player] = 0
            Players[player][SEASON]["teammates losses"][another] = 0


Players["season"] = New_Season

Save.save(Players, True)


