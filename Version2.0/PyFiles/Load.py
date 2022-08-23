import json


def load():
    '''Loads the current Data.json'''
    file_name = "Version2.0\Data\Data Bank\Data.json"
    with open(file_name, "r") as data:
        Stats = json.load(data)

    return Stats

        
   
