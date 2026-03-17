import random
import time



# ===================== TU NOTRI PRILEPI DIC ===============================================


DIC = { 
    "Lovšin Andraž" : 1114.03,
    "Babnik Nejc" : 1103.44,
 #   "Petrovič Blaž" : 1098.89,
 #   "Grad Danijel" : 1105.27,
    "Deželak Jaka" : 1114.34,
 #   "Bogataj Erik" : 1119.49,
 #   "Fele Miha" : 1073.46,
 #   "Prednik Gal" : 1129.25,
    "Petrovič Gašper" : 1148.82,
 #   "Šalamun Jan" : 1107.39,
 #   "Hribar Janez" : 1110.96,
 #   "Jerak Matej" : 1102.26,
    "Kokalj Jernej" : 1089.68,
    "Štrumbelj Luka" : 1116.14,
    "Lajovic Maks" : 1113.88,
    "Šalamun Marko" : 1124.84,
    "Kokalj Matevž" : 1108.57,
 #   "Pavli Matej" : 1100.98,
    "Šalamun Tilen" : 1095.65,
 #   "Nikolovski Matevž" : 1161.01,
 #   "Gerič Jaka" : 1062.36,
 #   "Štebe Simon" : 1070.08,
 #   "Bert" : 972.41,
 #   "Kris" : 1000.0,
 #   "Judez Judez" : 1000.0,
 #   "Domen" : 1000.0,
 #   "Skufca Luka" : 1111.91,
 #   "Jašovič Črt" : 1118.58,
    "Sokler Luka" : 1161.85,
    "Žolnir Žan" : 1089.9,
    "Plut Matic" : 1079.53,
 #   "Smole Brin" : 1153.75,
 #   "Lan" : 1000.0,
 #   "Deželak Žak" : 1083.66,
 #   "Mark" : 1080.13,
 #   "Svetlin Vid" : 1080.13,
 #   "Žolnir Žiga" : 1061.65,
 #   "Miha" : 1125.5,
 #   "Sušnik Evgen" : 1211.89,
 #   "Špendl Filip Jakob" : 1144.56,
    "Kadunc Blaž" : 1148.56,
    "Milek Val" : 1115.02,
 #   "Redja Nai" : 1057.14,
 #   "Kerzic Jan" : 1211.89,
 #   "Plevcak Tim" : 1105.44,
    "Milek Nik" : 1101.86,
 #   "Čebela Jure" : 1000.0,
 #   "Kladnik Jan" : 1144.56,
 #   "Trošt Jan" : 1054.51,
 #   "Milek Tom" : 1054.51,
 #   "Matevž" : 1054.51
 }

ROLES ={
    "Lovšin Andraž": "O",
    "Babnik Nejc": "O",
    "Petrovič Blaž": "F",
    "Grad Danijel": "O",
    "Deželak Jaka": "F",
    "Bogataj Erik": "O",
    "Fele Miha": "N",
    "Prednik Gal": "F",
    "Petrovič Gašper": "F",
    "Šalamun Jan": "F",
    "Hribar Janez": "D",
    "Jerak Matej": "D",
    "Kokalj Jernej": "D",
    "Štrumbelj Luka": "F",
    "Lajovic Maks": "O",
    "Šalamun Marko": "F",
    "Kokalj Matevž": "D",
    "Pavli Matej": "F",
    "Šalamun Tilen": "D",
    "Nikolovski Matevž": "N",
    "Gerič Jaka": "O",
    "Štebe Simon": "N",
    "Bert": "N",
    "Kris": "N",
    "Judez Judez": "N",
    "Domen": "N",
    "Skufca Luka": "O",
    "Jašovič Črt": "F",
    "Sokler Luka": "F",
    "Žolnir Žan": "D",
    "Plut Matic": "F",
    "Smole Brin": "O",
    "Lan": "N",
    "Deželak Žak": "O",
    "Mark": "N",
    "Svetlin Vid": "N",
    "Žolnir Žiga": "O",
    "Miha": "N",
    "Sušnik Evgen": "F",
    "Špendl Filip Jakob": "N",
    "Kadunc Blaž": "F",
    "Milek Val": "F",
    "Redja Nai": "D",
    "Kerzic Jan": "N",
    "Plevcak Tim": "O",
    "Milek Nik": "F",
    "Čebela Jure": "F",
    "Kladnik Jan": "F",
    "Trošt Jan": "N"
}


# Če igralca ni, ga zakomentiraj z "#"
# Če imata dva enak score sprermeni enega za +0.1 oz. -0.1

# ========================================== NE SPREMINJAJ =================================


DIC_COPY = dict(DIC)

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


def normalize_roles(roles, players):
    normalized = {}
    for player in players:
        role = roles.get(player, "F")
        role = str(role).strip().upper()
        if role not in {"O", "D", "F", "N"}:
            role = "F"
        normalized[player] = role
    return normalized


