import Load
import Save
import datetime as dt
import Previous_Match
import MMR
import SR
import MatchResult
import Standings
import Export
import time



Players = Load.load()
Players_old = Load.load().copy()
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
FEE = 1 # Standard attendance fee == 1 €


def phase_1():
    '''Update personal info such as goal count, winrate, MMR ... Also it counts attendences, mathes played and such.'''
    

    ## Determine MVPs
    for player in PMP:
        goals = PMP[player]["goal"]
        assists = PMP[player]["ass"]
        if goals == MVP_G["count"]:
            MVP_G["player"] = ""
        if goals > MVP_G["count"]:
            MVP_G["count"] = goals
            MVP_G["player"] = player
        if assists == MVP_A["count"]:
            MVP_A["player"] = ""
        if assists > MVP_A["count"]:
            MVP_A["count"] = assists
            MVP_A["player"] = player

        if Players[player][SEASON]["attendance"] == 0:
            Players[player][SEASON]["SR"] = 999
            


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

        # Add one time fee to how much money player owns
        Players[player]["debt"] += FEE                
        Players[player]["debt"] -= PMP[player]["money"]     # Amount player contributed this week

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
        # -> Winstreak / losing streak
        winstreak = 0
        for team in PMT:
            if player in PMT[team]:
                for match in RESULTS["separate"]:
                    if team in match:
                        R = MatchResult.match_analysis(team, match, RESULTS["separate"][match])
                        if R == 1:
                            winstreak += 1
                        if R == 0 or R == -1:
                           Players[player]["winstreak"] = 0
        Players[player]["winstreak"] += winstreak
        losing_streak = 0
        for team in PMT:
            if player in PMT[team]:
                for match in RESULTS["separate"]:
                    if team in match:
                        R = MatchResult.match_analysis(team, match, RESULTS["separate"][match])
                        if R == -1:
                            losing_streak += 1
                        if R == 0 or R == 1:
                            Players[player]["losing streak"] = 0
        Players[player]["losing streak"] += losing_streak
        
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
                        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], R, 0, 0, 0, 0, False, False, PMT[team], PMT[opp], Players)
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

        # -> Base SR (without wins and weight)
        Players[player][SEASON]["SR"] = SR.SR_calculator(Players[player][SEASON]["SR"], 0, PMP[player]["goal"], PMP[player]["ass"], PMP[player]["ag"], Players[player]["winstreak"], mvp_g, mvp_a, [], [], Players)

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

        # Undefeatable; winrate == 100%
        if Players[player]["winrate"] == 1:
            Players[player][SEASON]["title"] += ["Undefeatable"]
        
        # Worst Enemy; highest winrate
        if Players[player]["rank winrate"] == 1:
            Players[player][SEASON]["title"] += ["Worst Enemy"]
        
        # On a Roll!, On Fire!, Unstoppable!; Winstreak == 3 | 4 | 5+
        ws = Players[player]["winstreak"]
        title = ""
        if ws == 3:
            title = "On a Roll!"
        if ws == 4:
            title = "On Fire!"
        if ws >= 5:
            title = "Unstoppable!"
        Players[player][SEASON]["title"] += [title]

        # Helping hand, Ace; Most Assists | Goals
        if Players[player][SEASON]["rank goals"] == 1:
            Players[player][SEASON]["title"] += ["Ace"]
        if Players[player][SEASON]["rank assists"] == 1:
            Players[player][SEASON]["title"] += ["Helping Hand"]
        
        # Guardian Angel, Nightamre; Most Support | Goals MVP
        if Players[player][SEASON]["rank MVP goal"] == 1:
            Players[player][SEASON]["title"] += ["Nightmare"]
        if Players[player][SEASON]["rank MVP assist"] == 1:
            Players[player][SEASON]["title"] += ["Guardian Angel"] 

        # Support, Striker; Top 3 in goals, top 3 in assists average
        if Players[player][SEASON]["rank goal average"] >= 3:
            Players[player][SEASON]["title"] += ["Striker"]
        if Players[player][SEASON]["rank assist average"] >= 3:
            Players[player][SEASON]["title"] += ["Support"]
        
        # Perfectly Balanced, as all things should be
        if Players[player][SEASON]["goals"] == Players[player][SEASON]["assists"]:
            if Players[player][SEASON]["wins"] == Players[player][SEASON]["losses"]:
                if Players[player][SEASON]["wins"] == Players[player][SEASON]["ties"]:
                    Players[player][SEASON]["title"] += ["Perfectly Balanced (as all things should be)"]
            
        # Champion; most turnaments won
        if Players[player][SEASON]["rank tournaments won"] == 1:
            Players[player][SEASON]["title"] += ["Champion"]
        
        # Rare Element!; Only player in a rank
        Rare_element = True
        for other_player in Players:
            if type(Players[other_player]) != dict:
                continue
            if player == other_player:
                continue
            if Players[player][SEASON]["rank"] == Players[other_player][SEASON]["rank"]:
                Rare_element = False
        if Rare_element:
            Players[player][SEASON]["title"] += ["Rare Element!"]

        # Hat Trick Baby!; scored hat trick last match
        if PMP[player]["goal"] > 2:
            Players[player][SEASON]["title"] += ["Hat Trick Baby!"]

        # None Shall Win!; most ties
        if Players[player][SEASON]["rank ties"] == 1:
            Players[player][SEASON]["title"] += ["None Shall Win!"]

        # Alchemist
        if Players[player][SEASON]["rank"] != Players_old[player][SEASON]["rank"]:
            Players[player][SEASON]["title"] += ["Alchemist!"]
        
        # Traitor:
        if Players[player][SEASON]["rank auto goals"] == 1:
            Players[player][SEASON]["title"] += ["Traitor!"]
        




