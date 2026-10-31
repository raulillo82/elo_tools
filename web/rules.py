'''
The rules of a board order. Ratings go in board order, first board first, and
None means the player has no FIDE ELO.
'''

#The rules of each year can change it: set ELO_MARGIN in the environment
DEFAULT_MARGIN = 50


def check_order(ratings, margin=DEFAULT_MARGIN):
    '''
    Returns the list of broken rules, empty if the order is right. Each one is
    a dictionary with the two boards (numbered from 1), and "difference", which
    is None if the problem is a player without ELO above one who has it.
    '''
    errors = []
    for upper, upper_rating in enumerate(ratings):
        for lower, lower_rating in enumerate(ratings[upper + 1:], upper + 1):
            if lower_rating is None:
                continue
            if upper_rating is None:
                difference = None
            elif lower_rating - upper_rating > margin:
                difference = lower_rating - upper_rating
            else:
                continue
            errors.append({"upper": upper + 1, "lower": lower + 1,
                           "upper_rating": upper_rating, "lower_rating": lower_rating,
                           "difference": difference})
    return errors
