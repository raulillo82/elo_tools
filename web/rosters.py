'''
The players each club had last season. Those of the Álava championship are the
ones registered in the public team pages of info64. Those of the Basque league
are the ones who played, from Chess Results. Only the club and FIDE IDs are
kept: names and ratings come from the FIDE list. The files aren't part of the
repository.

Update the tournaments once a year, and run "python3 -m web.rosters <folder>".
'''
import html
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

#The two divisions of the Basque league, with their tournament in Chess Results
BASQUE_TOURNAMENTS = {"honor": 1331302, "primera": 1358593}
BASQUE_URL = "https://chess-results.com/tnr{}.aspx?lan=2&art=1&turdet=YES"
BASQUE_ROSTERS_FILE = "rosters_basque.json"
#Teams spelled in Chess Results differently from the club
BASQUE_TEAM_CLUBS = {"egidazu": "Eguidazu"}


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


def basque_teams(page):
    '''
    Returns the FIDE IDs of each team of a Chess Results page with the teams.
    Any federation is fine: only the ID matters
    '''
    teams, team = {}, None
    for row in re.findall(r"<tr.*?</tr>", page, re.S):
        title = re.search(r"\d+\.\s*(.+?)\s*\(Elo", html.unescape(re.sub(r"<[^>]+>", "", row)))
        if title and "colspan" in row:
            team = teams.setdefault(title.group(1).replace("\xa0", " ").strip(), [])
        elif team is not None:
            team.extend(int(fide_id) for fide_id in re.findall(r"ratings\.fide\.com/profile/(\d+)", row))
    return teams


def club_of_basque_team(team):
    '''
    Returns the club of a team of the Basque league, or None
    '''
    slug = normalize_name(team).replace(" ", "-")
    return BASQUE_TEAM_CLUBS.get(slug) or club_of_team(slug)


def fetch_basque_rosters():
    '''
    Returns a dictionary with the FIDE IDs of each club in each division
    '''
    rosters = {}
    for division, tournament in BASQUE_TOURNAMENTS.items():
        time.sleep(1)
        for team, ids in basque_teams(get_page(BASQUE_URL.format(tournament))).items():
            club = club_of_basque_team(team)
            if club:
                rosters.setdefault(club, {}).setdefault(division, []).extend(ids)
    return rosters


def load_rosters(folder):
    '''
    Returns the season and the rosters saved in the folder
    '''
    path = Path(folder) / ROSTERS_FILE
    if not path.exists():
        return None, {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    return saved["season"], saved["clubs"]


def load_basque_rosters(folder):
    '''
    Returns the Basque league players saved in the folder, by club and division
    '''
    path = Path(folder) / BASQUE_ROSTERS_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))["clubs"]


if __name__ == "__main__":
    clubs, unknown_teams = fetch_rosters()
    Path(sys.argv[1], ROSTERS_FILE).write_text(
        json.dumps({"season": SEASON, "clubs": clubs}), encoding="utf-8")
    print({club: len(ids) for club, ids in clubs.items()})
    if unknown_teams:
        print(f"Equipos sin club: {unknown_teams}")
    basque = fetch_basque_rosters()
    Path(sys.argv[1], BASQUE_ROSTERS_FILE).write_text(
        json.dumps({"season": SEASON, "clubs": basque}), encoding="utf-8")
    print(basque)