def phase_8():
    '''Calculate players' standigs in each category.'''
    N = len(Players) - 2

    Overall = {
    "goals": Standings.overall_standings("goals", Players),                                # Goal Standings Overall
    "assists": Standings.overall_standings("assists", Players),                              # Assists Standings Overall
    "auto goals": Standings.overall_standings("auto goals", Players),                           # Auto goal Standings Overall
    "winrate": Standings.overall_standings("winrate", Players),                             # Winrate Standings Overall
    "wins": Standings.overall_standings("wins", Players),                                 # Wins Standings Overall
    "losses": Standings.overall_standings("losses", Players),                               # Losses Standings Overall
    "ties": Standings.overall_standings("ties", Players),                                 # Ties Standings Overall
    "tournaments won": Standings.overall_standings("tournaments won", Players),                      # Tournaments Won Standings Overall
    "MMR": Standings.overall_standings("MMR", Players),                                # MMR Standings Overall
    "attendance": Standings.overall_standings("attendance", Players),                          # Attendance Standings Overall
    "matches played": Standings.overall_standings("matches played", Players),                      # Matches Played Standings Overall
    "goal average": Standings.overall_standings("goal average", Players),                        # Goal Average Standings Overall
    "assist average": Standings.overall_standings("assist average", Players),                     # Assist Average Standings Overall
    "auto goal average": Standings.overall_standings("auto goal average", Players),                  # Auto Goal Average Standings Overall
        }
    Seasonal = {    
    "goals": Standings.seasonal_standings("goals", SEASON, Players),                       # Goal Standings Overall
    "assists": Standings.seasonal_standings("assists", SEASON, Players),                     # Assists Standings Overall
    "auto goals": Standings.seasonal_standings("auto goals", SEASON, Players),                  # Auto goal Standings Overall
    "winrate": Standings.seasonal_standings("winrate", SEASON, Players),                    # Winrate Standings Overall
    "wins": Standings.seasonal_standings("wins", SEASON, Players),                        # Wins Standings Overall
    "losses": Standings.seasonal_standings("losses", SEASON, Players),                      # Losses Standings Overall
    "ties": Standings.seasonal_standings("ties", SEASON, Players),                        # Ties Standings Overall
    "tournaments won": Standings.seasonal_standings("tournaments won", SEASON, Players),             # Tournaments Won Standings Overall
    "SR": Standings.seasonal_standings("SR", SEASON, Players),                         # SR Standings Overall
    "attendance": Standings.seasonal_standings("attendance", SEASON, Players),                 # Attendance Standings Overall
    "matches played": Standings.seasonal_standings("matches played", SEASON, Players),             # Matches Played Standings Overall
    "goal average": Standings.seasonal_standings("goal average", SEASON, Players),               # Goal Average Standings Overall
    "assist average": Standings.seasonal_standings("assist average", SEASON, Players),             # Assist Average Standings Overall
    "auto goal average": Standings.seasonal_standings("auto goal average", SEASON, Players),         # Auto Goal Average Standings Overall
    "MVP goal": Standings.seasonal_standings("MVP goal", SEASON, Players),                 # MVP Goals Standings Overall
    "MVP assist": Standings.seasonal_standings("MVP assist", SEASON, Players)               # MVP Assists Standings Overall
    }
    
    for std in Overall:
        rank = "rank " + std
        for i in range(1, N):
            for player in Overall[std][str(i)]:
                Players[player][rank] = i
    
    
    for std in Seasonal:
        rank = "rank " + std
        for i in range(1, N):
            for player in Seasonal[std][str(i)]:
                Players[player][SEASON][rank] = i
    
    for player in Players:
        if type(Players[player]) != dict:
            continue
        if Players[player][SEASON]["rank SR"] == 1:
            Players[player][SEASON]["weeks on top"] += 1
            Players[player][SEASON]["consecutive weeks on top"] += 1
        else:
            Players[player][SEASON]["consecutive weeks on top"] = 0

        # King of the Hill
        if Players[player][SEASON]["consecutive weeks on top"] > 1:
            x = Players[player][SEASON]["consecutive weeks on top"] - 1
            asdf = "King of the hill: " + str(x)
            Players[player][SEASON]["title"] += [asdf]
    
    WOT = {"weeks on top": Standings.seasonal_standings("weeks on top", SEASON, Players)}
    rank = "rank weeks on top"
    for i in range(1, N):
        for player in WOT["weeks on top"][str(i)]:
            Players[player][SEASON][rank] = i

    

    
