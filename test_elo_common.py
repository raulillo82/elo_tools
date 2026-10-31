'''
Run with: python3 -m unittest
All the names are made up.
'''
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError
from zipfile import ZipFile

import pandas

import elo_common
from elo_common import (EXACT, NOT_FOUND, POSSIBLE, add_missing_comma,
                        find_player, load_fide_list, normalize_name,
                        prepare_fide_list, status_text)


def fide_list(*players):
    '''
    Builds a FIDE DF from (name, country, birthday) tuples
    '''
    df_fide = pandas.DataFrame(players, columns=["name", "country", "birthday"])
    df_fide["birthday"] = df_fide["birthday"].astype("float64")
    return prepare_fide_list(df_fide)


class NormalizeNameTest(unittest.TestCase):
    def test_removes_namesake_suffix(self):
        self.assertEqual(normalize_name("Roble Soto, Ana 1987"), "roble soto, ana")
        self.assertEqual(normalize_name("Roble Soto, Ana 1967 II"), "roble soto, ana")

    def test_removes_case_accents_and_enye(self):
        self.assertEqual(normalize_name("IBAÑEZ PÉREZ, IÑAKI"), "ibanez perez, inaki")

    def test_expands_abbreviations(self):
        self.assertEqual(normalize_name("SOTO, JOSE Mª"), "soto, jose maria")
        self.assertEqual(normalize_name("SOTO, FCO. JOSE"), "soto, francisco jose")

    def test_fixes_spacing(self):
        self.assertEqual(normalize_name("Soto  Rey ,Ana"), "soto rey, ana")


class AddMissingCommaTest(unittest.TestCase):
    def test_adds_comma(self):
        self.assertEqual(add_missing_comma("Soto Rey Ana"), "Soto Rey, Ana")

    def test_leaves_the_rest_alone(self):
        self.assertEqual(add_missing_comma("Soto, Ana"), "Soto, Ana")
        self.assertEqual(add_missing_comma("Soto"), "Soto")


class FindPlayerTest(unittest.TestCase):
    def names(self, rows):
        return rows["name"].tolist()

    def test_finds_name_with_namesake_suffix(self):
        df_fide = fide_list(("Roble Soto, Ana 1987", "ESP", 1987))
        result, rows = find_player(df_fide, "Roble Soto, Ana")
        self.assertEqual(result, EXACT)
        self.assertEqual(self.names(rows), ["Roble Soto, Ana 1987"])

    def test_finds_enye_without_enye_in_fide(self):
        df_fide = fide_list(("Ibanez Soto, Inaki", "ESP", 1990))
        self.assertEqual(find_player(df_fide, "Ibañez Soto, Iñaki")[0], EXACT)

    def test_namesakes_without_birth_year_returns_all(self):
        df_fide = fide_list(("Rey Soto, Ana 1970", "ESP", 1970),
                            ("Rey Soto, Ana 1980", "ESP", 1980))
        result, rows = find_player(df_fide, "Rey Soto, Ana")
        self.assertEqual((result, len(rows)), (EXACT, 2))

    def test_birth_year_picks_the_namesake(self):
        df_fide = fide_list(("Rey Soto, Ana 1970", "ESP", 1970),
                            ("Rey Soto, Ana 1980", "ESP", 1980))
        _, rows = find_player(df_fide, "Rey Soto, Ana", 1980)
        self.assertEqual(self.names(rows), ["Rey Soto, Ana 1980"])

    def test_incomplete_name_is_only_possible(self):
        df_fide = fide_list(("Lopez Rey, Ana Maria", "ESP", 1980))
        self.assertEqual(find_player(df_fide, "Rey, Ana")[0], POSSIBLE)

    def test_partial_match_needs_whole_words(self):
        df_fide = fide_list(("Gregorio Soto, Ana", "ESP", 1980),
                            ("Gregorio, Anastasia", "ESP", 1980))
        self.assertEqual(find_player(df_fide, "Orio, Ana")[0], NOT_FOUND)
        self.assertEqual(find_player(df_fide, "Gregorio, Ana")[0], NOT_FOUND)

    def test_name_cut_by_the_basque_list(self):
        df_fide = fide_list(("Fernandez De Rey Soto, Fernando", "ESP", 1980))
        name = "Fernandez De Rey Soto, Fernand"
        self.assertEqual(len(name), 30)
        self.assertEqual(find_player(df_fide, name)[0], POSSIBLE)

    def test_partial_match_ignores_other_countries(self):
        df_fide = fide_list(("Lopez Rey, Ana", "MEX", 1980))
        self.assertEqual(find_player(df_fide, "Rey, Ana")[0], NOT_FOUND)

    def test_partial_match_discards_other_birth_years(self):
        df_fide = fide_list(("Lopez Rey, Ana", "ESP", 1950))
        self.assertEqual(find_player(df_fide, "Rey, Ana", 1990)[0], NOT_FOUND)

    def test_other_second_surname_needs_birth_year(self):
        df_fide = fide_list(("Roble Soto, Ana 1987", "ESP", 1987))
        self.assertEqual(find_player(df_fide, "Roble Rey, Ana")[0], NOT_FOUND)
        self.assertEqual(find_player(df_fide, "Roble Rey, Ana", 1987)[0], POSSIBLE)
        self.assertEqual(find_player(df_fide, "Roble Rey, Ana", 1988)[0], NOT_FOUND)

    def test_regex_characters_in_name(self):
        df_fide = fide_list(("Soto, Ana (Jr)", "ESP", 1980))
        self.assertEqual(find_player(df_fide, "Rey (, A.*")[0], NOT_FOUND)

    def test_single_word_is_never_a_partial_match(self):
        df_fide = fide_list(("Soto Rey, Ana", "ESP", 1980))
        self.assertEqual(find_player(df_fide, "Soto")[0], NOT_FOUND)


