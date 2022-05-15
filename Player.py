import math
import Season

class Player:

    def __init__(self, id, name="", surname="", nick = "", goal=0, assist=0, attendence=[0, ""], autogoal=0, MMR=0, Seasons = [], wins=0, loses=0):
        self.id = id
        self.name = name
        self.sur = surname
        self.nick = nick
        self.g = goal
        self.a = assist
        self.atn = attendence[0]
        self.atl = attendence[1]
        self.ag = autogoal
        self.mmr = MMR
        self.seasons = Seasons
        self.w = wins
        self.l = loses

    def __str__(self):
        return "Player ID: " + str(self.id) + " \nPlayer: " + self.name + " \nSurname: " + self.sur

    def winrate(self):
        return fraction(float(self.w), float(self.atn))

    def g_avg(self):
        return fraction(float(self.g), float(self.atn))
    
    def a_avg(self):
        return fraction(float(self.a), float(self.atn))

    def ag_avg(self):
        return fraction(float(self.ag), float(self.atn))

    def get_mmr(self):
        A = self.winrate()
        B = self.g_avg()
        C = self.a_avg()
        D = self.ag_avg()

        Z = (4 / math.pi) * math.atan(math.exp(B/2) + math.exp(C/4) - 2)
        X = math.exp(-D) * 250
        Y = 500 * math.exp(-D)
        W = 500 * (math.exp(A - 0.5))
        return Z * X + Y + W
    

def fraction(n,m):
    if m == 0:
        return 0
    else:
        return n/m

# b = Player(100, "MMR", "Test", "MMRT", 0, 0, [8, "1.1.2022"], 0, 1000, [], 0, 8)

