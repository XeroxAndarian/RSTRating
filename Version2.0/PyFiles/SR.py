from ctypes.wintypes import HANDLE
from re import X
import numpy
import math
import Load

Players = Load.load()
SEASON = "season " + str(Players["season"])

# Values of each
G = lambda x: 10*x + max(0, 2*(x - 2))   # 10 SR for 1st and second, after that, 12 per goal
A = lambda x: 6*x + max(0, 2*(x - 2))    # 6 SR for 1st and second, after that, 8 per assist
AG = lambda x: -2*x                     # -2 SR per auto goal
W = lambda x: 20*x                      # 20 SR for victory, 0 for tie and -20 for defeat, but it's weighted
WS = lambda x: max(0, 5*(x - 1))                # 5 for each winstreak: 5, 10, 15, 20 ...
H = lambda x,y: 1 + 10 * (x/y - 1)      # Weight (Heavy)



def SR_calculator(current, R, g, a, ag, ws, mvpg, mvpa, own=[], opp=[]):
    # R = result from previous match [win = 1 | loss = -1 | tie = 0]
    # G/A/AG = goals/assists/autogoals from previoous match
    # WS = winstreak
    # MVPG/MVPA = [True | False] MVPs for Goals or Assists
    # own/opp = firendly team / opponent team


    if own == []:
        SR_opp_avg = 1
        SR_own_avg = 1
    else:    
        SR_own = 0
        SR_opp = 0
        for player in own:
            SR_own += Players[player][SEASON]["SR"]
        SR_own_avg = SR_own / len(own)
        for player in opp:
            SR_opp += Players[player][SEASON]["SR"]
        SR_opp_avg = SR_opp / len(opp)

    k=0
    if (mvpa & mvpg):
        k = 25
    elif (mvpa | mvpg):
        k = 10

    if R == 1:
        return current +  G(g) + A(a) + AG(ag) + W(R) * H(SR_opp_avg, SR_own_avg) + k + WS(ws)
    elif R == -1:
        return current +  G(g) + A(a) + AG(ag) + W(R) * H(SR_own_avg, SR_opp_avg) + k + WS(ws)
    else:
        return current +  G(g) + A(a) + AG(ag) + k + WS(ws)
    
def average(own, opp):
    SR_own = 0
    SR_opp = 0
    for player in own:
        SR_own += Players[player][SEASON]["SR"]
    SR_own_avg = SR_own / len(own)
    for player in opp:
        SR_opp += Players[player][SEASON]["SR"]
    SR_opp_avg = SR_opp / len(opp)
    return SR_opp_avg, SR_own_avg

