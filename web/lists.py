'''
The FIDE list used by the web: a read-only SQLite file for each month, in a
data folder. It has names, ratings and FIDE IDs on purpose: birth years and
sex are never copied, so the web can't show them by mistake.

Run "python3 -m web.lists <folder>" to download the list if there's a new one.
'''
import json
import os
import re
import sqlite3
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from elo_names import normalize_name

PLAYERS_URL = "https://ratings.fide.com/download/players_list_xml.zip"
INFO_FILE = "list_info.json"
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
MAX_RESULTS = 10
#Unrated players from other countries can't be found: they can be typed by hand
HOME_COUNTRY = "ESP"


def words_of(text):
    '''
    Returns the words to look for: without accents, case or commas
    '''
    return normalize_name(text).replace(",", " ").split()


def read_players(xml_file):
    '''
    Yields (fideid, name, rating, inactive, home) for each useful player
    '''
    for _, element in ET.iterparse(xml_file):
        if element.tag != "player":
            continue
        rating = int(element.findtext("rating") or 0) or None
        home = element.findtext("country") == HOME_COUNTRY
        if home or rating:
            yield (int(element.findtext("fideid")), element.findtext("name") or "", rating,
                   "i" in (element.findtext("flag") or ""), home)
        element.clear()


def build_list(xml_file, path):
    '''
    Writes the SQLite file of a FIDE XML. Replaces the old file only at the end
    '''
    temporary = path.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    database = sqlite3.connect(temporary)
    database.executescript("""
        CREATE TABLE players (fideid INTEGER PRIMARY KEY, name TEXT, rating INTEGER,
                              inactive INTEGER);
        CREATE TABLE words (word TEXT, fideid INTEGER);""")
    for fideid, name, rating, inactive, home in read_players(xml_file):
        database.execute("INSERT OR REPLACE INTO players VALUES (?, ?, ?, ?)",
                         (fideid, name, rating, inactive))
        #Only home players can be searched by name
        if home:
            database.executemany("INSERT INTO words VALUES (?, ?)",
                                 [(word, fideid) for word in set(words_of(name))])
    database.execute("CREATE INDEX words_word ON words (word)")
    database.commit()
    database.close()
    os.replace(temporary, path)


def update_list(folder):
    '''
    Downloads the FIDE list if it has changed. Returns the new file, or None
    '''
    folder = Path(folder)
    info_file = folder / INFO_FILE
    info = json.loads(info_file.read_text(encoding="utf-8")) if info_file.exists() else {}
    headers = {}
    if info.get("last_modified"):
        headers["If-Modified-Since"] = info["last_modified"]
    with tempfile.TemporaryFile(dir=folder) as data:
        try:
            with urlopen(Request(PLAYERS_URL, headers=headers), timeout=300) as resp:
                last_modified = resp.headers.get("Last-Modified")
                while chunk := resp.read(1024 * 1024):
                    data.write(chunk)
        except HTTPError as error:
            if error.code == 304:
                return None
            raise
        with ZipFile(data) as archive:
            name = archive.namelist()[0]
            year, month = archive.getinfo(name).date_time[:2]
            path = folder / f"players-{year:04}-{month:02}.sqlite"
            with archive.open(name) as xml_file:
                build_list(xml_file, path)
    info_file.write_text(json.dumps({"last_modified": last_modified}), encoding="utf-8")
    return path


class PlayerList:
    '''
    The list to use: the one chosen with ELO_LIST, for example "2027-01", or
    the newest one
    '''
    def __init__(self, folder, chosen=None):
        self.folder = Path(folder)
        self.chosen = chosen

    def path(self):
        if self.chosen:
            return self.folder / f"players-{self.chosen}.sqlite"
        files = sorted(self.folder.glob("players-*.sqlite"))
        return files[-1] if files else None

    def connect(self):
        path = self.path()
        if path is None or not path.exists():
            raise FileNotFoundError("No hay ninguna lista FIDE")
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def label(self):
        '''
        Returns what to tell users about the list
        '''
        path = self.path()
        if path is None or not path.exists():
            return {"text": "sin lista", "official": False}
        year, month = re.search(r"(\d{4})-(\d{2})", path.name).groups()
        return {"text": f"{MONTHS[int(month) - 1]} de {year}", "official": month == "01"}

    def get(self, fide_ids):
        '''
        Returns a dictionary with the players of those FIDE IDs which exist
        '''
        with self.connect() as database:
            found = {}
            for fide_id in fide_ids:
                row = database.execute("SELECT fideid, name, rating, inactive FROM players"
                                       " WHERE fideid = ?", (fide_id,)).fetchone()
                if row:
                    found[fide_id] = player_dict(row)
        return found

    def search(self, text):
        '''
        Returns the home players with all these whole words in their name, and
        True if there were more than MAX_RESULTS.
        '''
        words = words_of(text)
        if len(words) < 2 or any(len(word) < 2 for word in words):
            return [], False
        joins = " ".join(f"JOIN words w{number} ON w{number}.fideid = p.fideid"
                         f" AND w{number}.word = ?" for number in range(len(words)))
        query = (f"SELECT DISTINCT p.fideid, p.name, p.rating, p.inactive FROM players p {joins}"
                 " ORDER BY p.rating IS NULL, p.rating DESC, p.name LIMIT ?")
        with self.connect() as database:
            rows = database.execute(query, [*words, MAX_RESULTS + 1]).fetchall()
        return [player_dict(row) for row in rows[:MAX_RESULTS]], len(rows) > MAX_RESULTS


def player_dict(row):
    return {"id": row[0], "name": row[1], "rating": row[2], "inactive": bool(row[3])}


if __name__ == "__main__":
    new_file = update_list(sys.argv[1])
    print(f"Lista nueva: {new_file}" if new_file else "La lista no ha cambiado")
