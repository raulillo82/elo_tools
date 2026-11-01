'''
Run with: python3 -m unittest
'''
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas

import elo_history
from elo_history import previous_ratings, update_history


def fide_list(ratings, country="ESP"):
    return pandas.DataFrame({"fideid": list(ratings), "rating": list(ratings.values()),
                             "country": country})


class HistoryTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patcher = mock.patch.multiple(elo_history, HISTORY_FOLDER=Path(folder.name),
                                      MIN_CHANGES_NEW_LIST=2)
        patcher.start()
        self.addCleanup(patcher.stop)

    def saved(self):
        return [path.stem for path in elo_history.history_files()]

    def test_no_previous_list_at_first(self):
        update_history(fide_list({1: 1500, 2: 1600}), "2026-02")
        self.assertEqual(previous_ratings(), ({}, None))

    def test_new_list_keeps_the_previous_one(self):
        update_history(fide_list({1: 1500, 2: 1600}), "2026-02")
        update_history(fide_list({1: 1510, 2: 1590}), "2026-03")
        self.assertEqual(self.saved(), ["2026-02", "2026-03"])
        self.assertEqual(previous_ratings(), ({1: 1500, 2: 1600}, "2026-02"))

    def test_republished_list_is_not_a_new_list(self):
        update_history(fide_list({1: 1500, 2: 1600}), "2026-02")
        update_history(fide_list({1: 1510, 2: 1590}), "2026-03")
        update_history(fide_list({1: 1510, 2: 1590, 3: 1400}), "2026-03")
        self.assertEqual(self.saved(), ["2026-02", "2026-03"])
        self.assertEqual(previous_ratings()[1], "2026-02")

    def test_only_spanish_players(self):
        update_history(pandas.concat([fide_list({1: 1500}), fide_list({2: 1600}, "GER")]),
                       "2026-02")
        saved = pandas.read_parquet(elo_history.history_files()[0])
        self.assertEqual(saved["fideid"].tolist(), [1])


if __name__ == "__main__":
    unittest.main()
