import Load
import Find
import os.path
import Previous_Match

Players = Load.load()
Previous = Previous_Match.previous_match_stats()
Date = Previous[2]
Season = "season " + str(Players["season"])
File = "Version2.0\Data\DIC\Players" + Date + ".txt"

Ignore = ["nickname", "teammates plays", "teammates wins", "teammates losses", "teammates ties", "teammates winrate", "teammates lossrate"]
Worst_Best = ["worst teammate", "best teammate"]

def DIC(dic=Players):

    Content = "DIC = { "

    Names = [Players[str(i)]["name"] for i in range(len(Players) - 2)]
    Surnames = [Players[str(i)]["surname"] for i in range(len(Players) - 2)]
    mmrs = [Players[str(i)]["MMR"] for i in range(len(Players) - 2)]
    ids = [Players[str(i)]["id"] for i in range(len(Players) - 2)]

    for id in ids:
        Content += "\n #   "
        if Players[str(id)]["surname"] != "":
            Content += '"'
            Content += Players[str(id)]["surname"]
            Content += " "
            Content += Players[str(id)]["name"][0]
            Content += "."
            Content += '"'
        else: 
            Content += '"'
            Content += Players[str(id)]["name"]
            Content += '"'
        Content += " : "
        Content += str(round(Players[str(id)]["MMR"], 1))
        Content += ","

    Content = Content[:-1]
    Content += "\n }"

    with open(File, "w", encoding = "utf-8") as f:
        f.write(Content)
    return None



Names = [Players[str(i)]["name"] for i in range(len(Players) - 2)]
Surnames = [Players[str(i)]["surname"] for i in range(len(Players) - 2)]
mmrs = [Players[str(i)]["MMR"] for i in range(len(Players) - 2)]
ids = [Players[str(i)]["id"] for i in range(len(Players) - 2)]