def phase_2():
    '''Teammates and best/worst teammates'''

    # Set Winrates and lossrates
    for player in Players:
        if player == "update" or player == "season":
            continue
        for teammate in Players[player]["teammates winrate"]:
            if teammate == player:
                continue
            Players[player]["teammates winrate"][teammate] = Players[player]["teammates wins"][teammate] / max(Players[player]["teammates plays"][teammate], 1)
            Players[player]["teammates lossrate"][teammate] = Players[player]["teammates losses"][teammate] / max(Players[player]["teammates plays"][teammate], 1)
            Players[player][SEASON]["teammates winrate"][teammate] = Players[player][SEASON]["teammates wins"][teammate] / max(Players[player][SEASON]["teammates plays"][teammate], 1)
            Players[player][SEASON]["teammates lossrate"][teammate] = Players[player][SEASON]["teammates losses"][teammate] / max(Players[player][SEASON]["teammates plays"][teammate], 1)

    # Determine best / worst teammate
        player_winrates = sorted(list(Players[player]["teammates winrate"].values()), reverse=True) 
        player_lossrates = sorted(list(Players[player]["teammates lossrate"].values()), reverse=True) 
        player_winrates_season = sorted(list(Players[player][SEASON]["teammates winrate"].values()), reverse=True) 
        player_lossrates_season = sorted(list(Players[player][SEASON]["teammates lossrate"].values()), reverse=True) 
        

        def find(by, value, season=None):
            if season == None:
                Data = []
                for teammate in Players[player]["teammates " + by]:
                    if Players[player]["teammates " + by][teammate] == value:
                        Data += [teammate]
                return Data
            else:
                Data = []
                for teammate in Players[player][SEASON]["teammates " + by]:
                    if Players[player][SEASON]["teammates " + by][teammate] == value:
                        Data += [teammate]
                return Data
        
        Players[player]["best teammate"] = find("winrate", player_winrates[0]) 
        Players[player]["worst teammate"] = find("lossrate", player_lossrates[0]) 
        Players[player][SEASON]["best teammate"] = find("winrate", player_winrates_season[0]) 
        Players[player][SEASON]["worst teammate"] = find("lossrate", player_lossrates_season[0])

        A = Players[player]["worst teammate"].copy()
        for teammate in A:
            if teammate == player:
                continue
            if Players[player]["teammates losses"][teammate] == 0:
                Players[player]["worst teammate"].remove(teammate)
                Players[player][SEASON]["worst teammate"].remove(teammate)


def phase_10():
    '''Update and export in .csv format. Players seperately and general statistics.'''
    Export.export_csv(Players)
    Export.update_player_stats_all(Players)

def phase_9():
    '''Ladder Advancements Calculator'''
    Old = {}
    New = {}
    Climb = {}
    for player in Players:
        if type(Players[player]) != dict:
            continue
        New[player] = Players[player][SEASON]["rank SR"]
    for player in Players_old:
        if type(Players_old[player]) != dict:
            continue
        Old[player] = Players_old[player][SEASON]["rank SR"]
        if Players_old[player][SEASON]["attendance"] == 0:
            Old[player] = 0

    for player in Players:
        if type(Players[player]) != dict:
            continue
        if Players[player][SEASON]["SR"] == 0:
            Climb[player] = "U"
        elif Old[player] == 0:
            Climb[player] = "N"
        else:
            Climb[player] = Old[player] - New[player]

    
    for player in Climb:
        Players[player][SEASON]["climb"] = Climb[player]


        # To the Moon!; player who climbed the most
        lst = list(Climb.values())
        keys = list(Climb.keys())
        for e in lst:
            if type(e) != int:
                lst.remove(e)
        if type(lst[-1]) != int:
            lst.remove(lst[-1])
        
        m = max(lst)
        pos = lst.index(m)
        P = keys[pos]
        if player == P:
            Players[player][SEASON]["title"] += ["To the Moon!"]
    
    Save.save(Players, True, DATE)

# for i in range(0, 5):
#     if i == 0:
#         print("Phase 1:")
#         phase_1()
#     if i == 1:
#         print("Phase 2:")
#         phase_2()
#     if i == 2:
#         print("Phase 3:")
#         phase_3()
#     if i == 3:
#         print("Phase 4:")
#         phase_5()
#     if i == 4:
#         print("Phase 5:")
#         phase_4()
# 
#     for x in range (0,7):
#         if x < 5:  
#             y = "Updating (" + str(i + 1) + "/5)" + "." * x
#             print (y, end="\r")
#             time.sleep(0.5)
#         elif x == 5:  
#             y = "Updating (" + str(i + 1) + "/5)" + "." * x
#             print (y)
#             time.sleep(0.5)      
#         else:
#             y = "Phase " + str(i + 1) + " Done."
#             print (y)
#             time.sleep(0.75)
# print("Update Complete!")


if Players["update"] != DATE:  # Safety Check, da slucajno ne more updatat 2x isto
        Players["update"] = DATE

        phase_1()
        phase_2()
        phase_8()
        phase_9()
phase_10()


