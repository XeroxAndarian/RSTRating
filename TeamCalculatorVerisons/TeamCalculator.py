import random
import copy
import time

DIC = {
#    "Aljaž": 1085,
#    "Andraz": 1043,
    "Becho":1021,
    "Blaž": 1043,
    "Danijel": 1000,
#    "Dejan":1254,
    "Deželak":1047,
#    "Erik":979,    
#    "Fele":1013,
    "Gal":1091,
    "Gap":1131,
    "Jan":1061,
    "Janez":1024,
#    "Jerak":939,
    "Jernej":1006,
    "Luka":975,
    "Maks":977,
#    "Marko":978,
    "Matevž":991,
    "Pavli":1107,
    "Tilen":1032,
#    "Urh":711

    }

DIC_COPY = dict(DIC)


# Če igralca ni, je dovolj da mu nastaviš rating na 0
# Če imata dva enak score sprermeni enega za +1 oz. -1



ODD_PLAYER = " "

def MakeItEven(DIC):
    new_dic = {}
    values = list(DIC.values())
    global ODD_PLAYER
    if (len(values) % 2 == 0) | (len(values) < 11):
        new_dic = dict(DIC)
        ODD_PLAYER = " "
    else:
        values.sort()
        while len(values) > 1:
            del values[0]
            del values[-1]    
        m = values[0]
        igralec = list(DIC.keys())[list(DIC.values()).index(m)]
        new_dic = dict(DIC)
        new_dic[igralec] = 0
        ODD_PLAYER = igralec
    return new_dic

def Player_Complier(dic):
    new_dic = {}
    for player in dic:
        if (dic[player] != 0):
            new_dic[player] = dic[player]
    return new_dic


def listFairestWeakTeams(ratings):
    current_best_weak_team_rating = -1
    fairest_weak_teams = []
    for weak_team in recursiveWeakTeamGenerator(ratings):
        weak_team_rating = teamRating(weak_team, ratings)
        if weak_team_rating > current_best_weak_team_rating:
            fairest_weak_teams = []
            current_best_weak_team_rating = weak_team_rating
        if weak_team_rating == current_best_weak_team_rating:
            fairest_weak_teams.append(weak_team)
    return fairest_weak_teams


def recursiveWeakTeamGenerator(
    ratings,
    weak_team=[],
    current_applicant_index=0
):
    if not isValidWeakTeam(weak_team, ratings):
        return
    if current_applicant_index == len(ratings):
        yield weak_team
        return
    for new_team in recursiveWeakTeamGenerator(
        ratings,
        weak_team + [current_applicant_index],
        current_applicant_index + 1
    ):
        yield new_team
    for new_team in recursiveWeakTeamGenerator(
        ratings,
        weak_team,
        current_applicant_index + 1
    ):
        yield new_team


def isValidWeakTeam(weak_team, ratings):
    total_rating = sum(ratings)
    weak_team_rating = teamRating(weak_team, ratings)
    optimal_weak_team_rating = total_rating // 2
    if weak_team_rating > optimal_weak_team_rating:
        return False
    elif weak_team_rating * 2 == total_rating:
        # In case of equal strengths, player 0 is assumed
        # to be in the "weak" team
        return 0 in weak_team
    else:
        return True


def teamRating(team_members, ratings):
    return sum(memberRatings(team_members, ratings))    


def memberRatings(team_members, ratings):
    return [ratings[i] for i in team_members]


def getOpposingTeam(team, ratings):
    return [i for i in range(len(ratings)) if i not in team]

def get_key(DIC, val):
    for key, value in DIC.items():
         if val == value:
             return key
 
    return "key doesn't exist"

def team_comp(list):
    team = []
    for player in list:
        team.append(get_key(DIC, player))
    return team

def translator(DIC, score):
    return list(DIC.keys())[list(DIC.values()).index(score)]

def score(DIC, name):
    return DIC.get(name)
    
def average_rating(DIC, team):
    team_by_score = [score(DIC, igralec) for igralec in team]
    n = len(team)
    return round(sum(team_by_score)/n) 


