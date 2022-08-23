import math

class Player:

    def __init__(self, id):
        self.id = id
    
    def __str__(self):
        return "Player ID: " + str(self.id) + "."


    def set_name(self, name):
        self.name = name
    
    def set_surname(self, surname):
        self.sur = surname

    def set_goal(self, goals):
        self.goal = goals

    def set_assist(self, assist):
        self.ass = assist

    def set_autogoal(self, auto):
        self.ag = auto

    def set_MMR(self, MMR):
        self.mmr = MMR

    def set_SR(self, SR):
        self.sr = SR

    def set_score(self, played, win, loss):
        self.plyd = played
        self.win = win
        self.loss = loss
        self.draw = played - win - loss




