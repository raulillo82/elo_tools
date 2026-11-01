'''
Keeps a copy of the FIDE ratings of Spanish players each time FIDE publishes a
new list, to be able to show how they change.
'''
from pathlib import Path

import pandas

HISTORY_FOLDER = Path(__file__).parent / "fide_history"

#FIDE sometimes republishes a list adding new players or fixing a few details.
#That's not a new list: only ratings changing in many players mean that it is
MIN_CHANGES_NEW_LIST = 50


def ratings_of(df_fide):
    '''
    Returns the part of the FIDE DF to keep: the Spanish players' ratings
    '''
    spanish = df_fide[df_fide["country"] == "ESP"]
    return spanish[["fideid", "rating"]].sort_values("fideid").reset_index(drop=True)


def history_files():
    '''
    Returns the saved lists, oldest first. Their names are their months
    '''
    return sorted(HISTORY_FOLDER.glob("*.parquet"))


def count_changes(old, new):
    '''
    Returns how many players have a different rating in both lists
    '''
    both = old.merge(new, on="fideid", suffixes=("_old", "_new"))
    return int((both["rating_old"] != both["rating_new"]).sum())


def update_history(df_fide, month):
    '''
    Saves the ratings of a list, its month being year-month. If it's not really
    a new list, it takes the place of the last saved one
    '''
    HISTORY_FOLDER.mkdir(exist_ok=True)
    target = HISTORY_FOLDER / f"{month}.parquet"
    ratings = ratings_of(df_fide)
    files = history_files()
    if files:
        changes = count_changes(pandas.read_parquet(files[-1]), ratings)
        if changes < MIN_CHANGES_NEW_LIST:
            target = files[-1]
    ratings.to_parquet(target)


def previous_ratings():
    '''
    Returns the ratings of the list before the last one, as a tuple: a
    dictionary with FIDE ID -> rating, and its month as year-month. The
    month is None if there's no previous list yet.
    '''
    files = history_files()
    if len(files) < 2:
        return {}, None
    previous = pandas.read_parquet(files[-2])
    return dict(zip(previous["fideid"], previous["rating"])), files[-2].stem
