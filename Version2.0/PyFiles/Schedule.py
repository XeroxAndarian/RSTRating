

def schedule(teams, time, pause):
    T = lambda x,y: (x-5*y)//6
    if teams <=2: 
        return time
    if teams >= 3:
        return T(time, pause)
        
print("This is match / halftime calculator. Please insert:")
TEAMS = int(input("Number of teams: "))
TIME = int(input("Avalible time [min]: "))
PAUSE = int(input("Length of a break between two matches / halfitmes: "))
if TEAMS == 3:
    print("Duration of a halftime [min]: " + str(schedule(TEAMS, TIME, PAUSE)) + ", with " + str(PAUSE) + " minute breaks")
if TEAMS == 4:
    print("Duration of a match: [min]" + str(schedule(TEAMS, TIME, PAUSE)) + ", with " + str(PAUSE) + " minute breaks")