'''
The players each club registered last season, taken from the public team pages
of info64. Only the club and FIDE IDs are kept: names and ratings come from the
FIDE list. The file isn't part of the repository.

Update the tournaments once a year, and run "python3 -m web.rosters <folder>".
'''
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from elo_names import normalize_name
from web.accounts import CLUBS

SEASON = 2026
TOURNAMENTS = ["cto-de-alava-por-equipos-2026-preferente",
               "cto-de-alava-por-equipos-2026-primera",
               "cto-de-alava-por-equipos-2026-segunda-1"]
BASE_URL = "https://info64.org/team/"
ROSTERS_FILE = "rosters.json"
NOT_TEAMS = {"crosstable", "fidevar", "games", "listing", "schedule", "standings", "stats"}


def get_page(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def team_slugs(page, tournament):
    '''
    Returns the teams linked from the page of a tournament
    '''
    slugs = set(re.findall(rf'href="/team/{re.escape(tournament)}/([a-z0-9-]+)"', page))
    return sorted(slug for slug in slugs if slug not in NOT_TEAMS and not slug.isdigit())


def club_of_team(slug):
    '''
    Returns the club of a team, like "San Viator" for "san-viator-a", or None
    '''
    for club in CLUBS:
        if slug.startswith(normalize_name(club).replace(" ", "-")):
            return club
    return None


def roster_ids(page):
    '''
    Returns the FIDE IDs of the first table of a team page
    '''
    table = re.search(r"<table.*?</table>", page, re.S).group(0)
    rows = [re.findall(r"<t[dh].*?</t[dh]>", row, re.S) for row in re.findall(r"<tr.*?</tr>", table, re.S)]
    clean = [[re.sub(r"<[^>]+>|\s", "", cell) for cell in row] for row in rows]
    column = clean[0].index("FIDEID")
    return [int(row[column]) for row in clean[1:] if len(row) > column and row[column].isdigit()]


def fetch_rosters():
    '''
    Returns a dictionary with the FIDE IDs of each club, and the unknown teams
    '''
    rosters, unknown = {}, []
    for tournament in TOURNAMENTS:
        for slug in team_slugs(get_page(BASE_URL + tournament), tournament):
            time.sleep(1)
            club = club_of_team(slug)
            if club is None:
                unknown.append(slug)
                continue
            rosters.setdefault(club, set()).update(
                roster_ids(get_page(f"{BASE_URL}{tournament}/{slug}")))
    return {club: sorted(ids) for club, ids in rosters.items()}, unknown


def load_rosters(folder):
    '''
    Returns the season and the rosters saved in the folder
    '''
    path = Path(folder) / ROSTERS_FILE
    if not path.exists():
        return None, {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    return saved["season"], saved["clubs"]


if __name__ == "__main__":
    clubs, unknown_teams = fetch_rosters()
    Path(sys.argv[1], ROSTERS_FILE).write_text(
        json.dumps({"season": SEASON, "clubs": clubs}), encoding="utf-8")
    print({club: len(ids) for club, ids in clubs.items()})
    if unknown_teams:
        print(f"Equipos sin club: {unknown_teams}")
