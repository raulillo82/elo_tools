'''
The answers the program can give. Nothing here prints anything: the functions
return plain lists, dictionaries and text, so any interface can show them.
Today that's the console (elo.py).

A "player row" is a dictionary with these keys:
    name: the name of the player
    basque_elo: the Basque ELO, None if unknown
    basque_name: the name in the Basque list, None if unknown
    basque_confirmed: True if the name in the Basque list is the same one
    candidates: the FIDE players who may be this player, see candidate()
    confirmed: True if there's a single FIDE candidate and it's for sure them

The FIDE ELO and the Basque ELO are different lists with unrelated values,
so they're always shown side by side and never compared.
'''
import csv
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas
from pandas import DataFrame

from elo_basque import load_basque_lists
from elo_common import EXACT, find_player, load_fide_list, normalize_name, status_text
from elo_history import previous_ratings, update_history

MAX_SEARCH_RESULTS = 30
PLAYERS_FILE = Path(__file__).parent / "players.txt"

#Column names of the exported files
EXPORT_COLUMNS = ["Jugador", "ELO vasco", "ELO FIDE", "Variación", "Estado",
                  "Nacido", "ID FIDE", "A revisar"]
CHANGE_COLUMN = EXPORT_COLUMNS.index("Variación")


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
    previous_ratings: dict
    previous_date: str | None


def load_data():
    fide, fide_date, fide_warning = load_fide_list()
    update_history(fide, fide_date)
    clubs, basque = load_basque_lists()
    return EloData(fide, fide_date, fide_warning, clubs, basque, *previous_ratings())


def read_players_file(path=PLAYERS_FILE):
    '''
    Returns the players of the file: a name (text) or a FIDE ID (number) each.
    Whatever comes after a "#" is a comment. Returns None if there's no file.
    '''
    if not path.exists():
        return None
    players = []
    for line in path.read_text(encoding="utf-8").splitlines():
        player = line.split("#")[0].strip()
        if player:
            players.append(int(player) if player.isdigit() else player)
    return players


def candidate(data, row):
    '''
    Converts a row of the FIDE list to a dictionary. "change" is the difference
    with the previous list, None if the player wasn't in that list
    '''
    previous = data.previous_ratings.get(row.fideid)
    return {"fide_id": int(row.fideid),
            "name": row.name,
            "rating": int(row.rating),
            "change": None if previous is None else int(row.rating) - int(previous),
            "status": status_text(row.flag),
            "birth_year": None if pandas.isna(row.birthday) else int(row.birthday)}


def player_row(data, name, basque_elo, year=None, basque_name=None):
    '''
    Returns the player row of a player, looking for them in the FIDE list
    '''
    result, rows = find_player(data.fide, name, year)
    candidates = [candidate(data, row) for row in rows.itertuples()]
    return {"name": name,
            "basque_elo": basque_elo,
            "basque_name": basque_name,
            "basque_confirmed": basque_elo is not None,
            "candidates": candidates,
            "confirmed": result == EXACT and len(candidates) == 1}


def find_basque_player(data, name, year=None):
    '''
    Looks for a FIDE player in the Basque list. Returns a tuple: the row, None
    if not found, and True if the full name matches. If it doesn't, the first
    surname, first name and birth year must match, and it needs double checking
    '''
    key = normalize_name(name)
    same_name = data.basque[data.basque["key"] == key]
    if year is not None and len(same_name) > 1:
        same_name = same_name[same_name["year"] == year]
    #Namesakes could be someone else: only use a single match
    if len(same_name) == 1:
        return same_name.iloc[0], True
    if year is None or ", " not in key:
        return None, False
    surnames, first_name = key.split(", ", 1)
    keys = data.basque["key"]
    similar = data.basque[(data.basque["year"] == year)
                          & keys.str.startswith(surnames.split()[0] + " ")
                          & keys.str.endswith(", " + first_name)]
    return (similar.iloc[0], False) if len(similar) == 1 else (None, False)


def add_basque_data(data, row):
    '''
    Fills in the Basque list data of a player row which comes from FIDE
    '''
    year = row["candidates"][0]["birth_year"] if row["confirmed"] else None
    basque, confirmed = find_basque_player(data, row["name"], year)
    if basque is not None:
        row.update(basque_elo=int(basque["ELO"]), basque_name=basque["name"],
                   basque_confirmed=confirmed)
    return row


def fide_id_row(data, fide_id):
    '''
    Returns the player row of a FIDE ID
    '''
    rows = data.fide[data.fide["fideid"] == fide_id]
    candidates = [candidate(data, row) for row in rows.itertuples()]
    return {"name": candidates[0]["name"] if candidates else f"ID FIDE {fide_id}",
            "basque_elo": None,
            "basque_name": None,
            "basque_confirmed": False,
            "candidates": candidates,
            "confirmed": len(candidates) == 1}


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
                       None if pandas.isna(player.year) else int(player.year),
                       player.name)
            for player in players.itertuples()]
    return sorted(rows, key=lambda row: row["basque_elo"], reverse=True)


def my_players_table(data, players):
    '''
    Returns the player rows of a list of names and FIDE IDs, from the highest
    FIDE ELO to the lowest. Players without a confirmed FIDE ELO go last.
    '''
    rows = [add_basque_data(data, fide_id_row(data, player) if isinstance(player, int)
                            else player_row(data, player, None))
            for player in players]

    def fide_elo(row):
        return row["candidates"][0]["rating"] if row["confirmed"] else -1
    return sorted(rows, key=fide_elo, reverse=True)


def filter_rows(rows, show_inactive=True, show_without_fide=True):
    '''
    Returns the player rows to show. Without FIDE there's no status, so hiding
    inactive players doesn't hide them. If it's not sure who a player is, they
    are only hidden if all their FIDE candidates are inactive.
    '''
    def wanted(row):
        if not row["candidates"]:
            return show_without_fide
        return show_inactive or any(fide["status"] == "activo" for fide in row["candidates"])
    return [row for row in rows if wanted(row)]


def to_records(rows):
    '''
    Converts player rows to flat dictionaries, one per player, for files.
    FIDE data is left empty if there are several candidates
    '''
    records = []
    for row in rows:
        single = row["candidates"][0] if len(row["candidates"]) == 1 else {}
        doubtful = bool(row["candidates"]) and not row["confirmed"]
        if row["basque_elo"] is not None and not row["basque_confirmed"]:
            doubtful = True
        records.append(dict(zip(EXPORT_COLUMNS, (
            row["name"], row["basque_elo"], single.get("rating"), single.get("change"),
            single.get("status"), single.get("birth_year"), single.get("fide_id"),
            "sí" if doubtful else "no"))))
    return records


def to_csv(rows, previous_date=None):
    '''
    Returns the text of a CSV file with the player rows. It uses ";" because
    that's what Excel expects in Spain. The change column says since when
    '''
    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    headers = list(EXPORT_COLUMNS)
    if previous_date:
        headers[CHANGE_COLUMN] += f" desde {previous_date}"
    writer.writerow(headers)
    writer.writerows(record.values() for record in to_records(rows))
    return output.getvalue()


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
    return {"fide": [candidate(data, row) for row in fide.head(MAX_SEARCH_RESULTS).itertuples()],
            "basque": [{"name": row.name, "elo": int(row.ELO),
                        "club": club_names.get(row.CLUB, "")}
                       for row in basque.head(MAX_SEARCH_RESULTS).itertuples()],
            "too_many": max(len(fide), len(basque)) > MAX_SEARCH_RESULTS}
