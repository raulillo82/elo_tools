'''
Run with: python3 -m unittest
All the names are made up.
'''
import unittest

import pandas

from elo_common import (EXACT, NOT_FOUND, POSSIBLE, add_missing_comma,
                        find_player, normalize_name, prepare_fide_list,
                        status_text)


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


if __name__ == "__main__":
    unittest.main()
