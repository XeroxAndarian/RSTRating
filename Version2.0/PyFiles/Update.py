import Load
import Save
import datetime as dt
import Previous_Match
import MMR
import SR
import MatchResult
import Standings

def phase_1():
    Players = Load.load()
    Previous = Previous_Match.previous_match_stats()
    Save.backup_save(Players)
    PMP = Previous[0] # Previous Match Players
    PMT = Previous[1] # Previous Match Teams
    DATE = Previous[2] # Previous Match Date
    RESULTS = Previous[3] # Previous Match Results
    SEASON = "season " + str(Players["season"])
    MVP_G = {"player":"", "count": 0}
    MVP_A = {"player":"", "count": 0}
    match_type = Previous[4]



    if Players["update"] != DATE:  # Safety Check, da slucajno ne more updatat 2x isto
        Players["update"] = DATE

        ## Determine MVPs
        for player in PMP:
            goals = PMP[player]["goal"]
            assists = PMP[player]["ass"]
            if goals > MVP_G["count"]:
                MVP_G["count"] = goals
                MVP_G["player"] = player
            if goals == MVP_G["count"]:
                MVP_G["player"] = ""
            if goals > MVP_A["count"]:
                MVP_A["count"] = assists
                MVP_A["player"] = player
            if goals == MVP_A["count"]:
                MVP_A["player"] = ""


        for player in PMP:

            # Add goals, assists, attendance and auto goals
            Players[player]["goals"] += PMP[player]["goal"]
            Players[player]["assists"] += PMP[player]["ass"]
            Players[player]["auto goals"] += PMP[player]["ag"]
            Players[player][SEASON]["goals"] += PMP[player]["goal"]
            Players[player][SEASON]["assists"] += PMP[player]["ass"]
            Players[player][SEASON]["auto goals"] += PMP[player]["ag"]
            Players[player]["attendance"] += 1
            Players[player][SEASON]["attendance"] += 1

            # Add number of wins, ties and losses
            for team in PMT:
                if player in PMT[team]:
                    Players[player]["wins"] += RESULTS[team]["win"]
                    Players[player][SEASON]["wins"] += RESULTS[team]["win"]
                    Players[player]["losses"] += RESULTS[team]["loss"]
                    Players[player][SEASON]["losses"] += RESULTS[team]["loss"]
                    Players[player]["ties"] += RESULTS[team]["tie"]
                    Players[player][SEASON]["ties"] += RESULTS[team]["tie"]

            # Calculate matches played
            if match_type == "Match":
                Players[player]["matches played"] += 1
                Players[player][SEASON]["matches played"] += 1 
            if match_type == "Tournament":
                if len(RESULTS["separate"]) == 3:
                    Players[player]["matches played"] += 2
                    Players[player][SEASON]["matches played"] += 2
                if len(RESULTS["separate"]) == 6:
                    Players[player]["matches played"] += 3
                    Players[player][SEASON]["matches played"] += 3

            # Calculate MMR
            # -> Calculate averages
            Players[player]["goal average"] = Players[player]["goals"] / max(Players[player]["matches played"], 1)
            Players[player][SEASON]["goal average"] = Players[player][SEASON]["goals"] / max(Players[player][SEASON]["matches played"], 1)
            Players[player]["assist average"] = Players[player]["assists"] / max(Players[player]["matches played"], 1)
            Players[player][SEASON]["assist average"] = Players[player][SEASON]["assists"] / max(Players[player][SEASON]["matches played"], 1)
            Players[player]["auto goal average"] = Players[player]["auto goals"] / max(Players[player]["matches played"], 1)
            Players[player][SEASON]["auto goal average"] = Players[player][SEASON]["auto goals"] / max(Players[player][SEASON]["matches played"], 1)
            Players[player]["winrate"] = Players[player]["wins"] / max(Players[player]["matches played"], 1)
            Players[player][SEASON]["winrate"] = Players[player][SEASON]["wins"] / max(Players[player][SEASON]["matches played"], 1)
            # -> Calclate MMR
            Players[player]["MMR"] = MMR.MMR_calculator(Players[player]["winrate"], Players[player]["goal average"], Players[player]["assist average"], Players[player]["auto goal average"])

            ## Calculate SR
            # -> Winstreak
            winstreak = 0
            for team in PMT:
                if player in PMT[team]:
                    for match in RESULTS["separate"]:
                        if team in match:
                            R = MatchResult.match_analysis(team, match, RESULTS["separate"][match])
                            if R == 1:
                                winstreak += 1
                            if R == 0 or R == -1:
                                winstreak = 0
            Players[player]["winstreak"] += winstreak
            # --> Check for MVP
            if player == MVP_G["player"]:
                mvp_g = True
                Players[player][SEASON]["MVP goal"] += 1
            else:
                mvp_g = False
            if player == MVP_A["player"]:
                mvp_a = True
                Players[player][SEASON]["MVP assist"] += 1
            else:
                mvp_a = False
            # -> Base SR (without wins and weight)
            Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], 0, PMP[player]["goal"], PMP[player]["ass"], PMP[player]["ag"], Players[player]["winstreak"], mvp_g, mvp_a)

            # -> SR from wins / losses (weighted)
            for team in PMT:
                if player in PMT[team]:
                    for match in RESULTS["separate"]:
                        if team in match:
                            if team == match[0]:
                                opp = match[2]
                            if team == match[2]:
                                opp = match[0]

                            R = MatchResult.match_analysis(team, match, RESULTS["separate"][match])
                            Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], R, 0, 0, 0, 0, False, False, PMT[team], PMT[opp])

                            for teammate in PMT[team]:
                                if player == teammate:
                                    continue 
                                Players[player]["teammates plays"][teammate] += 1
                                Players[player][SEASON]["teammates plays"][teammate] += 1
                                if R == 1:
                                    Players[player]["teammates wins"][teammate] += 1
                                    Players[player][SEASON]["teammates wins"][teammate] += 1
                                if R == 0:
                                    Players[player]["teammates ties"][teammate] += 1
                                    Players[player][SEASON]["teammates ties"][teammate] += 1
                                if R == -1:
                                    Players[player]["teammates losses"][teammate] += 1
                                    Players[player][SEASON]["teammates losses"][teammate] += 1
            # Tournament Winner?
            if match_type == "Tournament":
                winner = Previous_Match.tournament_winner()
                if winner != "":
                    if player in PMT[winner]:
                        Players[player]["tournaments won"] += 1
                        Players[player][SEASON]["tournaments won"] += 1

            # Reset titles:
            Players[player][SEASON]["title"] = []       

            # Highest SR?
            # -> Seasonal
            if Players[player][SEASON]["SR"] > Players[player][SEASON]["highest SR"]:
                Players[player][SEASON]["highest SR"] = Players[player][SEASON]["SR"]
                Players[player][SEASON]["title"] += ["New Season Best"]
            # -> Overall
            if Players[player][SEASON]["SR"] > Players[player]["highest SR"]:
                Players[player]["highest SR"] = Players[player][SEASON]["SR"]
                Players[player][SEASON]["title"] += ["New Career Best (SR)"]

            # Update last match played
            Players[player]["last match played"] = DATE

            # Highest MMR?
            if Players[player]["MMR"] > Players[player]["highest MMR"]:
                Players[player]["highest MMR"] = Players[player]["MMR"]
                Players[player][SEASON]["title"] += ["New Career Best (MMR)"]


            # Determine rank based on player's SR
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