def three_teams_generator_simple(ratings):
    team_1 = []
    team_2 = []
    team_3 = []
    ratings.sort()
    
    t1 = [ratings[0], ratings[1], ratings[2]]
    r1 = random.choice(t1)
    team_1.append(r1)
    t1.remove(r1)
    r2 = random.choice(t1)
    team_2.append(r2)
    t1.remove(r2)
    team_3.append(t1[0])
    t1.remove(t1[0])

    t2 = [ratings[3], ratings[4], ratings[5]]
    r1 = random.choice(t2)
    team_2.append(r1)
    t2.remove(r1)
    r2 = random.choice(t2)
    team_3.append(r2)
    t2.remove(r2)
    team_1.append(t2[0])
    t2.remove(t2[0])

    t3 = [ratings[6], ratings[7], ratings[8]]
    r1 = random.choice(t3)
    team_3.append(r1)
    t3.remove(r1)
    r2 = random.choice(t3)
    team_1.append(r2)
    t3.remove(r2)
    team_2.append(t3[0])
    t3.remove(t3[0])

    t4 = [ratings[9], ratings[10], ratings[11]]
    r1 = random.choice(t4)
    team_1.append(r1)
    t4.remove(r1)
    r2 = random.choice(t4)
    team_3.append(r2)
    t4.remove(r2)
    team_2.append(t4[0])
    t4.remove(t4[0])

    t5 = [ratings[12], ratings[13], ratings[14]]
    r1 = random.choice(t5)
    team_2.append(r1)
    t5.remove(r1)
    r2 = random.choice(t5)
    team_1.append(r2)
    t5.remove(r2)
    team_3.append(t5[0])
    t5.remove(t5[0])

    team1 = []
    team2 = []
    team3 = []
    
    for score in team_1:
        team1.append(translator(DIC, score))
    for score in team_2:
        team2.append(translator(DIC, score))
    for score in team_3:
        team3.append(translator(DIC, score))
        

    return team1, team2, team3

def two_team_partitions(DIC):
    teamstrong_pbty = []
    teamweak_pbty = []
    Players = Player_Complier(MakeItEven(DIC))
    ratings = list(Players.values())
    for option, weak_team in enumerate(listFairestWeakTeams(ratings)):
        strong_team = getOpposingTeam(weak_team, ratings)
        strong = team_comp(memberRatings(strong_team, ratings))
        teamstrong_pbty.append((option, strong))
        weak = team_comp(memberRatings(weak_team, ratings))
        if ODD_PLAYER != " ":
            weak.append(ODD_PLAYER)
        teamweak_pbty.append((option, weak))
    return teamstrong_pbty, teamweak_pbty

def team_to_dic(DIC, list):
    new_dic = {}
    for player in list:
        new_dic[player] = score(DIC, player)
    return new_dic

def standings(DIC):
    S = {}
    sorted_players = list(DIC.values())
    sorted_players.sort()
    i = 1
    for rating in sorted_players:
        S[translator(DIC, rating)] = i
        i = i + 1
    return S

def standings_koefficient(team):
    k = 0
    S = standings(DIC)
    for player in team:
        k += S[player]
    return k


if len(DIC) < 15:
    global_pair = two_team_partitions(DIC)
    partitions = len(global_pair[0]) 
    print("*" * 50)
    for i in range(partitions):
        strong = global_pair[0][i][1]
        s = standings_koefficient(strong)
        weak = global_pair[1][i][1]
        w = standings_koefficient(weak)
        k = abs(s - w)
        print("Option ", i + 1 , ":")
        print("Team A: ", strong)
        print("Average Rating: ", average_rating(DIC, strong))
        print("Team B: ", weak)
        print("Average Rating: ", average_rating(DIC, weak))
        print("Standings Divergence: ", k)
        print("*" * 50)

