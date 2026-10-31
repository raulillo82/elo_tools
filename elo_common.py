'''
Code shared by script_elo_fide.py and script_elo_basque.py: downloading the
FIDE list and finding players in it.
'''
import re
import unicodedata
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile

import pandas

FIDE_URL = "https://ratings.fide.com/download/standard_rating_list_xml.zip"

#Possible results of find_player
EXACT = "exact"          #The full name matches
POSSIBLE = "possible"    #Partial match: a human should double check it
NOT_FOUND = "not found"

#FIDE tells namesakes apart adding the birth year to the name, sometimes with
#a roman numeral: "Mata Martinez, Javier 1987", "Garcia, Manuel 1967 II"
NAMESAKE_SUFFIX = re.compile(r"\s+\d{4}(\s+[ivx]+)?$")

#Names in the Basque list are cut at this length: "Soto, Fernand" for Fernando
MAX_BASQUE_NAME = 30


def normalize_name(name):
    '''
    Returns a version of the name which is only useful to compare names:
    lowercase, no accents, no "ñ", and without the FIDE namesake suffix.
    '''
    name = name.lower().replace("mª", "maria").replace("fco.", "francisco")
    #Split letters from their accents, then drop the accents
    decomposed = unicodedata.normalize("NFKD", name)
    name = "".join(char for char in decomposed if not unicodedata.combining(char))
    name = re.sub(r"\s*,\s*", ", ", name)
    name = " ".join(name.split())
    return NAMESAKE_SUFFIX.sub("", name)


def add_missing_comma(name):
    '''
    Some names in the Basque list have no comma. Assumes the last word is the
    first name: "Perez Lopez Juan" becomes "Perez Lopez, Juan"
    '''
    words = name.split()
    if "," in name or len(words) < 2:
        return name
    return " ".join(words[:-1]) + ", " + words[-1]


def prepare_fide_list(df_fide):
    '''
    Returns the FIDE DF with the extra "key" column find_player searches on
    '''
    df_fide = df_fide.copy()
    #Years without decimals, and empty if unknown
    df_fide["birthday"] = df_fide["birthday"].astype("Int64")
    df_fide["key"] = df_fide["name"].map(normalize_name)
    return df_fide


def download_fide_list():
    '''
    Returns the latest FIDE list, ready to be used with find_player
    '''
    with urlopen(FIDE_URL, timeout=120) as resp:
        data = resp.read()
    with ZipFile(BytesIO(data)) as archive:
        #zipfile has only one compressed file:
        xml_file = archive.namelist()[0]
        #Get the date, it's a tuple. Time is not needed, just the date
        year, month, day = archive.getinfo(xml_file).date_time[:3]
        print(f"ELOs FIDE a fecha de {day}/{month}/{year}:")
        return prepare_fide_list(pandas.read_xml(archive.open(xml_file)))


def find_player(df_fide, name, birth_year=None):
    '''
    Looks for a player in the FIDE DF. Returns a tuple: one of EXACT, POSSIBLE
    or NOT_FOUND, and a DF with the matching rows.

    Ratings are never used to compare players, because the FIDE ELO and the
    Basque ELO are different lists with unrelated values.

    Partial matches only look at Spanish players, otherwise common names get
    dozens of matches from all over the world.
    '''
    key = normalize_name(name)

    #1. The full name. There can be several: namesakes share the same key
    exact = df_fide[df_fide["key"] == key]
    if birth_year is not None:
        same_year = exact[exact["birthday"] == birth_year]
        if not same_year.empty:
            exact = same_year
    if not exact.empty:
        return EXACT, exact

    #Partial matches need at least a surname and a first name
    if ", " not in key:
        return NOT_FOUND, df_fide.iloc[0:0]
    spanish = df_fide[df_fide["country"] == "ESP"]
    if birth_year is not None:
        spanish = spanish[spanish["birthday"].isna()
                          | (spanish["birthday"] == birth_year)]

    #2. Incomplete name, whole words only: "Garcia, Juan" finds
    #"Lopez Garcia, Juan Jose", but "Orio, Juan" doesn't find "Gregorio, Juan"
    pattern = r"\b" + re.escape(key)
    if len(name) < MAX_BASQUE_NAME:
        pattern += r"\b"
    partial = spanish[spanish["key"].str.contains(pattern, regex=True)]
    if not partial.empty:
        return POSSIBLE, partial

    #3. Different second surname, same first surname, first name and birth
    #year. The year is required: without it there are too many false positives
    if birth_year is not None:
        surnames, first_name = key.split(", ", 1)
        first_surname = surnames.split()[0]
        same_person = (spanish["birthday"] == birth_year).fillna(False) \
            & spanish["key"].str.startswith(first_surname + " ") \
            & spanish["key"].str.endswith(", " + first_name)
        if same_person.any():
            return POSSIBLE, spanish[same_person]

    return NOT_FOUND, df_fide.iloc[0:0]


def status_text(flag):
    '''
    Converts the FIDE flag to text. Flag is "i" if inactive, "w" if woman, "wi"
    if both, and empty otherwise
    '''
    return "inactivo" if isinstance(flag, str) and "i" in flag else "activo"
