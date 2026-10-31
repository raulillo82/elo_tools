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
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from zipfile import ZipFile, ZipInfo

from web import lists, rosters
from web.accounts import AccountError, Accounts
from web.app import create_app, limiter
from web.lists import PlayerList, build_list
from web.rules import check_order

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
PASSWORD = "contrasena-larga"


def write_list(folder, name="players-2026-10.sqlite"):
    build_list(io.BytesIO(PLAYERS_XML), Path(folder, name))


TEAM_PAGE = """<table><tr><th>Brd.</th><th>Name</th><th>FIDE ID</th></tr>
<tr><td>1</td><td><a href="/x">Soto, Ana</a></td><td>
  123</td></tr><tr><td>2</td><td>Rey, Eva</td><td>456</td></tr></table>
<table><tr><th>Rd.</th></tr><tr><td>1</td></tr></table>"""


class RostersTest(unittest.TestCase):
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
        self.assertEqual(self.players.label(), {"text": "enero de 2027", "official": True})

    def test_chosen_list(self):
        write_list(self.folder, "players-2027-01.sqlite")
        chosen = PlayerList(self.folder, "2026-10")
        self.assertEqual(chosen.label(), {"text": "octubre de 2026", "official": False})


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

    def test_new_list(self):
        with mock.patch.object(lists, "urlopen", return_value=self.fake_zip()):
            path = lists.update_list(self.folder)
        self.assertEqual(path.name, "players-2026-10.sqlite")

    def test_unchanged_list(self):
        not_modified = HTTPError("url", 304, "Not Modified", {}, None)
        with mock.patch.object(lists, "urlopen", side_effect=[self.fake_zip(), not_modified]) as url:
            lists.update_list(self.folder)
            self.assertIsNone(lists.update_list(self.folder))
        self.assertEqual(url.call_args.args[0].get_header("If-modified-since"), "date1")


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
        self.assertIn("Contraseña incorrecta", response.get_data(as_text=True))
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

    def test_privacy_headers(self):
        headers = self.client.get("/login").headers
        self.assertIn("noindex", headers["X-Robots-Tag"])
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")


if __name__ == "__main__":
    unittest.main()
