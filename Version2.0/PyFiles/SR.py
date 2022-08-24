from ctypes.wintypes import HANDLE
from re import X
import numpy
import math
import Load

Players = Load.load()
SEASON = "S" + str(Players["season"]) + "R"

# Values of each
G = lambda x: 10*x + max(0, 2*(x - 2))   # 10 SR for 1st and second, after that, 12 per goal
A = lambda x: 6*x + max(0, 2*(x - 2))    # 6 SR for 1st and second, after that, 8 per assist
AG = lambda x: -2*x                     # -2 SR per auto goal
W = lambda x: 20*x                      # 20 SR for victory, 0 for draw and -20 for defeat, but it's weighted
WS = lambda x: 5*(x - 1)                # 5 for each winstreak: 5, 10, 15, 20 ...
H = lambda x,y: 1 + 10 * (x/y - 1)      # Weight (Heavy)



def SR_calculator(current, R, g, a, ag, ws, mvpg, mvpa, own, opp):
    # R = result from previous match [win | loss | draw]
    # G/A/AG = goals/assists/autogoals from previoous match
    # WS = winstreak
    # MVPG/MVPA = [True | False] MVPs for Goals or Assists
    # own/opp = firendly team / opponent team

    SR_own = 0
    SR_opp = 0
    for player in own:
        SR_own += Players[player][SEASON]
    SR_own_avg = SR_own / len(own)
    for player in opp:
        SR_opp += Players[player][SEASON]
    SR_opp_avg = SR_opp / len(opp)

    if R == "win":
        r = 1
    if R == "draw":
        r = 0
    if R == "loss":
        r = -1

    k=0
    if (mvpa & mvpg):
        k = 25
    elif (mvpa | mvpg):
        k = 10
             
    return current +  G(g) + A(a) + AG(ag) + W(r) * H(SR_opp_avg, SR_own_avg) + k + WS(ws)


