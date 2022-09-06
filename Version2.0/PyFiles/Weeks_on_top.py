import Save
import Load
import Previous_Match



def weeks_on_top():
    '''Consecutive wins and weeks on top calculator'''
    Players_new = Load.load()
    Players_old = Load.load("Backup_Data")
    Previous = Previous_Match.previous_match_stats()
    SEASON = "season " + str(Players_new["season"])
    N = len(Players_old) - 2
    DATE = Previous[2] # Previous Match Date
    for player in Players_new:
        if type(Players_new[player]) != dict:
            continue
        if Players_new[player][SEASON]["rank SR"] != 1:
            Players_new[player][SEASON]["consecutive wins"] = 0
        if Players_new[player][SEASON]["rank SR"] == 1:
            Players_new[player][SEASON]["weeks on top"] = Players_old[player][SEASON]["weeks on top"] + 1
            Players_new[player][SEASON]["consecutive weeks on top"] = Players_old[player][SEASON]["consecutive weeks on top"] + 1
    
    Save.save(Players_new, False)

weeks_on_top()