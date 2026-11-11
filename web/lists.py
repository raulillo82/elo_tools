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
from contextlib import closing
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from elo_names import normalize_name
from web.i18n import DEFAULT_LANGUAGE, month_label

PLAYERS_URL = "https://ratings.fide.com/download/players_list_xml.zip"
ARCHIVE_URL = "https://ratings.fide.com/download/standard_{name}frl_xml.zip"
ARCHIVE_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
INFO_FILE = "list_info.json"
#Only the ratings of the January list that the current one is compared with
JANUARY_FILE = "january-{year:04}.sqlite"
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


def read_ratings(xml_file):
    '''
    Yields (fideid, rating) for each rated player
    '''
    for _, element in ET.iterparse(xml_file):
        if element.tag != "player":
            continue
        rating = int(element.findtext("rating") or 0)
        if rating:
            yield int(element.findtext("fideid")), rating
        element.clear()


def build_january(xml_file, path):
    '''
    Writes the ratings of a January list. Replaces the old file only at the end
    '''
    temporary = path.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    database = sqlite3.connect(temporary)
    database.execute("CREATE TABLE ratings (fideid INTEGER PRIMARY KEY, rating INTEGER)")
    database.executemany("INSERT OR REPLACE INTO ratings VALUES (?, ?)", read_ratings(xml_file))
    database.commit()
    database.close()
    os.replace(temporary, path)


def january_year(year, month):
    '''
    Returns the year of the January to compare a list with: the last one before
    it, so a January list is compared with the one of the year before
    '''
    return year - 1 if month == 1 else year


def archive_url(year, month):
    return ARCHIVE_URL.format(name=f"{ARCHIVE_MONTHS[month - 1]}{year % 100:02}")


def archive_exists(year, month):
    '''
    Returns True if FIDE has published the list of that month
    '''
    try:
        with urlopen(Request(archive_url(year, month), method="HEAD"), timeout=30):
            return True
    except (URLError, TimeoutError):
        return False


def list_month(today=None):
    '''
    Returns the (year, month) of the current FIDE list. The date of the file
    doesn't say it: the November list is dated on 31 October. FIDE archives each
    list under its month, and the new one appears before that month starts.
    '''
    today = today or date.today()
    following = (today.year + today.month // 12, today.month % 12 + 1)
    return following if archive_exists(*following) else (today.year, today.month)


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
            year, month = list_month()
            path = folder / f"players-{year:04}-{month:02}.sqlite"
            with archive.open(name) as xml_file:
                build_list(xml_file, path)
    info_file.write_text(json.dumps({"last_modified": last_modified}), encoding="utf-8")
    return path


def update_january(folder):
    '''
    Downloads the January list that the newest list is compared with, if it's
    not there yet, and removes the ones of other years. Returns the new file,
    or None
    '''
    folder = Path(folder)
    month = PlayerList(folder).month()
    if month is None:
        return None
    year = january_year(*month)
    path = folder / JANUARY_FILE.format(year=year)
    new_file = None
    if not path.exists():
        with tempfile.TemporaryFile(dir=folder) as data:
            with urlopen(archive_url(year, 1), timeout=300) as resp:
                while chunk := resp.read(1024 * 1024):
                    data.write(chunk)
            with ZipFile(data) as archive, archive.open(archive.namelist()[0]) as xml_file:
                build_january(xml_file, path)
        new_file = path
    for old in folder.glob("january-*.sqlite"):
        if old != path:
            old.unlink()
    return new_file


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

    def month(self):
        '''
        Returns the (year, month) of the list, or None if there's none
        '''
        path = self.path()
        if path is None or not path.exists():
            return None
        year, month = re.search(r"(\d{4})-(\d{2})", path.name).groups()
        return int(year), int(month)

    def connect(self):
        if self.month() is None:
            raise FileNotFoundError("No hay ninguna lista FIDE")
        return sqlite3.connect(f"file:{self.path()}?mode=ro", uri=True)

    def january_path(self):
        '''
        Returns the January list to compare with, or None if it's not there
        '''
        month = self.month()
        if month is None:
            return None
        path = self.folder / JANUARY_FILE.format(year=january_year(*month))
        return path if path.exists() else None

    def label(self, language=DEFAULT_LANGUAGE):
        '''
        Returns what to tell users about the list. "january" is the year of the
        January the changes are counted from, or None if there's no list to do it
        '''
        month = self.month()
        if month is None:
            return {"text": "-", "official": False, "january": None}
        return {"text": month_label(language, *month), "official": month[1] == 1,
                "january": january_year(*month) if self.january_path() else None}

    def januaries(self, fide_ids):
        '''
        Returns a dictionary with the January ratings of those FIDE IDs. Those
        without one aren't in it. None if there's no January list
        '''
        path = self.january_path()
        if path is None:
            return None
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as database:
            found = {}
            for fide_id in fide_ids:
                row = database.execute("SELECT rating FROM ratings WHERE fideid = ?",
                                       (fide_id,)).fetchone()
                if row:
                    found[fide_id] = row[0]
        return found

    def with_januaries(self, players):
        '''
        Adds "january" to each player, if there's a January list
        '''
        januaries = self.januaries([player["id"] for player in players])
        if januaries is not None:
            for player in players:
                player["january"] = januaries.get(player["id"])
        return players

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
        self.with_januaries(list(found.values()))
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
        return self.with_januaries([player_dict(row) for row in rows[:MAX_RESULTS]]), len(rows) > MAX_RESULTS


def player_dict(row):
    return {"id": row[0], "name": row[1], "rating": row[2], "inactive": bool(row[3])}


if __name__ == "__main__":
    new_file = update_list(sys.argv[1])
    print(f"Lista nueva: {new_file}" if new_file else "La lista no ha cambiado")
    #Also when the list hasn't changed: the January one may be missing
    january = update_january(sys.argv[1])
    if january:
        print(f"Lista de enero nueva: {january}")
