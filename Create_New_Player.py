import Player
import Rating
import time


def new_player():

    print("To add a new player, please follow the instrucitions.")
    time.sleep(1)
    print("Press any key to continue...")
    input()
    print("Tell us something about the player you want to add.")
    time.sleep(0.5)
    print("What is the player's name?")
    name = input("Name: ")
    print("What is the player's surname?")
    surname = input("Surname: ")
    print("What is the player's nickname? Nickname must be specific to the person. You should used if two or more players share the same name.")
    nick = input("Nickname: ")
    print("Great. We've got everything we need. Please, confirm the information.")
    print("-" * 30)
    print("Name: " + name)
    print("Surname: " + surname)
    print("Nickname: " + nick)
    print("-" * 30)
    print("Begin player creation?")
    confirm = input("Yes/No (y/n): ")
    for i in range(10):
        if confirm == "y":
            for x in range (0,5):  
                b = "Creating a player" + "." * x
                print (b, end="\r")
                time.sleep(0.5)
            print("Player created.                        ")
            break
        if confirm == "n":
            print("Player not added.")
            break
        else:
            print("Please, confirm by pressing 'y' or cancel by pressing 'n'.")
            time.sleep(0.5)
            confirm = input("Yes/No (y/n): ")

    return [name, surname, nick]

def add_player(lst):
    max_id = len(Rating.PLAYERS_LIST)
    new_id = max_id + 1
    player = Player.Player(new_id, lst[0], lst[1], lst[2])
    with open(Rating.RATINGS, "a") as f:
        f.write("Player ID: " + str(player.id) + "\n")  
        f.write("Name: " + player.name + "\n")
        f.write("Surname: " + player.sur + "\n")
        f.write("Nickname: " + player.nick + "\n")
        f.write("Goals: " + str(player.g) + "\n")
        f.write("Assists: " + str(player.a) + "\n")
        f.write("Autogoals: " + str(player.ag) + "\n")
        f.write("Wins: " + str(player.w) + "\n")
        f.write("Loses: " + str(player.l) + "\n")
        f.write("Draws: " + str(player.atn - player.w - player.l) + "\n")
        f.write("Attendences:" + "\n")
        f.write("- Total: " + str(player.atn) + "\n")
        f.write("- Last: " + player.atl + "\n" )
        f.write("MMR: " + str(round(player.get_mmr())) + "\n")
        f.write("Seasons Ratings: " + "\n")
        for i in range(Rating.Seasons):
            f.write("- Season " + str(i+1) + ": " + str(0) + "\n")
        f.write(30*"*" + "\n")

 
    return None

add_player(new_player())
