'''
Downloads and reads the Basque ELO list. It has nothing to do with the FIDE
list: they're different lists with unrelated values.
'''
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import pandas
from dbfread import DBF
from pandas import DataFrame

from elo_common import add_missing_comma, normalize_name

BASE_FOLDER = Path(__file__).parent
ELOVASCO_FILE = BASE_FOLDER / "elovasco.zip"
ELOVASCO_URL = ("https://drive.google.com/uc?export=download"
                "&id=1pmXsi5xUikUWMo5CSpA0zYpwhTnMIYsc")
#The date is not in the file: update it by hand together with the file
ELOVASCO_DATE = "enero de 2022"
CLUBS_DBF = "clubs.dbf"
PLAYERS_DBF = "listaelo.dbf"


def birth_year(date):
    '''
    Returns the year of a Basque list date, or None if it's unknown
    '''
    return None if pandas.isna(date) else date.year


def read_dbf(path):
    '''
    Returns a DBF file as a DF
    '''
    return DataFrame(iter(DBF(path)))


def load_basque_lists():
    '''
    Returns a tuple with two DF: clubs and players. Players get three new
    columns: "name" (readable), "key" (to compare names) and "year" (of birth)
    '''
    #Download file unless it already exists
    if not ELOVASCO_FILE.exists():
        with urlopen(ELOVASCO_URL, timeout=120) as resp:
            ELOVASCO_FILE.write_bytes(resp.read())
    with ZipFile(ELOVASCO_FILE) as archive:
        #The zip also has a Windows program and more files which aren't needed
        dbf_files = [file for file in archive.namelist() if file.endswith(".dbf")]
        #Extract the databases, unless they're already extracted
        if not all((BASE_FOLDER / file).is_file() for file in dbf_files):
            archive.extractall(path=BASE_FOLDER, members=dbf_files)
    folder = (BASE_FOLDER / dbf_files[0]).parent
    df_clubs = read_dbf(folder / CLUBS_DBF)
    df_players = read_dbf(folder / PLAYERS_DBF)
    df_players["name"] = df_players["JUG"].map(lambda name: add_missing_comma(name.title()))
    df_players["key"] = df_players["name"].map(normalize_name)
    df_players["year"] = df_players["FECH_NAC"].map(birth_year)
    return df_clubs, df_players
