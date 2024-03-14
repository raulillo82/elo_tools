import gdown
import pandas
from io import BytesIO, StringIO
from dbfread import DBF
from pandas import DataFrame
from os.path import exists, isfile
from zipfile import ZipFile, ZipInfo
from urllib.request import urlopen
#import tempfile
#Try to refactor with tempfiles


def get_basque_elos():
    '''
    Returns a list with two panda DF
    First element: clubs
    Second element: players
    '''
    #Download file unless it already exists
    elovasco_file = "./elovasco.zip"
    if exists(elovasco_file):
        print("El fichero de ELOs vascos ya está en el disco, omitiendo descarga")
    else:
        print("Descargando fichero de ELOs vascos de gdrive")
        url_elovasco = "https://drive.google.com/uc?id=1pmXsi5xUikUWMo5CSpA0zYpwhTnMIYsc"
        gdown.download(url_elovasco, elovasco_file, quiet=True)
    #Warn about file being dated in 2022
    print("Fichero de jugadores vascos de enero de 2022, NO se comprueba si hay alguno más reciente")
    #Open zip file
    with ZipFile(elovasco_file) as archive:
        #Get databases from file
        dbf_files = [file for file in archive.namelist() if file.endswith(".dbf")]
        #Check whether the zipfile is already unzipped:
        if all([isfile(file) for file in dbf_files]):
            print("Fichero ya descomprimido, omitiendo descompresión")
        else:
            print("Descomprimiendo archivo")
            #Extract all dbf files (overkill, but required by DBF)
            archive.extractall()
        #Fetch needed DBs
        #First is clubs
        dbf_clubs = DBF(dbf_files[0])
        df_clubs = DataFrame(iter(dbf_clubs))
        #Second is players
        dbf_players = DBF(dbf_files[1])
        df_players = DataFrame(iter(dbf_players))
        #print(df_players)
        #print(df_clubs)
        return [df_clubs, df_players]


def get_fide_elos():
    '''
    Returns a panda DF with the FIDE ELOs
    '''
    url_list_latest = "http://ratings.fide.com/download/standard_rating_list_xml.zip"
    resp = urlopen(url_list_latest)
    with ZipFile(BytesIO(resp.read())) as archive:
        #zipfile has only one compressed file:
        xml_file = archive.namelist()[0]
        #Get the date, it's a tuple
        date = archive.getinfo(xml_file).date_time
        #Time is not needed, just the date. Make it human readable
        human_date = str(date[2]) + "/" + str(date[1]) + "/" + str(date[0])
        #Some formatting
        print(f"ELOs FIDE a fecha de {human_date}:")
        #Read the whole XML into a pandas dataframe
        return pandas.read_xml(archive.open(xml_file))


def print_club_fide_elos(df_clubs, df_basque_players, df_fide_players):
    '''
    Prints the players of Basque club, together with their FIDE ELO, if they
    have one
    '''
    #Iterate each of the clubs in Basque DB
    for club in df_clubs:
        for index_club, club_data in club.iterrows():
            #First print which club it is
            print(club_data.CLUB)
            #Iterate through each of the players of the club
            for index_player, player in df_basque_players[
                    df_basque_players.CLUB.isin([club_data.CLAVE])].iterrows():
                #Convert name to "Title" case
                player_name = player.JUG.title()
                #Sometimes there's no comma in the name, fix it
                if "," not in player_name:
                    player_name_temp = player_name.split()
                    if len(player_name_temp) > 1:
                        player_name_temp[-2] = player_name_temp[-2] + ","
                        player_name = " ".join(player_name_temp)
                #Search for the players in the FIDE list.
                player_id = df_fide_players[df_fide_players.name.str.contains(player_name,
                                                                              case=False)]
                #If there's a match, print only some fields.
                if not player_id.empty:
                    #fideid name sex rating birthday
                    print(player_name + " - ELO FIDE: " + player_id.rating.to_string(index=False)
                          + " - ESTADO: " + player_id.flag.to_string(index=False)
                          + " - ELO VASCO: " + str(player.ELO))
                else:
                    print(player_name)
            print()

[df_basque_clubs, df_basque_players] = get_basque_elos()
#print(df_basque_players)

#Get clubs from Araba
#Search for the players in the list.
clubs_araba = df_basque_clubs[df_basque_clubs.PROV.isin(["A"])]
#Print results. Remove the index column (misleading for non-developers)
#print(clubs_araba)
#Show "JUG" / "CLUB"

#Two of the clubs to use as example
#Avoiding to have thousands of lines in the output during testing
club_sanvi = clubs_araba[clubs_araba.CLUB.isin(["SAN VIATOR"])]
club_martintxo = clubs_araba[clubs_araba.CLUB.isin(["MARTINTXO"])]
#print(clubs_araba)

df_fide_players = get_fide_elos()
print_club_fide_elos([club_martintxo, club_sanvi], df_basque_players, df_fide_players)
