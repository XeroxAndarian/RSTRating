import Load
import Save


Players = Load.load()
Previous_Season = Players["season"]
New_Season = Previous_Season + 1
SEASON = "season " + str(New_Season)

Season_Template = {}
Season_Template["SR"] = 999
Season_Template["rank"] = "Unranked"
Season_Template["goal"] = 0
Season_Template["assist"] = 0
Season_Template["auto goal"] = 0
Season_Template["attendance"] = 0
Season_Template["standing"] = 0
Season_Template["win"] = 0
Season_Template["loss"] = 0
Season_Template["draw"] = 0
Season_Template["winrate"] = 0
Season_Template["goal average"] = 0
Season_Template["assist average"] = 0
Season_Template["auto goal average"] = 0


for player in list(Players.keys()):
    if player == "update":
        pass
    elif  player == "season":
        pass
    else:
        Players[player][SEASON] = Season_Template

Players["season"] = New_Season

Save.save(Players, True)


