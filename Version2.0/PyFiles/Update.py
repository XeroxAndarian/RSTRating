import Load
import Save
import datetime as dt
import Previous_Match
import MMR
import SR


Players = Load.load()
Previous = Previous_Match.previous_match_stats()
PMP = Previous[0] # Previous Match Players
PMT = Previous[1] # Previous Match Teams
DATE = Previous[2] # Previous Match Date
RESULTS = Previous[3] # Previous Match Results
SEASON = "season" + str(Players["season"])
MVP_G = {"player":"", "count": 0}
MVP_A = {"player":"", "count": 0}


Players["update"] = DATE

if Players["update"] != DATE:  # Safety Check, da slucajno ne more updatat 2x isto

    for player in list(PMP.keys()):
        Players[player]["attendance"] += 1
        Players[player]["goal"] += PMP[player]["goal"]
        Players[player]["assist"] += PMP[player]["ass"]
        Players[player]["auto goal"] += PMP[player]["ag"]
        attendance = Players[player]["attendance"]
        attendance_S = Players[player][SEASON]["attendance"]
        

        if RESULTS["Win"] == "0":
            Players[player]["draw"] += 1
            Players[player][SEASON]["draw"] += 1
            Players[player]["winsrteak"] = 0
            Players[player]["last match played"] = "draw"
        elif player in PMT[(RESULTS["Win"])]:
            Players[player]["win"] += 1
            Players[player][SEASON]["win"] += 1
            Players[player]["winsrteak"] += 1
            Players[player]["last match played"] = "win"
        else:
            Players[player]["loss"] += 1
            Players[player][SEASON]["loss"] += 1
            Players[player]["winsrteak"] = 0
            Players[player]["last match played"] = "loss"


        Players[player]["winrate"] = Players[player]["win"] / max(attendance, 1)
        Players[player]["goal average"] = Players[player]["goal"] / max(attendance,1)
        Players[player]["assist average"] = Players[player]["assist"] / max(attendance,1)
        Players[player]["auto goal average"] = Players[player]["auto goal"] / max(attendance,1)
        Players[player][SEASON]["winrate"] = Players[player]["win"] / max(attendance, 1)
        Players[player][SEASON]["goal average"] = Players[player]["goal"] / max(attendance,1)
        Players[player][SEASON]["assist average"] = Players[player]["assist"] / max(attendance,1)
        Players[player][SEASON]["auto goal average"] = Players[player]["auto goal"] / max(attendance,1)


        if MVP_G["count"] < PMP[player]["goal"]:
            MVP_G["count"] = PMP[player]["goal"]
            MVP_G["player"] == player

        if MVP_G["count"] == PMP[player]["goal"]:
            MVP_G["player"] == ""


        if MVP_A["count"] < PMP[player]["goal"]:
            MVP_A["count"] = PMP[player]["goal"]
            MVP_A["player"] == player

        if MVP_A["count"] == PMP[player]["goal"]:
            MVP_A["player"] == ""

            
    for player in list(PMP.keys()):
        WR = Players[player]["winrate"]
        G = Players[player]["goal average"]
        A = Players[player]["assist average"]
        AG = Players[player]["auto goal average"]
        WS = Players[player]["winstreak"]
        MVP_G = (MVP_G["player"] == player)
        MVP_A = (MVP_A["player"] == player)
        R = Players[player]["last match played"]
        if player in PMT["1"]:
            own = PMT["1"]
            opp = PMT["2"]
        else:
            own = PMT["2"]
            opp = PMT["1"]

        Players[player]["MMR"] = MMR.MMR_calculator(WR, G, A, AG)
        Current_SR = Players[player][SEASON]["SR"]
        Players[player][SEASON]["SR"] = SR.SR_calculator(Current_SR, R, G, A, AG, WS, MVP_G, MVP_A, own, opp)

        if Players[player]["SR"] < 1000:
            Players[player]["rank"] = "Bronze"
        if Players[player]["SR"] < 1100:
            Players[player]["rank"] = "Silver"
        if Players[player]["SR"] < 1200:
            Players[player]["rank"] = "Gold"
        if Players[player]["SR"] < 1300:
            Players[player]["rank"] = "Platinum"
        if Players[player]["SR"] < 1400:
            Players[player]["rank"] = "Saphire"
        if Players[player]["SR"] < 1500:
            Players[player]["rank"] = "Ruby"
        if Players[player]["SR"] > 1499:
            Players[player]["rank"] = "Diamond"

          








Save.save(Players, False)