'''
Code shared by script_elo_fide.py and script_elo_basque.py: downloading the
FIDE list and finding players in it.
'''
import json
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile

import pandas

FIDE_URL = "https://ratings.fide.com/download/standard_rating_list_xml.zip"

#Parsing the FIDE XML takes about 15 seconds, so keep the result on disk. The
#first file has the list, the second one its date
FIDE_CACHE = Path(__file__).parent / "fide_cache.parquet"
FIDE_CACHE_INFO = Path(__file__).parent / "fide_cache.json"

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
    name = name.lower().replace("mª", "maria")
    name = re.sub(r"\bfco\b\.?", "francisco", name)
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


def read_cache_info():
    '''
    Returns the information about the FIDE list on disk, None if there's no list
    '''
    if not (FIDE_CACHE.exists() and FIDE_CACHE_INFO.exists()):
        return None
    return json.loads(FIDE_CACHE_INFO.read_text(encoding="utf-8"))


def parse_fide_zip(data):
    '''
    Returns the date of a FIDE zipfile, and its list as a DF
    '''
    with ZipFile(BytesIO(data)) as archive:
        #zipfile has only one compressed file:
        xml_file = archive.namelist()[0]
        #Get the date, it's a tuple. Time is not needed, just the date
        year, month, day = archive.getinfo(xml_file).date_time[:3]
        return f"{day}/{month}/{year}", prepare_fide_list(pandas.read_xml(archive.open(xml_file)))


def load_fide_list():
    '''
    Returns the latest FIDE list, ready to be used with find_player, as a
    tuple: the DF, its date, and a warning (None if everything went fine).
    It's only downloaded if FIDE has a newer one than the list on disk.
    '''
    cache_info = read_cache_info()
    headers = {}
    if cache_info and cache_info["last_modified"]:
        #The server answers 304 if the list hasn't changed since that date
        headers["If-Modified-Since"] = cache_info["last_modified"]
    try:
        with urlopen(Request(FIDE_URL, headers=headers), timeout=120) as resp:
            data = resp.read()
            last_modified = resp.headers.get("Last-Modified")
    except (URLError, TimeoutError) as error:
        if cache_info is None:
            raise
        warning = None
        #urllib reports 304 as an error, but it's the expected answer
        if getattr(error, "code", None) != 304:
            warning = (f"no se ha podido consultar la lista FIDE ({error}), "
                       "se usa la del disco, que puede estar desactualizada")
        return pandas.read_parquet(FIDE_CACHE), cache_info["date"], warning

    date, df_fide = parse_fide_zip(data)
    df_fide.to_parquet(FIDE_CACHE)
    FIDE_CACHE_INFO.write_text(json.dumps({"date": date, "last_modified": last_modified}),
                               encoding="utf-8")
    return df_fide, date, None


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
