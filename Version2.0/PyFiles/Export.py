import Load
import Find
import os.path
import Previous_Match

Players = Load.load()
Previous = Previous_Match.previous_match_stats()
Date = Previous[2]
Season = "season " + str(Players["season"])
File = "Version2.0\Data\Exports\CSVExport" + Date + ".csv"

Ignore = ["nickname", "teammates plays", "teammates wins", "teammates losses", "teammates ties", "teammates winrate", "teammates lossrate"]
Worst_Best = ["worst teammate", "best teammate"]

def generate_latest_csv(player, dic=Players):
    player_report = ""
    for stat in dic[player]:
        if stat in Ignore:
            continue
        if stat == "season 0":
            break
        if type(dic[player][stat]) == str:
            player_report += dic[player][stat] + ";"
        if type(dic[player][stat]) in [int, float]:
            player_report += str(dic[player][stat]) + ";"
        if type(dic[player][stat]) == list:
            if len(dic[player][stat]) != 0:
                string = ""
                if stat in Worst_Best:
                    for value in dic[player][stat]:
                        string += dic[value]["name"] + ","
                    player_report += string[:-1] + ";"
                else:
                    for value in dic[player][stat]:
                        string += str(value) + ","
                    player_report += string[:-1] + ";"
            else:  
                player_report += ";"
    for stat in dic[player][Season]:
        if stat in Ignore:
            continue
        if type(dic[player][Season][stat]) == str:
            player_report += dic[player][Season][stat] + ";"
        if type(dic[player][Season][stat]) in [int, float]:
            player_report += str(dic[player][Season][stat]) + ";"
        if type(dic[player][Season][stat]) == list:
            if len(dic[player][Season][stat]) != 0:
                string = ""
                if stat in Worst_Best:
                    for value in dic[player][Season][stat]:
                        string += dic[value]["name"] + ","
                    player_report += string[:-1] + ";"
                else:
                    for value in dic[player][Season][stat]:
                        string += str(value) + ","
                    player_report += string[:-1] + ";"
            else:
                player_report += ";"

    return player_report.replace(".", ",")




def export_csv(dic=Players):
    
    Header = False
    header = ""
    Content = ""
    for player in dic:
        if type(dic[player]) == dict:
            player_report = ""
            for stat in dic[player]:
                if stat in Ignore:
                    continue
                if stat == "season 0":
                    break
                if not Header:
                    header += stat + ";"
                if type(dic[player][stat]) == str:
                    player_report += dic[player][stat] + ";"
                if type(dic[player][stat]) in [int, float]:
                    player_report += str(dic[player][stat]) + ";"
                if type(dic[player][stat]) == list:
                    if len(dic[player][stat]) != 0:
                        string = ""
                        if stat in Worst_Best:
                            for value in dic[player][stat]:
                                string += dic[value]["name"] + ","
                            player_report += string[:-1] + ";"
                        else:
                            for value in dic[player][stat]:
                                string += str(value) + ","
                            player_report += string[:-1] + ";"
                    else:  
                        player_report += ";"
            for stat in dic[player][Season]:
                if stat in Ignore:
                    continue
                if not Header:
                    header += stat + ";"
                if type(dic[player][Season][stat]) == str:
                    player_report += dic[player][Season][stat] + ";"
                if type(dic[player][Season][stat]) in [int, float]:
                    player_report += str(dic[player][Season][stat]) + ";"
                if type(dic[player][Season][stat]) == list:
                    if len(dic[player][Season][stat]) != 0:
                        string = ""
                        if stat in Worst_Best:
                            for value in dic[player][Season][stat]:
                                string += dic[value]["name"] + ","
                            player_report += string[:-1] + ";"
                        else:
                            for value in dic[player][Season][stat]:
                                string += str(value) + ","
                            player_report += string[:-1] + ";"
                    else:
                        player_report += ";"
            if not Header:
                Content += header + "\n"
            Header = True
            Content += player_report + "\n"

    with open(File, "w", encoding = "utf-8") as f:
        f.write(Content.replace(".", ","))
    return Content



def update_player_stats(player, dic=Players):
    file = "Version2.0\Data\Player Weekly Reports\Weekly_id_" + player + ".csv"
    exsists = os.path.exists(file)
    if exsists:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read().split("\n")
            line = content[-1].split(";")
            if line[0] == Date:
                return None
    if not exsists:
        with open(file, "w", encoding="utf-8") as f:
            header = ""
            for stat in dic[player]:
                if stat == "season 0":
                    break
                if stat not in Ignore:
                    header += stat + ";"
            for stat in dic[player][Season]:
                if stat not in Ignore:
                    header += stat + ";"
            f.write("date," + header)
            f.close
    if type(dic[player]) != dict:
        return None
    new_match = generate_latest_csv(player)
    new_line = Date + ";"
    new_line += new_match
        
    with open(file, "a", encoding="utf-8") as f:
        f.write("\n")
        f.write(new_line)
        f.close
    return None

def update_player_stats_all(dic):
    for player in dic:
        if type(dic[player]) == dict:
            update_player_stats(player)

export_csv()
update_player_stats_all()