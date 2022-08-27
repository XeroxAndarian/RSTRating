import Load


Bank = Load.load()

def find_by_name(name):
    '''Returns ID of a player with name'''
    pl_names = []
    data = list(Bank.keys())
    for player in list(Bank.values()):
        if type(player) is dict:
            if player["name"] == name:
                pl_names.append(player["id"])
    
    return pl_names

def find_by_surname(sur):
    '''Returns ID of a player with surname'''
    pl_names = []
    data = list(Bank.keys())
    for player in list(Bank.values()):
        if type(player) is dict:
            if player["surname"] == sur:
                pl_names.append(player["id"])
    
    return pl_names

def find_by_nickname(nick):
    '''Returns ID of a player with nickname'''
    pl_names = []
    data = list(Bank.keys())
    for player in list(Bank.values()):
        if type(player) is dict:
            if nick in player["nickname"]:
                pl_names.append(player["id"])
    
    return pl_names


def find_by_full_name(name, sur):
    names = find_by_name(name)
    surnames = find_by_surname(sur)
    list = []
    for id in names:
        if id in surnames:
            list.append(id)
    
    return list

def get_id_card(id):
    return Bank.get(id)

def find(name):
    names = find_by_name(name)
    surnames = find_by_surname(name)
    nicks = find_by_nickname(name)
    return remove_duplicates(union(names, union(surnames, nicks)))
    

def intersection(lst1, lst2):
    lst = [value for value in lst1 if value in lst2]
    return lst

def union(lst1, lst2):
    lst = lst1
    for i in lst2:
        lst.append(i)
    return lst

def remove_duplicates(list):
    lst = []
    for i in list:
        if i not in lst:
            lst.append(i)
    return lst

def find_by(by, value):
    match = []
    for player in Bank:
        if player == "update" or player == "season":
            continue
        if Bank[player][by] == value:
            match.append(player)

    return match

def find_by_season(season, by, value):
    match = []
    for player in Bank:
        if player == "update" or player == "season":
            continue
        if Bank[player][season][by] == value:
            match.append(player)

    return match