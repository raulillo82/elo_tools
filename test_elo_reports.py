'''
Run with: python3 -m unittest
All the names are made up.
'''
import unittest

import pandas

import elo
import elo_reports
from elo_common import normalize_name, prepare_fide_list
from elo_reports import EloData


def sample_data():
    fide = prepare_fide_list(pandas.DataFrame(
        [(1, "Soto Rey, Ana", "ESP", 1800, 1990.0, None),
         (2, "Roble Mar, Luis 1987", "ESP", 1650, 1987.0, "i"),
         (3, "Lago Pena, Eva 1970", "ESP", 2000, 1970.0, None),
         (4, "Lago Pena, Eva 1980", "ESP", 1500, 1980.0, None),
         (5, "Soto, Hans", "GER", 2100, 1960.0, None)],
        columns=["fideid", "name", "country", "rating", "birthday", "flag"]))
    clubs = pandas.DataFrame([("001", "SAN PRUEBA", "VITORIA"),
                              ("002", "SAN OTRO", "BILBAO"),
                              ("003", "LAGO", "VITORIA")],
                             columns=["CLAVE", "CLUB", "LOC"])
    basque = pandas.DataFrame(
        [("Soto Rey, Ana", 1700, "001", None),
         ("Roble Sol, Luis", 1750, "001", 1987),
         ("Lago Pena, Eva", 1600, "001", None),
         ("Sin Fide, Juan", 1900, "001", None),
         ("Otro Club, Mar", 1500, "002", None)],
        columns=["name", "ELO", "CLUB", "year"])
    basque["key"] = basque["name"].map(normalize_name)
    return EloData(fide, "1/1/2026", None, clubs, basque)


class ClubTableTest(unittest.TestCase):
    def setUp(self):
        self.rows = elo_reports.club_table(sample_data(), "001")
        self.by_name = {row["name"]: row for row in self.rows}

    def test_only_that_club_sorted_by_basque_elo(self):
        self.assertEqual([row["basque_elo"] for row in self.rows], [1900, 1750, 1700, 1600])

    def test_player_without_fide_keeps_the_basque_elo(self):
        row = self.by_name["Sin Fide, Juan"]
        self.assertEqual((row["basque_elo"], row["candidates"]), (1900, []))

    def test_full_name_is_confirmed(self):
        self.assertTrue(self.by_name["Soto Rey, Ana"]["confirmed"])

    def test_other_second_surname_is_not_confirmed(self):
        row = self.by_name["Roble Sol, Luis"]
        self.assertFalse(row["confirmed"])
        self.assertEqual(row["candidates"][0]["rating"], 1650)

    def test_namesakes_are_not_confirmed(self):
        row = self.by_name["Lago Pena, Eva"]
        self.assertFalse(row["confirmed"])
        self.assertEqual(len(row["candidates"]), 2)


class MyPlayersTableTest(unittest.TestCase):
    def test_sorted_by_fide_with_the_rest_last(self):
        rows = elo_reports.my_players_table(sample_data(), ["Nadie, Pepe", "Roble Mar, Luis",
                                                            "Soto Rey, Ana"])
        self.assertEqual([row["name"] for row in rows],
                         ["Soto Rey, Ana", "Roble Mar, Luis", "Nadie, Pepe"])

    def test_adds_the_basque_elo(self):
        rows = elo_reports.my_players_table(sample_data(), ["Soto Rey, Ana"])
        self.assertEqual(rows[0]["basque_elo"], 1700)

    def test_player_only_in_the_basque_list_is_shown(self):
        rows = elo_reports.my_players_table(sample_data(), ["Sin Fide, Juan"])
        self.assertEqual((rows[0]["basque_elo"], rows[0]["candidates"]), (1900, []))


class FindClubsTest(unittest.TestCase):
    def test_any_part_of_the_name_ignoring_case(self):
        names = [club["name"] for club in elo_reports.find_clubs(sample_data(), "san")]
        self.assertEqual(names, ["SAN PRUEBA", "SAN OTRO"])

    def test_no_club(self):
        self.assertEqual(elo_reports.find_clubs(sample_data(), "nada"), [])


class SearchPlayersTest(unittest.TestCase):
    def test_searches_both_lists_in_any_order(self):
        results = elo_reports.search_players(sample_data(), "ana soto")
        self.assertEqual([fide["fide_id"] for fide in results["fide"]], [1])
        self.assertEqual(results["basque"][0]["club"], "SAN PRUEBA")

    def test_words_can_be_incomplete_only_by_their_end(self):
        data = sample_data()
        self.assertEqual(len(elo_reports.search_players(data, "rob")["fide"]), 1)
        self.assertEqual(elo_reports.search_players(data, "oble")["fide"], [])

    def test_names_only_look_at_spanish_fide_players(self):
        self.assertEqual(elo_reports.search_players(sample_data(), "hans")["fide"], [])

    def test_fide_id_finds_any_country(self):
        self.assertEqual(elo_reports.search_players(sample_data(), "5")["fide"][0]["rating"], 2100)

    def test_special_characters(self):
        self.assertEqual(elo_reports.search_players(sample_data(), "(")["fide"], [])

    def test_empty_text_finds_nothing(self):
        results = elo_reports.search_players(sample_data(), "  ")
        self.assertEqual((results["fide"], results["basque"]), ([], []))


class ConsoleTest(unittest.TestCase):
    def test_table_aligns_columns(self):
        self.assertEqual(elo.format_table(["A", "ELO"], [["Soto", 1], ["Rey", 1500]]),
                         "A      ELO\nSoto     1\nRey   1500")

    def test_fide_cell(self):
        fide = {"rating": 1650}
        self.assertEqual(elo.fide_cell({"candidates": []}), "-")
        self.assertEqual(elo.fide_cell({"candidates": [fide], "confirmed": True}), 1650)
        self.assertEqual(elo.fide_cell({"candidates": [fide], "confirmed": False}), "1650?")
        self.assertEqual(elo.fide_cell({"candidates": [fide, fide], "confirmed": False}), "varios?")

    def test_doubts_are_explained_below_the_table(self):
        rows = elo_reports.club_table(sample_data(), "001")
        text = elo.format_players("CLUB", rows)
        self.assertIn("¿Es Roble Mar, Luis 1987?", text)
        self.assertNotIn("¿Es Soto Rey, Ana?", text)


if __name__ == "__main__":
    unittest.main()
