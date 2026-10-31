from os.path import exists, isfile, join
from urllib.request import urlopen
from zipfile import ZipFile

import pandas
from dbfread import DBF
from pandas import DataFrame

from elo_common import (EXACT, POSSIBLE, add_missing_comma, download_fide_list,
                        find_player, status_text)

ELOVASCO_FILE = "./elovasco.zip"
ELOVASCO_URL = ("https://drive.google.com/uc?export=download"
                "&id=1pmXsi5xUikUWMo5CSpA0zYpwhTnMIYsc")
CLUBS_DBF = "clubs.dbf"
PLAYERS_DBF = "listaelo.dbf"


def get_basque_elos():
    '''
    Returns a list with two panda DF
    First element: clubs
    Second element: players
    '''
    #Download file unless it already exists
    if exists(ELOVASCO_FILE):
        print("El fichero de ELOs vascos ya está en el disco, omitiendo descarga")
    else:
        print("Descargando fichero de ELOs vascos de gdrive")
        with urlopen(ELOVASCO_URL, timeout=120) as resp:
            data = resp.read()
        with open(ELOVASCO_FILE, "wb") as file:
            file.write(data)
    #Warn about file being dated in 2022
    print("Fichero de jugadores vascos de enero de 2022, NO se comprueba si hay alguno más reciente")
    with ZipFile(ELOVASCO_FILE) as archive:
        #The zip also has a Windows program and more files which aren't needed
        dbf_files = [file for file in archive.namelist() if file.endswith(".dbf")]
        #Check whether the zipfile is already unzipped:
        if all(isfile(file) for file in dbf_files):
            print("Fichero ya descomprimido, omitiendo descompresión")
        else:
            print("Descomprimiendo archivo")
            archive.extractall(members=dbf_files)
    folder = dbf_files[0].rsplit("/", 1)[0]
    df_clubs = DataFrame(iter(DBF(join(folder, CLUBS_DBF))))
    df_players = DataFrame(iter(DBF(join(folder, PLAYERS_DBF))))
    return [df_clubs, df_players]


def birth_year(date):
    '''
    Returns the year of a Basque list date, or None if it's unknown
    '''
    return None if pandas.isna(date) else date.year


def print_candidates(rows):
    '''
    Prints FIDE players which might be the Basque player. They're only a
    suggestion: the names are not the same
    '''
    for row in rows.itertuples():
        print(f"    ¿Es {row.name}? (nacido en {row.birthday}) - ELO FIDE: {row.rating}"
              f" - ESTADO: {status_text(row.flag)}")


def print_player(player, df_fide):
    '''
    Prints a player of the Basque list, together with their FIDE ELO, if they
    have one. They're different lists, so each ELO is shown as it is.
    '''
    name = add_missing_comma(player.JUG.title())
    result, rows = find_player(df_fide, name, birth_year(player.FECH_NAC))
    if result == EXACT:
        for row in rows.itertuples():
            print(f"{name} - ELO FIDE: {row.rating}"
                  f" - ESTADO: {status_text(row.flag)}"
                  f" - ELO VASCO: {player.ELO}")
    else:
        print(name)
        if result == POSSIBLE:
            print_candidates(rows)


def print_club_fide_elos(clubs, df_basque_players, df_fide):
    '''
    Prints the players of Basque clubs, together with their FIDE ELO, if they
    have one
    '''
    for club in clubs.itertuples():
        #First print which club it is
        print(club.CLUB)
        #Iterate through each of the players of the club
        club_players = df_basque_players[df_basque_players.CLUB == club.CLAVE]
        for player in club_players.itertuples():
            print_player(player, df_fide)
        print()


def main():
    df_basque_clubs, df_basque_players = get_basque_elos()
    #Two of the clubs of Araba as example
    #Avoiding to have thousands of lines in the output during testing
    clubs = df_basque_clubs[(df_basque_clubs.PROV == "A")
                            & df_basque_clubs.CLUB.isin(["MARTINTXO", "SAN VIATOR"])]
    print_club_fide_elos(clubs, df_basque_players, download_fide_list())


if __name__ == "__main__":
    main()
