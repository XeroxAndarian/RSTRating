## Navodila za uporabo - kreiranje ekip

1. Namestite si aplikacijo, ki lahko požene python datoteke. Če ne veste katero iščite po iskalniku kaj na sceno "python", "edit" ipd.

[Pydroid 3](https://play.google.com/store/apps/details?id=ru.iiec.pydroid3) (Android)\
[Python Editor](https://apps.apple.com/us/app/python-editor-app/id1672453872) (iOS)



2. Iz Mape [DIC](https://drive.google.com/drive/folders/108yeOEXMw8jhqsven3g5MV-iH60DcHmV?usp=drive_link) si prenesite aplikacijo `TeamCalculator_v1.x.py` (x neka številka odvisna od verzije) in jo shranite v telefon tako, da boste vedeli kam. 

3. Odprite `TeamCalculator_v1.x.py` s pomočjo aplikacije, ki ste si jo izbrali v koraku 1.

4. Poleg datoteke `TeamCalculator_v1.x.py` je v mapi [DIC](https://drive.google.com/drive/folders/108yeOEXMw8jhqsven3g5MV-iH60DcHmV?usp=drive_link) tudi `Players[datum].txt` * datoteka. 

\* Če se datum na datoteki `Players[datum].txt` **ne ujema z datum zadnjega termina to sporočite meni**. Lahko sicer uporabite starejše podatke (in za MMR so na tem mestu spremembe bolj ali manj minimalne), vendar ne bo čisto natačno.


5. Celotno vsebino datoteke skopirajte in jo prilepite v označen prostor v `TeamCalculator_v1.x.py`. Natančneje, prilepite celotno vsebino med dvojno ograjo: 
```python
# ===================== TU NOTRI PRILEPI DIC =========


vsebina datoteke "Players[datum].txt"


# Če igralca ni, ga zakomentiraj z "#"
# Če imata dva enak score sprermeni enega za +0.1 oz. -0.1

# ============================= NE SPREMINJAJ ==========
```

6. Pred prisotnimi igralci pobrišite lojtre (#). 

Primer:

```python
...
    "Lovšin Andraž" : 1110.0,
    "Babnik Nejc" : 1100.32,
 #   "Petrovič Blaž" : 1095.84,
 #   "Grad Danijel" : 1103.58,
    "Deželak Jaka" : 1109.59,
 #   "Bogataj Erik" : 1119.49,
 #   "Fele Miha" : 1073.46,
 #   "Prednik Gal" : 1129.25,
    "Petrovič Gašper" : 1143.72,
    "Šalamun Jan" : 1105.62,
 #   "Hribar Janez" : 1110.96,
    "Jerak Matej" : 1092.97,
    "Kokalj Jernej" : 1090.86,
    "Štrumbelj Luka" : 1113.94,
 ...
```
V zgornjem primeru so prisotni Andraž, Nejc, Jaka, Gašper, Jan, Matej, Jernej in Luka.

7. Poženite program. Večina editorjev (med drugim tudi zgoraj navedena dva) ima za pogon programa trikotni simbol, ki ga na predvajalnikih glasbe in videev poznami tudi kot "play button".

8. Izpisati bi se morala vsaj ena možnost ekip.

Primer:
```
Število igralcev: 8
****************************************
Option 1:
---------------- Team A ----------------
-> Deželak Jaka
-> Petrovič Gašper
-> Jerak Matej
-> Kokalj Jernej
Average rating: 1109
---------------- Team B ----------------
-> Lovšin Andraž
-> Babnik Nejc
-> Šalamun Jan
-> Štrumbelj Luka
Average rating: 1107
Standings Divergence:  4
****************************************
```

Iz seznamov preporsoto razberite igralce v posamezni ekipi. Barvo dresov lahko določite naknadno.

Lahko se zgodi (redko), da bo dalo več možnosti. V tem primeru je našel dve ekvivalentni razporeditvi igralcev (z vidika MMR). V tem primeru priporočam, da vzamete možosti, ki ima manjši `Standings Divergence`.


## Navodila za uporabo - beleženje statistike

[Tabela](https://docs.google.com/spreadsheets/d/1vkC97h4CXLo96XvU-as9QEFaJLYS9mvunBy6fx7QOWc/edit?gid=762821190#gid=762821190)

### Tekma

1. Podvojite zavihek `Privzeto - tekma`
2. Spremenite ime zavihka na datum termina v obliki `yyyy-mm-dd`
3. Taisti datum vpišite v polje `A2`
4. V stolpce player vpišite igralce v posamezni ekipi. Tu upoštevajte naslednje:
   a) Začnete čisto na vrhu in ne spuščate vrstic med igralci\
   b) Poskrbite, da so imena taka, da se igralce lahko natančno identificira. Najbolje je zapisati vzdevek - ta je gotovo specifičen na igralca. To storite predvsem pri igralcih, ki si delijo ime s kom drugim. Lahko si pomagate s statistikami iz prejšnjih tekem.\
   c) Glejte, da bodo imena tudi slovnično pravilno zapisana
5. Gol, asistence in avtogol se označuje s simbolom (do sedaj je bila praksa veliki i = "I"). Vsak gol, assitenca oz. avtogol je svoj simbol. \
Primer:\
`II` - dva gola,\
`xyz` - tri assistence \
`4` - en gol
6. Stoplec za denar pustite prazen

### Turnir

1. Podvojite zavihek `Privzeto - turnir`
2. Spremenite ime zavihka na datum termina v obliki `yyyy-mm-dd`
3. Taisti datum vpišite v polje `A2`
4. V stolpce player vpišite igralce v posamezni ekipi. Tu upoštevajte naslednje:
   a) Začnete čisto na vrhu in ne spuščate vrstic med igralci\
   b) Poskrbite, da so imena taka, da se igralce lahko natančno identificira. Najbolje je zapisati vzdevek - ta je gotovo specifičen na igralca. To storite predvsem pri igralcih, ki si delijo ime s kom drugim. Lahko si pomagate s statistikami iz prejšnjih tekem.\
   c) Glejte, da bodo imena tudi slovnično pravilno zapisana
5. Gol, asistence in avtogol se označuje s simbolom (do sedaj je bila praksa veliki i = "I"). Vsak gol, assitenca oz. avtogol je svoj simbol. \
Primer:\
`II` - dva gola,\
`xyz` - tri assistence \
`4` - en gol

6. Stoplec za denar pustite prazen
7. Številke pri ekipah, ki beležijo zmage (W), poraze (L) in izenačenja (T) so samo dekorativne. Lahko jih spremenite, da ob koncu lažje vidite tmagovalca turnirja. Prvi stolpec 

#### 3x3

8. Če je turnir 3x3 nadomestite polje `A18:B18` (Team4) z `None`.
9. Izpolnite levo tabelo (Tournament 3x3). Vsaka izmed 6 tekem šteje za polčas. Na koncu v najbolj desni stolpec vpišite končni rezultat. **Bodite pozorni na to, katera ekipa je ekipa 1, katera ekipa 2 itd.**

#### 4x4
8. Izpolnite desno tabelo (Tournament 4x4). Vsaka izmed 6 tekem šteje za celotno tekmo. V stolpec vpišite končni rezultat. **Bodite pozorni na to, katera ekipa je ekipa 1, katera ekipa 2 itd.**
