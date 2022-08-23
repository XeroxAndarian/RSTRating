import Load
import Save
import datetime as dt
import Previous_Match
import MMR


Players = Load.load()
Previous_Match = Previous_Match.last_match_stats()
PMP = Previous_Match[0] # Previous Match Players
PMT = Previous_Match[1] # Previous Match Teams
DATE = Previous_Match[2] # Previous Match Date
RESULTS = Previous_Match[3] # Previous Match Results

Players["update"] = DATE

if Players["update"] != DATE:  # Safety Check, da slucajno ne more updatat 2x isto

    for player in list(PMP.keys()):
        Players[player]["attendence"] += 1
        Players[player]["goal"] += PMP[player]["goal"]
        Players[player]["assist"] += PMP[player]["ass"]
        Players[player]["auto goal"] += PMP[player]["ag"]
        attendence = Players[player]["attendence"]
        goals = Players[player]["goal"] 
        assists = Players[player]["assist"]

        if RESULTS["Win"] == "0":
            Players[player]["draw"] += 1
        elif player in PMT[(RESULTS["Win"])]:
            Players[player]["win"] += 1
        else:
            Players[player]["loss"] += 1

        Players[player]["winrate"] = Players[player]["win"] / max(attendence, 1)
        Players[player]["goal average"] = Players[player]["goal"] / max(attendence,1)
        Players[player]["assist average"] = Players[player]["assist"] / max(attendence,1)
        Players[player]["auto goal average"] = Players[player]["auto goal"] / max(attendence,1)


        WR = Players[player]["winrate"]
        G = Players[player]["goal average"]
        A = Players[player]["assist average"]
        AG = Players[player]["auto goal average"]

        Players[player]["MMR"] = MMR.MMR_calculator(WR, G, A, AG)



Save.save(Players, False)
