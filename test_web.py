'''
Run with: python3 -m unittest
All the names are made up.
'''
import io
import json
import re
import sqlite3
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from zipfile import ZipFile, ZipInfo

from web import i18n, lists, rosters
from web.accounts import AccountError, Accounts
from web.app import create_app, limiter
from web.lists import PlayerList, build_list
from web.rules import check_order
from web.staging import ENTRY_SECONDS, entry_token, read_entry

PLAYERS_XML = b"""<playerslist>
<player><fideid>1</fideid><name>Soto Rey, Ana</name><country>ESP</country><sex>F</sex>
<rating>1800</rating><birthday>2012</birthday><flag>w</flag></player>
<player><fideid>2</fideid><name>Roble Mar, Luis 1987</name><country>ESP</country><sex>M</sex>
<rating>1650</rating><birthday>1987</birthday><flag>i</flag></player>
<player><fideid>3</fideid><name>Iba\xc3\xb1ez Soto, I\xc3\xb1aki</name><country>ESP</country><sex>M</sex>
<rating>0</rating><birthday>2015</birthday><flag></flag></player>
<player><fideid>4</fideid><name>Soto, Hans</name><country>GER</country><sex>M</sex>
<rating>2100</rating><birthday>1960</birthday><flag></flag></player>
<player><fideid>5</fideid><name>Soto, Fritz</name><country>GER</country><sex>M</sex>
<rating>0</rating><birthday>1960</birthday><flag></flag></player>
</playerslist>"""
#January has only rated players, as FIDE's archive. 1 rose, 2 fell, 4 kept it
#and 3 has no rating now. 6 isn't in the list
JANUARY_XML = b"""<playerslist>
<player><fideid>1</fideid><name>Soto Rey, Ana</name><country>ESP</country><rating>1755</rating></player>
<player><fideid>2</fideid><name>Roble Mar, Luis</name><country>ESP</country><rating>1680</rating></player>
<player><fideid>3</fideid><name>Iba\xc3\xb1ez Soto, I\xc3\xb1aki</name><country>ESP</country><rating>1400</rating></player>
<player><fideid>4</fideid><name>Soto, Hans</name><country>GER</country><rating>2100</rating></player>
<player><fideid>6</fideid><name>Mar, Eva</name><country>ESP</country><rating>0</rating></player>
</playerslist>"""
PASSWORD = "contrasena-larga"


def write_list(folder, name="players-2026-10.sqlite"):
    build_list(io.BytesIO(PLAYERS_XML), Path(folder, name))


def write_january(folder, year=2026):
    lists.build_january(io.BytesIO(JANUARY_XML), Path(folder, f"january-{year}.sqlite"))


def fake_download(content):
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        info = ZipInfo("list.xml", date_time=(2026, 10, 30, 0, 0, 0))
        archive.writestr(info, content)
    response = mock.MagicMock()
    response.__enter__.return_value = io.BytesIO(data.getvalue())
    response.__enter__.return_value.headers = {"Last-Modified": "date1"}
    return response


TEAM_PAGE = """<table><tr><th>Brd.</th><th>Name</th><th>FIDE ID</th></tr>
<tr><td>1</td><td><a href="/x">Soto, Ana</a></td><td>
  123</td></tr><tr><td>2</td><td>Rey, Eva</td><td>456</td></tr></table>
<table><tr><th>Rd.</th></tr><tr><td>1</td></tr></table>"""


class TextsTest(unittest.TestCase):
    def test_every_text_in_the_web_exists(self):
        web = Path(__file__).parent / "web"
        used = set()
        for path in (web / "templates").glob("*.html"):
            used |= set(re.findall(r"""\bt\('(\w+)'""", path.read_text(encoding="utf-8")))
        used |= set(re.findall(r"""\bt\("(\w+)"\s*[,)]""",
                               (web / "static" / "app.js").read_text(encoding="utf-8")))
        self.assertEqual(used - set(i18n.TEXTS) - set(i18n.BROWSER_TEXTS), set())

    def test_months(self):
        self.assertEqual(i18n.month_label("eu", 2026, 10), "2026ko urria")
        self.assertEqual(i18n.month_label("es", 2026, 10), "octubre de 2026")


