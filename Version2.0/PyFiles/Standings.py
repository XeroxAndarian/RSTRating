import Find
import Load


def overall_standings(of, dict):
    Standings = {}
    N = len(dict) - 2
    for i in range(N):
        Standings[str(i + 1)] = []

    Data = []

    for player in dict:
        if player == "update" or player == "season":
            continue
        Data.append(dict[player][of])
    
    Data_sort = sorted(Data, reverse=True)
    
    def find_to_map(n):
        return Find.find_by_2(of, n, dict)

    stnd = Find.remove_duplicates(list(map(find_to_map, Data_sort)))
    
    for j in range(len(stnd)):
        Standings[str(j + 1)] = stnd[j]
     

    return Standings

def seasonal_standings(of, season, dict):
    SEASON = "season " + str(dict["season"]) 
    Standings = {}
    N = len(dict) - 2
    for i in range(N):
        Standings[str(i + 1)] = []

    Data = []

    for player in dict:
        if player == "update" or player == "season":
            continue
        Data.append(dict[player][season][of])
    
    Data_sort = sorted(Data, reverse=True)
    
    def find_to_map(n):
        return Find.find_by_season_2(season, of, n, dict)

    stnd = list(map(find_to_map, Data_sort))
    
    stsd = Find.remove_duplicates(stnd)

    for j in range(len(stsd)):
        Standings[str(j + 1)] = stsd[j]
     
     
    return Standings

def seasonal_standings_file(of, season, file):
    Bank = Load.load(file)
    Standings = {}
    N = len(Bank) - 2
    for i in range(N):
        Standings[str(i + 1)] = []

    Data = []

    for player in Bank:
        if player == "update" or player == "season":
            continue
        Data.append(Bank[player][season][of])
    
    Data_sort = sorted(Data, reverse=True)
    
    def find_to_map(n):
        return Find.find_by_season(season, of, n)

    stnd = list(map(find_to_map, Data_sort))
    
    stsd = Find.remove_duplicates(stnd)

    for i in range(len(stsd)):
        Standings[str(i + 1)] = stsd[i]
     
     
    return Standings
# print(overall_standings("goals"))
# print(seasonal_standings("goals", "season 0"))