def role_counts(team_indices, roles_list):
    counts = {"O": 0, "D": 0, "F": 0, "N": 0}
    for i in team_indices:
        role = roles_list[i]
        counts[role] = counts.get(role, 0) + 1
    return counts


def roles_balanced(team_indices, roles_list):
    all_indices = list(range(len(roles_list)))
    other_indices = [i for i in all_indices if i not in team_indices]
    counts_a = role_counts(team_indices, roles_list)
    counts_b = role_counts(other_indices, roles_list)
    o_counts = [counts_a.get("O", 0), counts_b.get("O", 0)]
    d_counts = [counts_a.get("D", 0), counts_b.get("D", 0)]
    return (max(o_counts) - min(o_counts) <= 1) and (max(d_counts) - min(d_counts) <= 1)


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
    players_list = list(Players.keys())
    ratings = list(Players.values())
    normalized_roles = normalize_roles(ROLES, players_list)
    roles_list = [normalized_roles[player] for player in players_list]
    best_role_balanced = []
    best_rating = -1
    for weak_team in recursiveWeakTeamGenerator(ratings):
        if not roles_balanced(weak_team, roles_list):
            continue
        weak_team_rating = teamRating(weak_team, ratings)
        if weak_team_rating > best_rating:
            best_rating = weak_team_rating
            best_role_balanced = []
        if weak_team_rating == best_rating:
            best_role_balanced.append(weak_team)
    if len(best_role_balanced) == 0:
        best_role_balanced = listFairestWeakTeams(ratings)
    for option, weak_team in enumerate(best_role_balanced):
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
    sorted_players.sort(reverse=True)
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

def print_team(team, name):
    output = ""
    output += (16 * "-" + f" {name} " + 16* "-"+  "\n")
    team_roles = normalize_roles(ROLES, team)
    counts = {"O": 0, "D": 0, "F": 0, "N": 0}
    for player in team:
        role = team_roles.get(player, "F")
        counts[role] = counts.get(role, 0) + 1
        output += f"-> {player} [{role}]"
        output += "\n"
    output = output[:-1]
    output += "\n"
    output += f"Average rating: {average_rating(DIC, team)}"
    output += "\n"
    output += f"Roles: O={counts['O']} D={counts['D']} F={counts['F']} N={counts['N']}"
    print(output)
    return None

def team_role_counts(team):
    team_roles = normalize_roles(ROLES, team)
    counts = {"O": 0, "D": 0, "F": 0, "N": 0}
    for player in team:
        role = team_roles.get(player, "F")
        counts[role] = counts.get(role, 0) + 1
    return counts


def roles_balanced_three(team_a, team_b, team_c):
    counts_a = team_role_counts(team_a)
    counts_b = team_role_counts(team_b)
    counts_c = team_role_counts(team_c)
    o_counts = [counts_a.get("O", 0), counts_b.get("O", 0), counts_c.get("O", 0)]
    d_counts = [counts_a.get("D", 0), counts_b.get("D", 0), counts_c.get("D", 0)]
    return (max(o_counts) - min(o_counts) <= 1) and (max(d_counts) - min(d_counts) <= 1)


def roles_balanced_four(team_a, team_b, team_c, team_d):
    counts_a = team_role_counts(team_a)
    counts_b = team_role_counts(team_b)
    counts_c = team_role_counts(team_c)
    counts_d = team_role_counts(team_d)
    o_counts = [
        counts_a.get("O", 0),
        counts_b.get("O", 0),
        counts_c.get("O", 0),
        counts_d.get("O", 0)
    ]
    d_counts = [
        counts_a.get("D", 0),
        counts_b.get("D", 0),
        counts_c.get("D", 0),
        counts_d.get("D", 0)
    ]
    return (max(o_counts) - min(o_counts) <= 1) and (max(d_counts) - min(d_counts) <= 1)

def key_with_smallest_value(d):
    """Return the key that has the smallest value in dictionary d."""
    if not d:
        return None  # or raise ValueError("Empty dictionary")
    key = min(d, key=d.get)
    return key, d[key]
    
# ============================================================ PROGRAM ==================================

print(f"Število igralcev: {len(DIC)}")

