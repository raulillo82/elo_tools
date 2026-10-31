'''
The answers the program can give. Nothing here prints anything: the functions
return plain lists and dictionaries, so any interface can show them. Today
that's the console (elo.py).

A "player row" is a dictionary with these keys:
    name: the name of the player
    basque_elo: the Basque ELO, None if unknown
    candidates: the FIDE players who may be this player, see candidate()
    confirmed: True if there's a single candidate and the full name matches

The FIDE ELO and the Basque ELO are different lists with unrelated values,
so they're always shown side by side and never compared.
'''
import re
from dataclasses import dataclass

import pandas
from pandas import DataFrame

from elo_basque import load_basque_lists
from elo_common import EXACT, find_player, load_fide_list, normalize_name, status_text

MAX_SEARCH_RESULTS = 30


@dataclass
class EloData:
    '''
    Everything which has to be loaded just once
    '''
    fide: DataFrame
    fide_date: str
    fide_warning: str | None
    clubs: DataFrame
    basque: DataFrame


def load_data():
    fide, fide_date, fide_warning = load_fide_list()
    clubs, basque = load_basque_lists()
    return EloData(fide, fide_date, fide_warning, clubs, basque)


def candidate(row):
    '''
    Converts a row of the FIDE list to a dictionary
    '''
    return {"fide_id": int(row.fideid),
            "name": row.name,
            "rating": int(row.rating),
            "status": status_text(row.flag),
            "birth_year": None if pandas.isna(row.birthday) else int(row.birthday)}


def player_row(data, name, basque_elo, year=None):
    '''
    Returns the player row of a player, looking for them in the FIDE list
    '''
    result, rows = find_player(data.fide, name, year)
    candidates = [candidate(row) for row in rows.itertuples()]
    return {"name": name,
            "basque_elo": basque_elo,
            "candidates": candidates,
            "confirmed": result == EXACT and len(candidates) == 1}


def find_clubs(data, text):
    '''
    Returns the clubs with that text in their name, as dictionaries
    '''
    key = normalize_name(text)
    names = data.clubs["CLUB"].map(normalize_name)
    clubs = data.clubs[names.str.contains(key, regex=False)]
    return [{"id": club.CLAVE, "name": club.CLUB, "town": club.LOC}
            for club in clubs.itertuples()]


def club_table(data, club_id):
    '''
    Returns the player rows of a club, from the highest Basque ELO to the lowest
    '''
    players = data.basque[data.basque["CLUB"] == club_id]
    rows = [player_row(data, player.name, int(player.ELO),
                       None if pandas.isna(player.year) else int(player.year))
            for player in players.itertuples()]
    return sorted(rows, key=lambda row: row["basque_elo"], reverse=True)


def my_players_table(data, names):
    '''
    Returns the player rows of a list of names, from the highest FIDE ELO to
    the lowest. Players without a confirmed FIDE ELO go last.
    '''
    rows = []
    for name in names:
        #A Basque namesake could be someone else: only use a single match
        basque = data.basque[data.basque["key"] == normalize_name(name)]
        basque_elo = int(basque["ELO"].iloc[0]) if len(basque) == 1 else None
        rows.append(player_row(data, name, basque_elo))

    def fide_elo(row):
        return row["candidates"][0]["rating"] if row["confirmed"] else -1
    return sorted(rows, key=fide_elo, reverse=True)


def has_all_words(keys, text):
    '''
    Returns which keys have all the words of the text, in any order. Each word
    can be incomplete, but only by its end: "mar" finds "martinez" not "omar"
    '''
    found = pandas.Series(True, index=keys.index)
    for word in normalize_name(text).replace(",", " ").split():
        found &= keys.str.contains(r"\b" + re.escape(word), regex=True)
    return found


def search_players(data, text):
    '''
    Looks for a text in both lists. A FIDE ID finds that player, whatever their
    country. Any other text looks at the names of Spanish FIDE players. Returns
    a dictionary with "fide" and "basque" results, and "too_many", which is
    True if some results were left out.
    '''
    if not text.strip():
        fide, basque = data.fide.iloc[0:0], data.basque.iloc[0:0]
    elif text.strip().isdigit():
        fide = data.fide[data.fide["fideid"] == int(text)]
        basque = data.basque.iloc[0:0]
    else:
        spanish = data.fide[data.fide["country"] == "ESP"]
        fide = spanish[has_all_words(spanish["key"], text)]
        basque = data.basque[has_all_words(data.basque["key"], text)]
    club_names = dict(zip(data.clubs["CLAVE"], data.clubs["CLUB"]))
    return {"fide": [candidate(row) for row in fide.head(MAX_SEARCH_RESULTS).itertuples()],
            "basque": [{"name": row.name, "elo": int(row.ELO),
                        "club": club_names.get(row.CLUB, "")}
                       for row in basque.head(MAX_SEARCH_RESULTS).itertuples()],
            "too_many": max(len(fide), len(basque)) > MAX_SEARCH_RESULTS}
