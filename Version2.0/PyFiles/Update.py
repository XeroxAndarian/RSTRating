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
SEASON = "season " + str(Players["season"])
MVP_G = {"player":"", "count": 0}
MVP_A = {"player":"", "count": 0}
match_type = PMP["match type"]



if Players["update"] != DATE:  # Safety Check, da slucajno ne more updatat 2x isto
    Players["update"] = DATE

    for player in list(PMP.keys()):
        if player != "match type":
            Players[player]["attendance"] += 1
            Players[player][SEASON]["attendance"] += 1
            Players[player]["goal"] += PMP[player]["goal"]
            Players[player]["assist"] += PMP[player]["ass"]
            Players[player]["auto goal"] += PMP[player]["ag"]
            Players[player][SEASON]["goal"] += PMP[player]["goal"]
            Players[player][SEASON]["assist"] += PMP[player]["ass"]
            Players[player][SEASON]["auto goal"] += PMP[player]["ag"]
    
    
        
        if match_type == "Match":
            Players[player]["match played"] += 1
            Players[player][SEASON]["match played"] += 1

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
    
        

        if match_type == "Tournament":
                for team in list(PMT.keys()):
                    if player in PMT[team]:
                        Players[player]["draw"] += RESULTS[team]["draw"]
                        Players[player][SEASON]["draw"] += RESULTS[team]["draw"]
                        Players[player]["win"] += RESULTS[team]["win"]
                        Players[player][SEASON]["win"] += RESULTS[team]["win"]
                        Players[player]["loss"] += RESULTS[team]["loss"]
                        Players[player][SEASON]["loss"] += RESULTS[team]["loss"]
        
        if player != "match type":
            Players[player]["winrate"] = Players[player]["win"] / max(Players[player]["match played"], 1)
            Players[player][SEASON]["winrate"] = Players[player]["win"] / max(Players[player][SEASON]["match played"], 1)
            Players[player]["goal average"] = Players[player]["goal"] / max(Players[player]["match played"],1)
            Players[player]["assist average"] = Players[player]["assist"] / max(Players[player]["match played"],1)
            Players[player]["auto goal average"] = Players[player]["auto goal"] / max(Players[player]["match played"],1)
            Players[player][SEASON]["goal average"] = Players[player]["goal"] / max(Players[player][SEASON]["match played"],1)
            Players[player][SEASON]["assist average"] = Players[player]["assist"] / max(Players[player][SEASON]["match played"],1)
            Players[player][SEASON]["auto goal average"] = Players[player]["auto goal"] / max(Players[player][SEASON]["match played"],1)


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

            
        for player in list(PMP.keys())[:-1]:
            WR = Players[player]["winrate"]
            G = Players[player]["goal average"]
            A = Players[player]["assist average"]
            AG = Players[player]["auto goal average"]
            WS = Players[player]["winstreak"]
            mvpg = (MVP_G["player"] == player)
            mvpa = (MVP_A["player"] == player)
            Players[player]["MMR"] = MMR.MMR_calculator(WR, G, A, AG)
            Current_SR = Players[player][SEASON]["SR"]

            if match_type == "Match":
                R = Players[player]["last match played"]
                if player in PMT["1"]:
                    own = PMT["1"]
                    opp = PMT["2"]
                else:
                    own = PMT["2"]
                    opp = PMT["1"]

                Players[player][SEASON]["SR"] = SR.SR_calculator(Current_SR, R, PMP[player]["goal"], PMP[player]["ass"], PMP[player]["ag"], WS, mvpg, mvpa, own, opp)

            if match_type == "Tournament":
                Players[player][SEASON]["SR"] = SR.SR_calculator(Current_SR, "draw", PMP[player]["goal"], PMP[player]["ass"], PMP[player]["ag"], WS, mvpg, mvpa, [], [])
                for team in list(PMT.keys()):
                    if player in PMT[team]:
                        for match in list(RESULTS["separate"].keys()):
                            if team in match:
                                Players[player]["match played"] += 1
                                Players[player][SEASON]["match played"] += 1
                                outcome = Previous_Match.determine_winner(match, RESULTS["separate"][match])
                                if team == match[0]:
                                    if outcome[0] == None:
                                        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], "draw", 0, 0, 0, 0, False, False, PMT[match[0]], PMT[match[2]])
                                    elif outcome[0]:
                                        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], "win", 0, 0, 0, 0, False, False, PMT[match[0]], PMT[match[2]])
                                    else:
                                        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], "loss", 0, 0, 0, 0, False, False, PMT[match[0]], PMT[match[2]])
                                if team == match[2]:
                                    if outcome[1] == None:
                                        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], "draw", 0, 0, 0, 0, False, False, PMT[match[0]], PMT[match[2]])
                                    elif outcome[1]:
                                        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], "win", 0, 0, 0, 0, False, False, PMT[match[0]], PMT[match[2]])
                                    else:
                                        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], "loss", 0, 0, 0, 0, False, False, PMT[match[0]], PMT[match[2]])
                        
         
            if Players[player][SEASON]["SR"] < 1000:
                Players[player][SEASON]["rank"] = "Bronze"
            if Players[player][SEASON]["SR"] >= 1000:
                Players[player][SEASON]["rank"] = "Silver"
            if Players[player][SEASON]["SR"] >= 1100:
                Players[player][SEASON]["rank"] = "Gold"
            if Players[player][SEASON]["SR"] >= 1200:
                Players[player][SEASON]["rank"] = "Platinum"
            if Players[player][SEASON]["SR"] >= 1300:
                Players[player][SEASON]["rank"] = "Saphire"
            if Players[player][SEASON]["SR"] >= 1400:
                Players[player][SEASON]["rank"] = "Ruby"
            if Players[player][SEASON]["SR"] >= 1500:
                Players[player][SEASON]["rank"] = "Diamond"

          



Save.save(Players, False)