if len(DIC) == 15:
    Players = Player_Complier(DIC)
    ratings = list(Players.values())
    print("*" * 10, " TURNAMENT 3x3 ", "*" * 10)
    min = 1000
    for i in range(10):
        teams = three_teams_generator_simple(ratings)
        maximum = max(abs(average_rating(DIC,teams[0]) - average_rating(DIC, teams[1])), abs(average_rating(DIC, teams[1]) - average_rating(DIC, teams[2])), abs(average_rating(DIC, teams[2]) - average_rating(DIC, teams[0])))
        if maximum < min:
            save_teams = teams
            min = maximum
    print("Team A:{}; ".format(save_teams[0]))
    print("Average rating: {}".format(average_rating(DIC, save_teams[0])))
    print("Team A:{}; ".format(save_teams[1]))
    print("Average rating: {}".format(average_rating(DIC, save_teams[1])))
    print("Team A:{}; ".format(save_teams[2]))
    print("Average rating: {}".format(average_rating(DIC, save_teams[2])))
    # print("Team B:{}; Average rating: {}".format(save_teams[1], average_rating(DIC, save_teams[1])))
    # print("Team C:{}; Average rating: {}".format(save_teams[2], average_rating(DIC, save_teams[2])))
    print("*" * 40)

if len(DIC) > 15 & len(DIC) < 21:
    global_pair = two_team_partitions(DIC)
    partitions = min(len(global_pair[0]), len(global_pair[1]))
    n = random.randint(0, partitions)
    step1 = team_to_dic(DIC_COPY, global_pair[0][n][1])
    step1_pair = two_team_partitions(step1) 
    team_A = step1_pair[0][0][1]
    team_B = step1_pair[1][0][1]
    step2 = team_to_dic(DIC_COPY, global_pair[1][n][1])
    step2_pair = two_team_partitions(step2)
    team_C = step2_pair[0][0][1]
    team_D = step2_pair[1][0][1]
    for player in (global_pair[0][n][1] + global_pair[1][n][1]):
        if (player not in team_A) & (player not in team_B) & (player not in team_C) & (player not in team_D):
            rating_A = average_rating(DIC, team_A)
            rating_B = average_rating(DIC, team_B)
            rating_C = average_rating(DIC, team_C)
            rating_D = average_rating(DIC, team_D)
            target = min(rating_A, rating_B, rating_C, rating_D)
            if target == rating_A:
                team_A.append(player)
                rating_A = average_rating(DIC, team_A)
            if target == rating_B & target != rating_A:
                team_B.append(player)
                rating_B = average_rating(DIC, team_B)
            if target == rating_C & target != rating_A & target != rating_B:
                team_C.append(player)
                rating_C = average_rating(DIC, team_C)
            if target == rating_D & target != rating_A & target != rating_B & target != rating_C:
                team_D.append(player)
                rating_D = average_rating(DIC, team_D) 
    k1 = min(len(team_A), len(team_B), len(team_C), len(team_D))
    k2 = max(len(team_A), len(team_B), len(team_C), len(team_D))
    if k1 == k2:
        print("*" * 15, " TOURNAMENT ", "4 x", k1, " ",   "*" * 15)
    else:
        print("*" * 15, " TOURNAMENT ", "4 x", k1, "-", k2, " ",   "*" * 15)
    print("Total players: ", len(DIC))
    print("Chance of success: ", random.randint(0,99), "%")
    print("-" * 30)
    time.sleep(3)
    check = (len(DIC) == len(team_A) + len(team_B) + len(team_C) + len(team_D))
    if check:
        print("Success!")
        print("Team A: ", team_A,";")
        print("Average Rating: ", average_rating(DIC, team_A),";")
        print("Players: ", len(team_B))
        print("Team B: ", team_B,";")
        print("Average Rating: ", average_rating(DIC, team_B),";")
        print("Players: ", len(team_B))
        print("Team C: ", team_C,";")
        print("Average Rating: ", average_rating(DIC, team_C),";")
        print("Players: ", len(team_C))
        print("Team D: ", team_D,";")
        print("Average Rating: ", average_rating(DIC, team_D),";")
        print("Players: ", len(team_D))
        # print("Team B: ", team_B, " , Average Rating: ", average_rating(DIC, team_B), "; Players: ", len(team_B))
        # print("Team C: ", team_C, " , Average Rating: ", average_rating(DIC, team_C), "; Players: ", len(team_C))
        # print("Team D: ", team_D, " , Average Rating: ", average_rating(DIC, team_D), "; Players: ", len(team_D))
    else:
        print("Failed! Try Again...")
    
    # if check:
    #     print("Matches:")
    #     print("A:B")
    #     print("C:D")
    #     print("A:C")
    #     print("B:D")
    #     print("A:D")
    #     print("B:C")
    print("*" * 50)



    
