'''
Run with: python3 -m unittest
All the names are made up.
'''
import tempfile
import unittest
from pathlib import Path

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
        [("Soto Rey, Ana", 1700, "001", 1990),
         ("Roble Sol, Luis", 1750, "001", 1987),
         ("Lago Pena, Eva", 1600, "001", None),
         ("Sin Fide, Juan", 1900, "001", None),
         ("Otro Club, Mar", 1500, "002", None)],
        columns=["name", "ELO", "CLUB", "year"])
    basque["key"] = basque["name"].map(normalize_name)
    return EloData(fide, "1/1/2026", None, clubs, basque, {1: 1788, 2: 1650}, "1/12/2025")


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


    def test_fide_id(self):
        row = elo_reports.my_players_table(sample_data(), [2])[0]
        self.assertEqual((row["name"], row["confirmed"]), ("Roble Mar, Luis 1987", True))

    def test_unknown_fide_id(self):
        row = elo_reports.my_players_table(sample_data(), [999])[0]
        self.assertEqual((row["name"], row["candidates"]), ("ID FIDE 999", []))

    def test_other_second_surname_in_the_basque_list_is_not_confirmed(self):
        row = elo_reports.my_players_table(sample_data(), [2])[0]
        self.assertEqual((row["basque_elo"], row["basque_confirmed"], row["basque_name"]),
                         (1750, False, "Roble Sol, Luis"))

    def test_other_birth_year_is_not_the_basque_player(self):
        self.assertEqual(elo_reports.find_basque_player(sample_data(), "Roble Mar, Luis", 1950),
                         (None, False))


class ChangeTest(unittest.TestCase):
    def test_change_with_the_previous_list(self):
        rows = elo_reports.my_players_table(sample_data(), [1, 2, 5])
        self.assertEqual({row["candidates"][0]["fide_id"]: row["candidates"][0]["change"]
                          for row in rows}, {1: 12, 2: 0, 5: None})


class ReadPlayersFileTest(unittest.TestCase):
    def read(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "players.txt")
            path.write_text(text, encoding="utf-8")
            return elo_reports.read_players_file(path)

    def test_names_ids_and_comments(self):
        self.assertEqual(self.read("# Title\n\nSoto Rey, Ana\n  123  # Luis\n#Rey, Eva\n"),
                         ["Soto Rey, Ana", 123])

    def test_accents(self):
        self.assertEqual(self.read("Ibañez, Iñaki\n"), ["Ibañez, Iñaki"])

    def test_no_file(self):
        self.assertIsNone(elo_reports.read_players_file(Path("/no/such/file")))


def row_with(*statuses):
    return {"name": "Rey, Eva", "candidates": [{"status": status} for status in statuses]}


class FilterRowsTest(unittest.TestCase):
    def setUp(self):
        self.without_fide = row_with()
        self.active = row_with("activo")
        self.inactive = row_with("inactivo")
        self.mixed = row_with("inactivo", "activo")
        self.rows = [self.without_fide, self.active, self.inactive, self.mixed]

    def test_shows_everything_by_default(self):
        self.assertEqual(elo_reports.filter_rows(self.rows), self.rows)

    def test_hide_inactive(self):
        self.assertEqual(elo_reports.filter_rows(self.rows, show_inactive=False),
                         [self.without_fide, self.active, self.mixed])

    def test_hide_without_fide(self):
        self.assertEqual(elo_reports.filter_rows(self.rows, show_without_fide=False),
                         [self.active, self.inactive, self.mixed])

    def test_both(self):
        self.assertEqual(elo_reports.filter_rows(self.rows, False, False),
                         [self.active, self.mixed])


class ExportTest(unittest.TestCase):
    def test_csv(self):
        rows = elo_reports.club_table(sample_data(), "001")
        lines = elo_reports.to_csv(rows).splitlines()
        self.assertEqual(lines[0], ";".join(elo_reports.EXPORT_COLUMNS))
        self.assertEqual(lines[1], "Sin Fide, Juan;1900;;;;;;no")
        self.assertIn("Soto Rey, Ana;1700;1800;12;activo;1990;1;no", lines)

    def test_csv_says_since_when_is_the_change(self):
        rows = elo_reports.club_table(sample_data(), "001")
        self.assertIn("Variación desde 1/12/2025;", elo_reports.to_csv(rows, "1/12/2025"))

    def test_several_candidates_leave_fide_data_empty_and_need_review(self):
        rows = elo_reports.club_table(sample_data(), "001")
        lines = elo_reports.to_csv(rows).splitlines()
        self.assertIn("Lago Pena, Eva;1600;;;;;;sí", lines)


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
    def test_change_cell(self):
        def row(change):
            return {"candidates": [{"change": change}]}
        self.assertEqual(elo.change_cell(row(12)), "+12")
        self.assertEqual(elo.change_cell(row(-3)), "-3")
        self.assertEqual(elo.change_cell(row(0)), "=")
        self.assertEqual(elo.change_cell(row(None)), "")

    def test_change_header_says_since_when(self):
        rows = elo_reports.club_table(sample_data(), "001")
        self.assertIn("Var. desde 1/12/2025", elo.format_players("X", rows, "1/12/2025"))

    def test_change_header_without_previous_list(self):
        rows = elo_reports.club_table(sample_data(), "001")
        self.assertNotIn("desde", elo.format_players("X", rows))

    def test_doubt_in_the_basque_list_is_explained(self):
        rows = elo_reports.my_players_table(sample_data(), [2])
        self.assertEqual(elo.basque_cell(rows[0]), "1750?")
        self.assertIn("¿Es Roble Sol, Luis en la lista vasca?", elo.format_players("X", rows))

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
