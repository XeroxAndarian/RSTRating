import math
from scipy.integrate import quad
from math import pi, exp
import Find
import Load
import Save



def MMR_calculator(WR, G, A, AG):
    f = float(6* WR + 2 * G + A - AG)/6
    sd   = 1.5
    mean = 0
    Itg = quad(lambda x: 1 / ( sd * ( 2 * pi ) ** 0.5 ) * 5 / 2 * exp( -x ** 2 / (sd ** 2) ), 0, f)
    MMR = 250 * Itg[0] + 1000
    return MMR

def MMR(id):
    ID_Card = Find.get_id_card(id)
    return MMR_calculator(ID_Card["winrate"], ID_Card["goal average"], ID_Card["assist average"], ID_Card["auto goal average"])

# MMR_calculator(0.439, 0.27, 0.24, 0)

def MMR_updator():
    Players = Load.load()
    for player in Players:
        if type(Players[player]) != dict:
            continue
        avg_g = Players[player]["goals"] / max(Players[player]["matches played"], 1)
        avg_a = Players[player]["assists"] / max(Players[player]["matches played"], 1)
        avg_ag = Players[player]["auto goals"] / max(Players[player]["matches played"],1)
        wr = Players[player]["wins"] / max(Players[player]["matches played"], 1)
        Players[player]["MMR"] = MMR_calculator(wr, avg_g, avg_a, avg_ag)
    
    Save.save(Players, False)

MMR_updator()