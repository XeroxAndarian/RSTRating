import json


def load():
    '''Loads the current Data.json'''
    file_name = "Version2.0\Data\Data Bank\Data.json"
    with open(file_name, "r", encoding="utf-8") as data:
        Stats = json.load(data)

    return Stats

def load(file="Data"):
    '''Loads the current Data.json'''
    file_name = "Version2.0\Data\Data Bank\\" + file + ".json"
    with open(file_name, "r", encoding="utf-8") as data:
        Stats = json.load(data)

    return Stats
   
