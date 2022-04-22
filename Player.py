

class Player:

    def __init__(self, id, name="", surname="",nick = "", goal=0, assist=0, attendence=["", ""], autogoal=0, MMR=0, SR = []):
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
        self.sr = SR

    def __str__(self):
        return "Player ID: " + str(self.id) + " \nPlayer: " + self.name + " \nSurname: " + self.sur