class StatusTextTest(unittest.TestCase):
    def test_flags(self):
        self.assertEqual(status_text("i"), "inactivo")
        self.assertEqual(status_text("wi"), "inactivo")
        self.assertEqual(status_text("w"), "activo")
        self.assertEqual(status_text(float("nan")), "activo")


FIDE_XML = """<playerslist><player><fideid>1</fideid><name>Soto, Ana</name>
<country>ESP</country><rating>1500</rating><birthday>1990</birthday></player>
</playerslist>"""


def fide_zip():
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("list.xml", FIDE_XML)
    return data.getvalue()


def response(data, last_modified):
    resp = mock.MagicMock()
    resp.__enter__.return_value = resp
    resp.read.return_value = data
    resp.headers = {"Last-Modified": last_modified}
    return resp


class LoadFideListTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        for name, value in (("FIDE_CACHE", Path(folder.name, "list.parquet")),
                            ("FIDE_CACHE_INFO", Path(folder.name, "list.json"))):
            patcher = mock.patch.object(elo_common, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def load(self, *answers):
        '''
        Calls load_fide_list once per answer: a response or an exception.
        Returns the last DF and all the requests and printed text
        '''
        output = StringIO()
        with mock.patch.object(elo_common, "urlopen", side_effect=answers) as urlopen, \
                redirect_stdout(output):
            for _ in answers:
                df_fide = load_fide_list()
        return df_fide, [call.args[0] for call in urlopen.call_args_list], output.getvalue()

    def test_first_run_downloads_and_saves_the_list(self):
        df_fide, _, _ = self.load(response(fide_zip(), "date1"))
        self.assertEqual(df_fide["key"].tolist(), ["soto, ana"])
        self.assertTrue(elo_common.FIDE_CACHE.exists())

    def test_unchanged_list_comes_from_disk(self):
        not_modified = HTTPError("url", 304, "Not Modified", {}, None)
        df_fide, requests, output = self.load(response(fide_zip(), "date1"), not_modified)
        self.assertEqual(requests[1].get_header("If-modified-since"), "date1")
        self.assertEqual(df_fide["key"].tolist(), ["soto, ana"])
        self.assertEqual(find_player(df_fide, "Soto, Ana")[0], EXACT)
        self.assertNotIn("AVISO", output)

    def test_newer_list_replaces_the_one_on_disk(self):
        self.load(response(fide_zip(), "date1"), response(fide_zip(), "date2"))
        info = json.loads(elo_common.FIDE_CACHE_INFO.read_text(encoding="utf-8"))
        self.assertEqual(info["last_modified"], "date2")

    def test_network_error_warns_and_uses_the_disk(self):
        df_fide, _, output = self.load(response(fide_zip(), "date1"), URLError("no network"))
        self.assertEqual(len(df_fide), 1)
        self.assertIn("AVISO", output)

    def test_network_error_without_list_on_disk_fails(self):
        with self.assertRaises(URLError):
            self.load(URLError("no network"))


if __name__ == "__main__":
    unittest.main()
