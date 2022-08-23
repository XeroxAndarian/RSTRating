import math

class Season:

    def __init__(self, id, season=0, name="", surname="", nick = "", goal=0, assist=0, attendence=[0, ""], autogoal=0, SR = 0, wins=0, loses=0, con_wins=0, position=[0, 0], winstreak=0):
        self.id = id
        self.season = season
        self.name = name
        self.sur = surname
        self.nick = nick
        self.g = goal
        self.a = assist
        self.atn = attendence[0]
        self.atl = attendence[1]
        self.ag = autogoal
        self.sr = SR
        self.w = wins
        self.l = loses
        self.cw = con_wins
        self.pos = position
        self.winstreak = winstreak

    def rating(self):
        
        return 0