class RostersTest(unittest.TestCase):
    def test_basque_teams_any_federation_and_first_team(self):
        page = ('<table><tr class="CRg1b"><td colspan="18">&nbsp;&nbsp;1. Rey (Elo medio:2000)</td></tr>'
                '<tr><th>Nombre</th></tr>'
                '<tr class="CRng2 FRA"><td><a href="http://ratings.fide.com/profile/633">633</a></td></tr>'
                '<tr class="CRg1b"><td colspan="18">&nbsp;&nbsp;2. Dama B (Elo medio:1900)</td></tr>'
                '<tr><td><a href="http://ratings.fide.com/profile/22">22</a></td></tr></table>')
        self.assertEqual(rosters.basque_teams(page), {"Rey": [633], "Dama B": [22]})

    def test_club_of_basque_team(self):
        self.assertEqual(rosters.club_of_basque_team("Egidazu"), "Eguidazu")
        self.assertEqual(rosters.club_of_basque_team("Martintxo"), "Martintxo")
        self.assertIsNone(rosters.club_of_basque_team("Zuri Baltza"))

    def test_both_languages_use_the_same_values(self):
        for key, (basque, spanish) in {**i18n.TEXTS, **i18n.BROWSER_TEXTS}.items():
            self.assertEqual(sorted(re.findall(r"\{\w+\}", basque)),
                             sorted(re.findall(r"\{\w+\}", spanish)), key)

    def test_nothing_is_left_empty(self):
        for key, pair in {**i18n.TEXTS, **i18n.BROWSER_TEXTS}.items():
            self.assertEqual(len(pair), 2, key)
            self.assertTrue(all(pair), key)

    def test_ids_of_the_team(self):
        self.assertEqual(rosters.roster_ids(TEAM_PAGE), [123, 456])

    def test_club_of_team(self):
        self.assertEqual(rosters.club_of_team("san-viator-a"), "San Viator")
        self.assertEqual(rosters.club_of_team("martintxo-gazte"), "Martintxo")
        self.assertEqual(rosters.club_of_team("laudio"), "Laudio")
        self.assertIsNone(rosters.club_of_team("otro-a"))

    def test_team_slugs_leave_out_other_links(self):
        page = """<a href="/team/t/rey-a"></a><a href="/team/t/standings"></a>
                  <a href="/team/t/3"></a><a href="/team/t2/otro"></a>"""
        self.assertEqual(rosters.team_slugs(page, "t"), ["rey-a"])

    def test_no_file(self):
        self.assertEqual(rosters.load_rosters("/no/such/folder"), (None, {}))


class CheckOrderTest(unittest.TestCase):
    def test_sorted_order_is_right(self):
        self.assertEqual(check_order([1800, 1760, 1720]), [])

    def test_exactly_the_margin_is_right(self):
        self.assertEqual(check_order([1750, 1800]), [])

    def test_one_point_over_the_margin(self):
        errors = check_order([1749, 1800])
        self.assertEqual([(e["upper"], e["lower"], e["difference"]) for e in errors], [(1, 2, 51)])

    def test_jumping_several_players_inside_the_margin(self):
        self.assertEqual(check_order([1760, 1800, 1790, 1770]), [])

    def test_the_margin_counts_against_everyone_overtaken(self):
        errors = check_order([1720, 1800, 1760])
        self.assertEqual([(e["upper"], e["lower"]) for e in errors], [(1, 2)])

    def test_real_case_with_a_high_rating_on_the_last_board(self):
        self.assertEqual(len(check_order([1583, 1591, 1554, 1514, 1511, 1451, 1430, 1667])), 7)

    def test_players_without_elo_go_last(self):
        self.assertEqual(check_order([1500, None, None]), [])

    def test_player_without_elo_above_one_with_elo(self):
        errors = check_order([None, 1000])
        self.assertEqual([(e["difference"], e["lower_rating"]) for e in errors], [(None, 1000)])

    def test_other_margin(self):
        self.assertEqual(check_order([1700, 1800], margin=100), [])


class PlayerListTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        write_list(self.folder)
        self.players = PlayerList(self.folder)

    def names(self, text):
        return [player["name"] for player in self.players.search(text)[0]]

    def test_needs_two_whole_words(self):
        self.assertEqual(self.names("Soto"), [])
        self.assertEqual(self.names("Sot Ana"), [])
        self.assertEqual(self.names("a soto"), [])

    def test_words_in_any_order_ignoring_accents(self):
        self.assertEqual(self.names("ana SOTO"), ["Soto Rey, Ana"])
        self.assertEqual(self.names("iñaki ibañez"), ["Ibañez Soto, Iñaki"])
        self.assertEqual(self.names("inaki ibanez"), ["Ibañez Soto, Iñaki"])

    def test_minors_can_be_found(self):
        self.assertEqual(self.names("soto rey"), ["Soto Rey, Ana"])

    def test_namesake_suffix_isnt_needed(self):
        self.assertEqual(self.names("roble luis"), ["Roble Mar, Luis 1987"])

    def test_other_countries_cant_be_searched_by_name(self):
        self.assertEqual(self.names("soto hans"), [])

    def test_rated_foreigners_can_be_found_by_id(self):
        self.assertEqual(self.players.get([4])[4]["rating"], 2100)

    def test_unrated_foreigners_are_left_out(self):
        self.assertEqual(self.players.get([5]), {})

    def test_no_rating_is_none(self):
        self.assertIsNone(self.players.get([3])[3]["rating"])

    def test_inactive_flag(self):
        self.assertTrue(self.players.get([2])[2]["inactive"])
        self.assertFalse(self.players.get([1])[1]["inactive"])

    def test_no_birth_year_or_sex_in_the_file(self):
        database = sqlite3.connect(next(Path(self.folder).glob("*.sqlite")))
        columns = [row[1] for row in database.execute("PRAGMA table_info(players)")]
        database.close()
        self.assertEqual(columns, ["fideid", "name", "rating", "inactive"])

    def test_max_results(self):
        words = [f"<player><fideid>{n}</fideid><name>Rey Soto, Eva {n}</name><country>ESP</country>"
                 f"<rating>0</rating></player>" for n in range(lists.MAX_RESULTS + 2)]
        build_list(io.BytesIO(f"<a>{''.join(words)}</a>".encode()),
                   Path(self.folder, "players-2026-11.sqlite"))
        results, more = self.players.search("rey eva")
        self.assertEqual((len(results), more), (lists.MAX_RESULTS, True))

    def test_newest_list_and_label(self):
        write_list(self.folder, "players-2027-01.sqlite")
        self.assertEqual(self.players.label("es"),
                         {"text": "enero de 2027", "official": True, "january": None})
        self.assertEqual(self.players.label(),
                         {"text": "2027ko urtarrila", "official": True, "january": None})

    def test_chosen_list(self):
        write_list(self.folder, "players-2027-01.sqlite")
        chosen = PlayerList(self.folder, "2026-10")
        self.assertEqual(chosen.label("es"),
                         {"text": "octubre de 2026", "official": False, "january": None})


class JanuaryTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        write_list(self.folder)
        write_january(self.folder)
        self.players = PlayerList(self.folder)

    def test_the_january_before_the_list(self):
        self.assertEqual(lists.january_year(2026, 11), 2026)
        self.assertEqual(lists.january_year(2026, 2), 2026)
        #A January list is compared with the one of the year before
        self.assertEqual(lists.january_year(2027, 1), 2026)

    def test_ratings_of_january(self):
        found = self.players.get([1, 2, 3, 4])
        self.assertEqual({fide_id: player["january"] for fide_id, player in found.items()},
                         {1: 1755, 2: 1680, 3: 1400, 4: 2100})

    def test_rated_now_but_not_in_january(self):
        build_list(io.BytesIO(PLAYERS_XML.replace(b"<fideid>4</fideid>", b"<fideid>6</fideid>")),
                   Path(self.folder, "players-2026-10.sqlite"))
        self.assertIsNone(self.players.get([6])[6]["january"])

    def test_search_has_january_too(self):
        self.assertEqual(self.players.search("ana soto")[0][0]["january"], 1755)

    def test_only_ids_and_ratings_in_the_file(self):
        database = sqlite3.connect(Path(self.folder, "january-2026.sqlite"))
        columns = [row[1] for row in database.execute("PRAGMA table_info(ratings)")]
        count = database.execute("SELECT COUNT(*) FROM ratings").fetchone()[0]
        database.close()
        self.assertEqual((columns, count), (["fideid", "rating"], 4))

    def test_label_says_which_january(self):
        self.assertEqual(self.players.label("es")["january"], 2026)
        write_list(self.folder, "players-2027-01.sqlite")
        self.assertEqual(self.players.label("es")["january"], 2026)

    def test_without_the_right_january_nothing_changes(self):
        write_list(self.folder, "players-2027-02.sqlite")
        self.assertIsNone(self.players.label("es")["january"])
        self.assertNotIn("january", self.players.get([1])[1])
        self.assertNotIn("january", self.players.search("ana soto")[0][0])

    def update(self):
        with mock.patch.object(lists, "urlopen", return_value=fake_download(JANUARY_XML)) as url:
            path = lists.update_january(self.folder)
        return path, url

    def test_downloads_the_january_it_needs_and_removes_the_old_one(self):
        write_list(self.folder, "players-2027-02.sqlite")
        path, url = self.update()
        self.assertEqual(path.name, "january-2027.sqlite")
        self.assertIn("standard_jan27frl_xml.zip", url.call_args.args[0])
        self.assertEqual(sorted(p.name for p in Path(self.folder).glob("january-*")),
                         ["january-2027.sqlite"])
        self.assertEqual(self.players.get([2])[2]["january"], 1680)

    def test_doesnt_download_it_twice(self):
        path, url = self.update()
        self.assertIsNone(path)
        url.assert_not_called()

    def test_nothing_without_a_list(self):
        for path in Path(self.folder).glob("*.sqlite"):
            path.unlink()
        path, url = self.update()
        self.assertIsNone(path)
        url.assert_not_called()


class UpdateListTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def fake_zip(self):
        data = io.BytesIO()
        with ZipFile(data, "w") as archive:
            info = ZipInfo("list.xml", date_time=(2026, 10, 30, 0, 0, 0))
            archive.writestr(info, PLAYERS_XML)
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(data.getvalue())
        response.__enter__.return_value.headers = {"Last-Modified": "date1"}
        return response

    def test_new_list_is_named_after_its_month(self):
        with mock.patch.object(lists, "urlopen", return_value=self.fake_zip()), \
                mock.patch.object(lists, "list_month", return_value=(2026, 11)):
            path = lists.update_list(self.folder)
        self.assertEqual(path.name, "players-2026-11.sqlite")

    def test_unchanged_list(self):
        not_modified = HTTPError("url", 304, "Not Modified", {}, None)
        with mock.patch.object(lists, "urlopen", side_effect=[self.fake_zip(), not_modified]) as url, \
                mock.patch.object(lists, "list_month", return_value=(2026, 11)):
            lists.update_list(self.folder)
            self.assertIsNone(lists.update_list(self.folder))
        self.assertEqual(url.call_args.args[0].get_header("If-modified-since"), "date1")


class ListMonthTest(unittest.TestCase):
    def month(self, today, published):
        def exists(year, month):
            return (year, month) in published
        with mock.patch.object(lists, "archive_exists", side_effect=exists):
            return lists.list_month(today)

    def test_next_list_published_before_the_month_starts(self):
        self.assertEqual(self.month(date(2026, 10, 31), {(2026, 11)}), (2026, 11))

    def test_inside_the_month(self):
        self.assertEqual(self.month(date(2026, 11, 15), {(2026, 11)}), (2026, 11))

    def test_new_year(self):
        self.assertEqual(self.month(date(2026, 12, 31), {(2027, 1)}), (2027, 1))
        self.assertEqual(self.month(date(2026, 12, 15), set()), (2026, 12))

    def test_archive_url(self):
        with mock.patch.object(lists, "urlopen", return_value=mock.MagicMock()) as url:
            self.assertTrue(lists.archive_exists(2027, 1))
        self.assertIn("standard_jan27frl_xml.zip", url.call_args.args[0].full_url)
        self.assertEqual(url.call_args.args[0].get_method(), "HEAD")

    def test_missing_archive(self):
        error = HTTPError("url", 404, "Not Found", {}, None)
        with mock.patch.object(lists, "urlopen", side_effect=error):
            self.assertFalse(lists.archive_exists(2027, 1))


class DeployTest(unittest.TestCase):
    def test_list_update_doesnt_start_a_second_container(self):
        #With :Z, a second container takes the SELinux label of the data folder
        #and the web can't open its accounts any more
        unit = Path(__file__).parent / "web" / "deploy" / "elo-list-update.service"
        text = unit.read_text(encoding="utf-8")
        self.assertIn("podman exec elo-web", text)
        self.assertNotIn("podman run", text)


class AccountsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.accounts = Accounts(Path(folder.name, "accounts.db"))

    def join(self, club="Laudio"):
        token = self.accounts.create_invite("Ane", club)
        return self.accounts.accept_invite(token, PASSWORD)

    def test_invitation_works_once(self):
        token = self.accounts.create_invite("Ane", "Laudio")
        self.accounts.accept_invite(token, PASSWORD)
        with self.assertRaises(AccountError):
            self.accounts.accept_invite(token, PASSWORD)

    def test_expired_invitation(self):
        token = self.accounts.create_invite("Ane", "Laudio")
        with mock.patch("web.accounts.time.time", return_value=time.time() + 73 * 3600):
            self.assertIsNone(self.accounts.find_invite(token))

    def test_short_password(self):
        token = self.accounts.create_invite("Ane", "Laudio")
        with self.assertRaises(AccountError):
            self.accounts.accept_invite(token, "corta")

    def test_a_club_has_one_person(self):
        self.accounts.create_invite("Ane", "Laudio")
        with self.assertRaises(AccountError):
            self.accounts.create_invite("Jon", "Laudio")
        self.assertNotIn("Laudio", self.accounts.free_clubs())

    def test_unknown_club(self):
        with self.assertRaises(AccountError):
            self.accounts.create_invite("Ane", "Otro")

    def test_login_needs_device_and_password(self):
        user, device = self.join()
        self.assertEqual(self.accounts.login(device, PASSWORD)["id"], user["id"])
        self.assertIsNone(self.accounts.login(device, "otra-contrasena"))
        self.assertIsNone(self.accounts.login("otro-dispositivo", PASSWORD))
        self.assertIsNone(self.accounts.login(None, PASSWORD))

    def test_second_device_needs_the_password(self):
        user, _ = self.join()
        token = self.accounts.create_invite(user_id=user["id"])
        with self.assertRaises(AccountError):
            self.accounts.accept_invite(token, "contrasena-mala")
        self.accounts.accept_invite(token, PASSWORD)

    def test_third_device_is_refused(self):
        user, _ = self.join()
        self.accounts.accept_invite(self.accounts.create_invite(user_id=user["id"]), PASSWORD)
        with self.assertRaises(AccountError):
            self.accounts.accept_invite(self.accounts.create_invite(user_id=user["id"]), PASSWORD)

    def test_tokens_are_kept_hashed(self):
        token = self.accounts.create_invite("Ane", "Laudio")
        user, device = self.accounts.accept_invite(token, PASSWORD)
        dump = "\n".join(self.accounts.connect().iterdump())
        self.assertNotIn(device, dump)
        self.assertNotIn(PASSWORD, dump)

    def test_removed_device_stops_working(self):
        user, device = self.join()
        self.accounts.remove_devices(user["id"])
        self.assertIsNone(self.accounts.user_of_device(device))

    def test_deleting_frees_the_club(self):
        user, _ = self.join()
        self.accounts.delete_user(user["id"])
        self.assertIn("Laudio", self.accounts.free_clubs())

    def test_admin_cant_be_deleted(self):
        token = self.accounts.create_invite("Ane", "Laudio", is_admin=True)
        user, _ = self.accounts.accept_invite(token, PASSWORD)
        with self.assertRaises(AccountError):
            self.accounts.delete_user(user["id"])


class WebTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        write_list(folder.name)
        self.accounts = Accounts(Path(folder.name, "accounts.db"))
        self.app = create_app({"ACCOUNTS": self.accounts, "PLAYERS": PlayerList(folder.name),
                               "SESSION_COOKIE_SECURE": False, "SESSION_COOKIE_PATH": "/",
                               "MARGIN": 50, "RATELIMIT_ENABLED": False,
                               "DATA_FOLDER": folder.name})
        Path(folder.name, rosters.ROSTERS_FILE).write_text(json.dumps(
            {"season": 2026, "clubs": {"Laudio": [2, 1, 999], "Martintxo": [3]}}), encoding="utf-8")
        self.folder = folder.name
        limiter.enabled = False
        self.addCleanup(setattr, limiter, "enabled", True)
        self.client = self.app.test_client()

    def csrf(self, client=None, path="/login"):
        text = (client or self.client).get(path).get_data(as_text=True)
        return re.search(r'name="csrf" content="([^"]+)"', text).group(1)

    def join(self, is_admin=False, club="Laudio", client=None):
        client = client or self.client
        token = self.accounts.create_invite("Ane", club, is_admin)
        path = f"/invite/{token}"
        response = client.post(path, data={"password": PASSWORD, "csrf": self.csrf(client, path)})
        self.assertEqual(response.status_code, 302)
        return client

    def api(self, path, body, client=None):
        client = client or self.client
        return client.post(f"/api/{path}", json=body, headers={"X-CSRF": self.csrf(client, "/")})

    def test_nothing_without_an_account(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(self.client.post("/api/search", json={"text": "soto ana"},
                                          headers={"X-CSRF": self.csrf()}).status_code, 401)

    def test_post_needs_csrf(self):
        self.join()
        self.assertEqual(self.client.post("/api/search", json={"text": "ana soto"}).status_code, 403)

    def test_login_from_an_unknown_device_is_refused(self):
        self.join()
        other = self.app.test_client()
        response = other.post("/login", data={"password": PASSWORD, "csrf": self.csrf(other)})
        self.assertIn("Pasahitz okerra", response.get_data(as_text=True))
        self.assertEqual(other.get("/").status_code, 302)

    def test_login_from_the_device(self):
        self.join()
        self.client.post("/logout", data={"csrf": self.csrf(path="/")})
        self.assertEqual(self.client.get("/").status_code, 302)
        self.client.post("/login", data={"password": PASSWORD, "csrf": self.csrf()})
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_removing_the_device_closes_the_session(self):
        self.join()
        self.accounts.remove_devices(self.accounts.list_users()[0]["id"])
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_search_shows_no_birth_year_or_sex(self):
        self.join()
        answer = self.api("search", {"text": "ana soto"}).get_json()
        self.assertEqual(set(answer["results"][0]), {"id", "name", "rating", "inactive"})

    def test_check_right_and_wrong(self):
        self.join()
        self.assertEqual(self.api("check", {"entries": [1, 2, None]}).get_json()["errors"], [])
        errors = self.api("check", {"entries": [2, 1]}).get_json()["errors"]
        self.assertEqual(errors[0]["difference"], 150)
        errors = self.api("check", {"entries": [None, 2]}).get_json()["errors"]
        self.assertIsNone(errors[0]["difference"])

    def test_the_server_keeps_no_orders(self):
        self.join()
        before = "\n".join(self.accounts.connect().iterdump())
        self.api("check", {"entries": [1, 2]})
        self.assertEqual("\n".join(self.accounts.connect().iterdump()), before)

    def test_check_gives_the_january_ratings(self):
        self.join()
        self.assertEqual(self.api("check", {"entries": [1, None]}).get_json()["januaries"],
                         [None, None])
        write_january(self.folder)
        answer = self.api("check", {"entries": [1, None, 3]}).get_json()
        self.assertEqual(answer["januaries"], [1755, None, 1400])
        self.assertEqual(answer["list"]["january"], 2026)

    def test_the_notice_says_since_when(self):
        self.join()
        self.set_language("es", "/")
        self.assertNotIn("el cambio desde", self.client.get("/").get_data(as_text=True))
        write_january(self.folder)
        text = self.client.get("/").get_data(as_text=True)
        self.assertIn("el cambio desde enero de 2026", text)
        self.assertIn('data-january="2026"', text)

    def test_lookup(self):
        self.join()
        answer = self.api("lookup", {"ids": [1, 999]}).get_json()
        self.assertEqual((answer["players"][0]["id"], answer["missing"]), (1, [999]))

    def test_roster_of_the_own_club_sorted_by_rating(self):
        self.join()
        answer = self.api("roster", {}).get_json()
        self.assertEqual((answer["season"], [p["id"] for p in answer["players"]]), (2026, [1, 2]))

    def test_roster_of_other_clubs_cant_be_asked_for(self):
        self.join()
        answer = self.api("roster", {"club": "Martintxo"}).get_json()
        self.assertNotIn(3, [player["id"] for player in answer["players"]])

    def test_players_say_their_leagues(self):
        Path(self.folder, rosters.BASQUE_ROSTERS_FILE).write_text(json.dumps(
            {"season": 2026, "clubs": {"Laudio": {"primera": [1, 3]}, "Martintxo": {"honor": [2]}}}),
            encoding="utf-8")
        self.join()
        answer = self.api("roster", {}).get_json()
        leagues = {player["id"]: player["leagues"] for player in answer["players"]}
        self.assertEqual(leagues, {1: ["alava", "primera"], 2: ["alava"], 3: ["primera"]})

    def test_no_basque_file_changes_nothing(self):
        self.join()
        answer = self.api("roster", {}).get_json()
        self.assertEqual({tuple(p["leagues"]) for p in answer["players"]}, {("alava",)})

    def test_club_without_roster(self):
        self.join(club="Amurrio")
        self.assertEqual(self.api("roster", {}).get_json()["players"], [])

    def test_wrong_requests(self):
        self.join()
        self.assertEqual(self.api("lookup", {"ids": ["1"]}).status_code, 400)
        self.assertEqual(self.api("lookup", {"ids": list(range(31))}).status_code, 400)
        self.assertEqual(self.api("check", {"entries": "x"}).status_code, 400)

    def test_only_admins_manage_accounts(self):
        self.join()
        self.assertEqual(self.client.get("/admin").status_code, 403)

    def test_admin_invites_and_the_club_is_taken(self):
        self.join(is_admin=True, club="San Viator")
        text = self.client.get("/admin").get_data(as_text=True)
        self.assertNotIn("<option>San Viator</option>", text)
        self.client.post("/admin/invite", data={"name": "Maite", "club": "Martintxo",
                                                "csrf": self.csrf(path="/admin")})
        text = self.client.get("/admin").get_data(as_text=True)
        self.assertRegex(text, r"/invite/[\w-]{40,}")
        self.assertNotRegex(self.client.get("/admin").get_data(as_text=True), r"/invite/[\w-]{40,}")

    def test_cookies_are_safe(self):
        app = create_app({"ACCOUNTS": self.accounts, "PLAYERS": self.app.config["PLAYERS"],
                          "SESSION_COOKIE_PATH": "/"})
        client = app.test_client()
        token = self.accounts.create_invite("Ane", "Amurrio")
        text = client.get(f"/invite/{token}", base_url="https://x/").get_data(as_text=True)
        csrf = re.search(r'name="csrf" content="([^"]+)"', text).group(1)
        response = client.post(f"/invite/{token}", base_url="https://x/",
                               data={"password": PASSWORD, "csrf": csrf})
        cookies = "\n".join(response.headers.getlist("Set-Cookie"))
        self.assertEqual(cookies.count("Secure"), 2)
        self.assertEqual(cookies.count("HttpOnly"), 2)

    def set_language(self, code, next_page="/login"):
        return self.client.post("/language", data={"lang": code, "next": next_page,
                                                   "csrf": self.csrf()})

    def test_basque_comes_first_and_is_the_default(self):
        text = self.client.get("/login").get_data(as_text=True)
        self.assertIn('<html lang="eu">', text)
        self.assertIn("Gonbidapen bidezko sarbidea", text)
        self.assertLess(text.index("flag-eu.svg"), text.index("flag-es.svg"))

    def test_chosen_language_stays(self):
        response = self.set_language("es")
        self.assertEqual(response.headers["Location"], "/login")
        for _ in range(2):
            text = self.client.get("/login").get_data(as_text=True)
            self.assertIn('<html lang="es">', text)
            self.assertIn("Acceso solo por invitación", text)
        self.assertIn('lang="es"', self.client.get("/privacidad").get_data(as_text=True))

    def test_unknown_language_is_ignored(self):
        self.set_language("xx")
        self.assertIn('<html lang="eu">', self.client.get("/login").get_data(as_text=True))

    def test_language_cant_redirect_to_other_sites(self):
        for target in ("https://example.com/", "//example.com/", "/\\example.com"):
            location = self.set_language("es", target).headers["Location"]
            self.assertEqual(location, "/", target)

    def staging_setup(self):
        production = create_app({"ACCOUNTS": self.accounts, "PLAYERS": self.app.config["PLAYERS"],
                                 "SESSION_COOKIE_SECURE": False, "SESSION_COOKIE_PATH": "/",
                                 "RATELIMIT_ENABLED": False, "DATA_FOLDER": self.folder,
                                 "STAGING_KEY": "shared", "STAGING_URL": "https://staging.test/elo"})
        self.staging_accounts = Accounts(Path(self.folder, "staging.db"))
        staging = create_app({"ACCOUNTS": self.staging_accounts, "PLAYERS": self.app.config["PLAYERS"],
                              "SESSION_COOKIE_SECURE": False, "SESSION_COOKIE_PATH": "/",
                              "RATELIMIT_ENABLED": False, "DATA_FOLDER": self.folder,
                              "STAGING": True, "STAGING_KEY": "shared"})
        self.app = production
        self.client = production.test_client()
        self.join(is_admin=True)
        self.user_id = self.accounts.list_users()[0]["id"]
        return staging.test_client()

    def staging_path(self):
        location = self.client.get("/staging").headers["Location"]
        self.assertTrue(location.startswith("https://staging.test/elo/enter/"))
        return location.removeprefix("https://staging.test/elo")

    def test_staging_needs_access_from_the_admin(self):
        self.staging_setup()
        self.assertEqual(self.client.get("/staging").status_code, 404)
        self.assertNotIn('href="/staging"', self.client.get("/").get_data(as_text=True))
        response = self.client.post(f"/admin/staging/{self.user_id}",
                                    data={"days": "7", "csrf": self.csrf(path="/admin")})
        self.assertEqual(response.status_code, 302)
        self.assertIn('href="/staging"', self.client.get("/").get_data(as_text=True))
        self.client.post(f"/admin/staging/{self.user_id}", data={"csrf": self.csrf(path="/admin")})
        self.assertEqual(self.client.get("/staging").status_code, 404)

    def test_only_admins_give_staging_access(self):
        self.staging_setup()
        other = self.app.test_client()
        self.join(club="Amurrio", client=other)
        response = other.post(f"/admin/staging/{self.user_id}",
                              data={"days": "30", "csrf": self.csrf(other, "/")})
        self.assertEqual(response.status_code, 403)

    def test_entry_opens_staging_without_a_password(self):
        staging = self.staging_setup()
        self.accounts.set_staging(self.user_id, time.time() + 3600)
        self.assertEqual(staging.get("/").status_code, 302)
        self.assertEqual(staging.get(self.staging_path()).status_code, 302)
        self.assertEqual(staging.get("/").status_code, 200)
        self.assertIn('class="staging"', staging.get("/").get_data(as_text=True))
        person = self.staging_accounts.list_users()[0]
        self.assertEqual(person["production_id"], self.user_id)
        self.assertEqual(person["club"], "Laudio")
        self.assertIsNone(person["password_hash"])

    def test_staging_links_back_to_production(self):
        staging = self.staging_setup()
        self.assertNotIn("<a href", re.search(r'<p class="staging">.*?</p>',
                                              staging.get("/login").get_data(as_text=True)).group())
        staging.application.config["PRODUCTION_URL"] = "https://real.test/elo/"
        self.assertIn('href="https://real.test/elo/"', staging.get("/login").get_data(as_text=True))
        self.assertNotIn('class="staging"', self.client.get("/login").get_data(as_text=True))

    def test_entry_works_once(self):
        staging = self.staging_setup()
        self.accounts.set_staging(self.user_id, time.time() + 3600)
        path = self.staging_path()
        self.assertEqual(staging.get(path).status_code, 302)
        self.assertEqual(staging.application.test_client().get(path).status_code, 403)

    def test_entry_must_be_signed_by_the_right_key(self):
        staging = self.staging_setup()
        forged = entry_token("other", {"id": 1, "name": "x", "club": "Laudio", "is_admin": 1,
                                       "staging_until": time.time() + 3600})
        self.assertEqual(staging.get(f"/enter/{forged}").status_code, 403)
        self.assertEqual(staging.get("/enter/rubbish").status_code, 403)

    def test_entry_is_short_lived(self):
        token = entry_token("shared", {"id": 1, "name": "x", "club": "Laudio", "is_admin": 0,
                                       "staging_until": time.time() + 3600})
        self.assertIsNotNone(read_entry("shared", token))
        with mock.patch("itsdangerous.timed.time.time", return_value=time.time() + ENTRY_SECONDS + 5):
            self.assertIsNone(read_entry("shared", token))

    def test_production_never_accepts_an_entry(self):
        self.staging_setup()
        self.accounts.set_staging(self.user_id, time.time() + 3600)
        self.assertEqual(self.client.get(self.staging_path()).status_code, 404)

    def test_staging_closes_when_the_access_ends(self):
        staging = self.staging_setup()
        self.accounts.set_staging(self.user_id, time.time() + 3600)
        staging.get(self.staging_path())
        self.staging_accounts.set_staging(self.staging_accounts.list_users()[0]["id"], time.time() - 1)
        self.assertEqual(staging.get("/").status_code, 302)

    def test_deleting_in_staging_closes_the_session(self):
        staging = self.staging_setup()
        self.accounts.set_staging(self.user_id, time.time() + 3600)
        staging.get(self.staging_path())
        self.staging_accounts.remove_devices(self.staging_accounts.list_users()[0]["id"])
        self.assertEqual(staging.get("/").status_code, 302)

    def test_a_club_that_changed_hands_replaces_the_old_account(self):
        entry = {"name": "Ane", "club": "Laudio", "is_admin": 0, "until": time.time() + 3600}
        accounts = Accounts(Path(self.folder, "staging.db"))
        accounts.enter_staging({**entry, "id": 1, "nonce": "a"})
        accounts.enter_staging({**entry, "id": 2, "nonce": "b", "name": "Jon"})
        self.assertEqual([user["name"] for user in accounts.list_users()], ["Jon"])

    def test_old_databases_get_the_new_columns(self):
        path = Path(self.folder, "old.db")
        database = sqlite3.connect(path)
        database.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL,"
                         " club TEXT UNIQUE NOT NULL, password_hash TEXT,"
                         " is_admin INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1)")
        database.execute("INSERT INTO users (name, club) VALUES ('Ane', 'Laudio')")
        database.commit()
        database.close()
        for _ in range(2):
            users = Accounts(path).list_users()
        self.assertIsNone(users[0]["staging_until"])
    def test_the_browser_gets_the_margin_of_the_server(self):
        self.join()
        text = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-margin="50"', text)
        self.assertIn(i18n.text("eu", "range_hint", margin=50), text)

    def set_theme(self, code, next_page="/login"):
        return self.client.post("/theme", data={"theme": code, "next": next_page,
                                                "csrf": self.csrf()})

    def test_theme_follows_the_device_until_chosen(self):
        text = self.client.get("/login").get_data(as_text=True)
        self.assertIn('<html lang="eu">', text)
        self.assertNotIn('aria-pressed="true"', re.search(r'class="themes".*?</form>', text, re.S).group())

    def test_chosen_theme_stays(self):
        response = self.set_theme("dark")
        self.assertEqual(response.headers["Location"], "/login")
        for page in ("/login", "/privacidad"):
            self.assertIn('data-theme="dark"', self.client.get(page).get_data(as_text=True))
        self.set_theme("light")
        self.assertIn('data-theme="light"', self.client.get("/login").get_data(as_text=True))

    def test_unknown_theme_is_ignored(self):
        self.set_theme('"><script>')
        self.assertNotIn("data-theme", self.client.get("/login").get_data(as_text=True))

    def test_theme_needs_csrf_and_cant_redirect_to_other_sites(self):
        self.assertEqual(self.client.post("/theme", data={"theme": "dark"}).status_code, 403)
        self.assertEqual(self.set_theme("dark", "https://example.com/").headers["Location"], "/")

    def test_both_ways_to_night_mode_use_the_same_colours(self):
        style = open("web/static/style.css", encoding="utf-8").read()
        chosen = re.search(r':root\[data-theme="dark"\] \{ (.*?) \}', style).group(1)
        device = re.search(r':root:not\(\[data-theme="light"\]\) \{ (.*?) \}', style).group(1)
        self.assertEqual(chosen, device)

    def test_language_of_the_results(self):
        self.join()
        self.assertEqual(self.api("check", {"entries": [1]}).get_json()["list"]["text"],
                         "2026ko urria")
        self.set_language("es", "/")
        self.assertEqual(self.api("check", {"entries": [1]}).get_json()["list"]["text"],
                         "octubre de 2026")

    def test_errors_are_translated(self):
        token = self.accounts.create_invite("Ane", "Amurrio")
        path = f"/invite/{token}"
        text = self.client.post(path, data={"password": "corta", "csrf": self.csrf(path=path)})
        self.assertIn("gutxienez 10 karaktere", text.get_data(as_text=True))

    def test_browser_texts_are_in_the_page(self):
        self.join()
        self.assertIn("Ordena zuzena", self.client.get("/").get_data(as_text=True))

    def test_privacy_headers(self):
        headers = self.client.get("/login").headers
        self.assertIn("noindex", headers["X-Robots-Tag"])
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")


if __name__ == "__main__":
    unittest.main()