def phase_2():
    Players = Load.load()
    Previous = Previous_Match.previous_match_stats()
    PMP = Previous[0] # Previous Match Players
    PMT = Previous[1] # Previous Match Teams
    DATE = Previous[2] # Previous Match Date
    RESULTS = Previous[3] # Previous Match Results
    SEASON = "season " + str(Players["season"])
    MVP_G = {"player":"", "count": 0}
    MVP_A = {"player":"", "count": 0}
    match_type = Previous[4]

    Overall = {
    "GSO": Standings.overall_standings("goals"),                                # Goal Standings Overall
    "ASO": Standings.overall_standings("assists"),                              # Assists Standings Overall
    "AGO": Standings.overall_standings("auto goals"),                           # Auto goal Standings Overall
    "WRSO": Standings.overall_standings("winrate"),                             # Winrate Standings Overall
    "WSO": Standings.overall_standings("wins"),                                 # Wins Standings Overall
    "LSO": Standings.overall_standings("losses"),                               # Losses Standings Overall
    "TSO": Standings.overall_standings("ties"),                                 # Ties Standings Overall
    "TWO": Standings.overall_standings("tournaments won"),                      # Tournaments Won Standings Overall
    "MMRSO": Standings.overall_standings("MMR"),                                # MMR Standings Overall
    "ATSO": Standings.overall_standings("attendance"),                          # Attendance Standings Overall
    "MPSO": Standings.overall_standings("matches played"),                      # Matches Played Standings Overall
    "GASO": Standings.overall_standings("goal average"),                        # Goal Average Standings Overall
    "AASO": Standings.overall_standings("assist average"),                     # Assist Average Standings Overall
    "AGASO": Standings.overall_standings("auto goal average"),                  # Auto Goal Average Standings Overall
    "GSS": Standings.seasonal_standings("goals", SEASON),                       # Goal Standings Overall
    "ASS": Standings.seasonal_standings("assists", SEASON),                     # Assists Standings Overall
    "AGS": Standings.seasonal_standings("auto goals", SEASON),                  # Auto goal Standings Overall
    "WRSS": Standings.seasonal_standings("winrate", SEASON),                    # Winrate Standings Overall
    "WSS": Standings.seasonal_standings("wins", SEASON),                        # Wins Standings Overall
    "LSS": Standings.seasonal_standings("losses", SEASON),                      # Losses Standings Overall
    "TSS": Standings.seasonal_standings("ties", SEASON),                        # Ties Standings Overall
    "TWS": Standings.seasonal_standings("tournaments won", SEASON),             # Tournaments Won Standings Overall
    "SRSS": Standings.seasonal_standings("SR", SEASON),                         # SR Standings Overall
    "ATSS": Standings.seasonal_standings("attendance", SEASON),                 # Attendance Standings Overall
    "MPSS": Standings.seasonal_standings("matches played", SEASON),             # Matches Played Standings Overall
    "GASS": Standings.seasonal_standings("goal average", SEASON),               # Goal Average Standings Overall
    "AASS": Standings.seasonal_standings("assist average", SEASON),             # Assist Average Standings Overall
    "AGASS": Standings.seasonal_standings("auto goal average", SEASON),         # Auto Goal Average Standings Overall
    "MVPGSS": Standings.seasonal_standings("MVP goal", SEASON),                 # MVP Goals Standings Overall
    "MVPASS": Standings.seasonal_standings("MVP assist", SEASON),               # MVP Assists Standings Overall
        }

    
        ### Not yet done!
     


    return Overall