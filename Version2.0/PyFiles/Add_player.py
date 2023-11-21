import Load
import Save


Players = Load.load()
SEASON = "season " + str(Players["season"])



def check_if_exsists(name, surname):
    for player in Players:
        if (player == "update"):
            pass
        elif player == "season":
            pass
        else:
            S = False
            N = False
            if Players[player]["name"] == name:
                N = True
            if Players[player]["surname"] == surname:
                S = True
            if S & N:
                return True
    
    return False


def new_player(name="",surname="", nick=[]):

    if check_if_exsists(name, surname):
        return False
    else:

        i = 0
        while str(i) in Players:
            i += 1

        Players[str(i)] = {}
        Players[str(i)]["id"] = i
        Players[str(i)]["name"] = name
        Players[str(i)]["surname"] = surname
        Players[str(i)]["nickname"] = nick
        Players[str(i)]["attendance"] = 0
        Players[str(i)]["matches played"] = 0
        Players[str(i)]["goals"] = 0
        Players[str(i)]["assists"] = 0
        Players[str(i)]["auto goals"] = 0
        Players[str(i)]["winrate"] = 0
        Players[str(i)]["goal average"] = 0
        Players[str(i)]["assist average"] = 0
        Players[str(i)]["auto goal average"] = 0
        Players[str(i)]["wins"] = 0
        Players[str(i)]["losses"] = 0
        Players[str(i)]["ties"] = 0
        Players[str(i)]["MMR"] = 0
        Players[str(i)]["winstreak"] = 0
        Players[str(i)]["losing streak"] = 0
        Players[str(i)]["last match played"] = 0
        Players[str(i)]["teammates plays"] = {} 
        Players[str(i)]["teammates wins"] = {} 
        Players[str(i)]["teammates losses"] = {}
        Players[str(i)]["teammates ties"] = {}
        Players[str(i)]["teammates winrate"] = {}
        Players[str(i)]["teammates lossrate"] = {}
        Players[str(i)]["best teammate"] = []
        Players[str(i)]["worst teammate"] = []
        Players[str(i)]["tournaments won"] = 0
        Players[str(i)]["weeks on top"] = 0
        Players[str(i)]["highest SR"] = 0
        Players[str(i)]["highest MMR"] = 0
        Players[str(i)]["rank goals"] = 0
        Players[str(i)]["rank assists"] = 0
        Players[str(i)]["rank auto goals"] = 0
        Players[str(i)]["rank winrate"] = 0
        Players[str(i)]["rank wins"] = 0
        Players[str(i)]["rank losses"] = 0
        Players[str(i)]["rank ties"] = 0
        Players[str(i)]["rank MMR"] = 0
        Players[str(i)]["rank tournaments won"] = 0
        Players[str(i)]["rank attendance"] = 0
        Players[str(i)]["rank matches played"] = 0
        Players[str(i)]["rank goal average"] = 0
        Players[str(i)]["rank assist average"] = 0
        Players[str(i)]["rank auto goal average"] = 0
        Players[str(i)]["debt"] = 0
        
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
        Season_Template["teammates winrate"] = {}
        Season_Template["teammates lossrate"] = {}
        Season_Template["title"] = []
        Season_Template["highest SR"] = 0
        Season_Template["tournaments won"] = 0
        Season_Template["rank tournaments won"] = 0
        Season_Template["weeks on top"] = 0
        Season_Template["rank weeks on top"] = 0
        Season_Template["consecutive weeks on top"] = 0
        Season_Template["best teammate"] = []
        Season_Template["worst teammate"] = []
        
        
        
        Players[str(i)][SEASON] = Season_Template
        
        for player in list(Players.keys()):
            if player == "update" or player == "season":
                continue
            if str(i) != player:
                Players[str(i)]["teammates plays"][player] = 0
                Players[player]["teammates plays"][str(i)] = 0
                Players[str(i)]["teammates wins"][player] = 0
                Players[player]["teammates wins"][str(i)] = 0
                Players[str(i)]["teammates ties"][player] = 0
                Players[player]["teammates ties"][str(i)] = 0
                Players[str(i)]["teammates losses"][player] = 0
                Players[player]["teammates losses"][str(i)] = 0
                Players[str(i)]["teammates winrate"][player] = 0
                Players[player]["teammates winrate"][str(i)] = 0
                Players[str(i)]["teammates lossrate"][player] = 0
                Players[player]["teammates lossrate"][str(i)] = 0


                Players[str(i)][SEASON]["teammates plays"][player] = 0
                Players[player][SEASON]["teammates plays"][str(i)] = 0
                Players[str(i)][SEASON]["teammates wins"][player] = 0
                Players[player][SEASON]["teammates wins"][str(i)] = 0
                Players[str(i)][SEASON]["teammates ties"][player] = 0
                Players[player][SEASON]["teammates ties"][str(i)] = 0
                Players[str(i)][SEASON]["teammates losses"][player] = 0
                Players[player][SEASON]["teammates losses"][str(i)] = 0
                Players[str(i)][SEASON]["teammates winrate"][player] = 0
                Players[player][SEASON]["teammates winrate"][str(i)] = 0
                Players[str(i)][SEASON]["teammates lossrate"][player] = 0
                Players[player][SEASON]["teammates lossrate"][str(i)] = 0

        
        

        Save.save(Players, False)

        return True


def new_test():
    i = 0
    while str(i) in Players:
        i += 1
    
    new_player("test" + str(i), "TEST")

def add_tests(n):
    for i in range(n):
        new_test()
    
    