if len(DIC) == 11 or len(DIC) == 13:
    razrstitev = standings(DIC)
    srednji = list(razrstitev.keys())[len(DIC)//2]
    srednji_mmr = DIC[srednji]
    del DIC[srednji]
    global_pair = two_team_partitions(DIC)
    partitions = len(global_pair[0])
    DIC[srednji] = srednji_mmr
    print("*" * 40)
    for i in range(partitions):
        strong = global_pair[0][i][1]
        weak = global_pair[1][i][1]
        if average_rating(DIC, strong) < srednji_mmr:
            weak.append(srednji)
        else:
            strong.append(srednji)
        s = standings_koefficient(strong)
        w = standings_koefficient(weak)
        k = abs(s - w)
        print(f"Option {i + 1}:")
        print_team(strong, "Team A")
        print_team(weak, "Team B")
        print("Standings Divergence: ", k)
        print("*" * 40)
        
elif len(DIC) == 9:
    sidro = key_with_smallest_value(DIC)
    del DIC[sidro[0]]
    global_pair = two_team_partitions(DIC)
    partitions = len(global_pair[0]) 
    DIC[sidro[0]] = sidro[1]
    print("*" * 40)
    for i in range(partitions):
        strong = global_pair[0][i][1]
        s = standings_koefficient(strong)
        weak = global_pair[1][i][1]
        weak.append(sidro[0])
        w = standings_koefficient(weak)
        k = abs(s - w)
        print(f"Option {i + 1}:")
        print_team(strong, "Team A")
        print_team(weak, "Team B")
        print("Standings Divergence: ", k)
        print("*" * 40)

elif len(DIC) < 15:
    global_pair = two_team_partitions(DIC)
    partitions = len(global_pair[0]) 
    print("*" * 40)
    for i in range(partitions):
        strong = global_pair[0][i][1]
        s = standings_koefficient(strong)
        weak = global_pair[1][i][1]
        w = standings_koefficient(weak)
        k = abs(s - w)
        print(f"Option {i + 1}:")
        print_team(strong, "Team A")
        print_team(weak, "Team B")
        print("Standings Divergence: ", k)
        print("*" * 40)
        

elif len(DIC) == 15:
    Players = Player_Complier(DIC)
    ratings = list(Players.values())
    print("*" * 10, " TURNAMENT 3x3 ", "*" * 10)
    best_max_diff = 1000
    save_teams = None
    fallback_best = 1000
    fallback_teams = None
    for i in range(30):
        teams = three_teams_generator_simple(ratings)
        maximum = max(
            abs(average_rating(DIC, teams[0]) - average_rating(DIC, teams[1])),
            abs(average_rating(DIC, teams[1]) - average_rating(DIC, teams[2])),
            abs(average_rating(DIC, teams[2]) - average_rating(DIC, teams[0]))
        )
        if maximum < fallback_best:
            fallback_best = maximum
            fallback_teams = teams
        if not roles_balanced_three(teams[0], teams[1], teams[2]):
            continue
        if maximum < best_max_diff:
            save_teams = teams
            best_max_diff = maximum
    if save_teams is None:
        save_teams = fallback_teams
   
    print_team(save_teams[0], "Team A")
    print_team(save_teams[1], "Team B")
    print_team(save_teams[2], "Team C")
    print("*" * 40)

elif len(DIC) > 15 & len(DIC) < 21:
    global_pair = two_team_partitions(DIC)
    partitions = min(len(global_pair[0]), len(global_pair[1]))
    n = random.randint(0, partitions - 1)
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

    if not roles_balanced_four(team_A, team_B, team_C, team_D):
        remaining_players = [
            player for player in (global_pair[0][n][1] + global_pair[1][n][1])
            if player not in team_A and player not in team_B and player not in team_C and player not in team_D
        ]
        for player in remaining_players:
            counts_a = team_role_counts(team_A)
            counts_b = team_role_counts(team_B)
            counts_c = team_role_counts(team_C)
            counts_d = team_role_counts(team_D)
            o_counts = [counts_a.get("O", 0), counts_b.get("O", 0), counts_c.get("O", 0), counts_d.get("O", 0)]
            d_counts = [counts_a.get("D", 0), counts_b.get("D", 0), counts_c.get("D", 0), counts_d.get("D", 0)]
            min_o = min(o_counts)
            min_d = min(d_counts)
            team_targets = []
            player_role = normalize_roles(ROLES, [player]).get(player, "F")
            if player_role == "O":
                team_targets = [team_A, team_B, team_C, team_D]
                team_targets = [t for t, o in zip(team_targets, o_counts) if o == min_o]
            elif player_role == "D":
                team_targets = [team_A, team_B, team_C, team_D]
                team_targets = [t for t, d in zip(team_targets, d_counts) if d == min_d]
            else:
                team_targets = [team_A, team_B, team_C, team_D]
            if not team_targets:
                team_targets = [team_A, team_B, team_C, team_D]
            ratings_targets = [average_rating(DIC, t) for t in team_targets]
            target_team = team_targets[ratings_targets.index(min(ratings_targets))]
            target_team.append(player)
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
        print_team(team_A, "Team A")
        print_team(team_B, "Team B")
        print_team(team_C, "Team C")
        print_team(team_D, "Team D")
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

else:
    print("Preveč igralcev cela za 4x4 format!")

    
