import Add_player
import time


print("Welcome!")
print("Do you want to add a new player?")
a = input("[Y|N]; Y - yes; N - no: ")
if a == "N":
    print("Okay. See ya next time!")
done = False
if a == "Y":
    print("Great!")
    time.sleep(0.5)
    print("Please provide more information about the new player.")
    time.sleep(0.5)
    while done == False:
        print("We will start with player's name. Please provide your player's full name (including multiple ones).")
        b = input("Name: ")
        time.sleep(0.5)
        print("Next, it will be his surname. Please provide your player's full surname (including multiple ones).")
        c = input("Surname: ")
        time.sleep(0.5)
        print("Lastly, please write all player's nicknames. If player has multiple names and surnames please write each one also individualy as nicknames. Seperate them just with a comma. E.q. Danny,Thunder,Shark")
        d = input("Nicknames: ")
        time.sleep(0.5)
        print("Now please check your inforamtion again.")
        print("\n")
        print("-------PLAYER---CARD-------")
        print("Name: " + b)
        print("Surname: " + c)
        nicks = d.split(",")
        print("Nicknames: ")
        for nick in nicks:
            if nick != "":
                print("-> " + nick)
            else: 
                nicks = []
            
        print("--------------------------")
        print("\n")
        time.sleep(0.5)
        p = input("Are the information correct? [Y|N]: ")
        if p == "N":
            print("Yikes, there must have beein a typo.")
            g = input("Would you like to repeat the process?[Y|N]: ")
            if g == "N":
                print("Okay. See ya next time!")
                break
        if p == "Y":
            print("Cool!")
            time.sleep(0.5)
            print("Player " + b + " " + c + " will be added to the player base. This may take a moment.")
            k = Add_player.new_player(b, c, nicks)
            for x in range (0,5):
                if x != 5:  
                    y = "Adding" + "." * x
                    print (y, end="\r")
                    time.sleep(0.75)     
                else:
                    y = "Adding" + "." * x
                    print (y)
                    time.sleep(0.75)
            if k:
                print("Player successfully added.")
            else:
                print("Player already exsists in playerbase.")
            done = True


