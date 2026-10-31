'''
Comparing player names. It only uses the standard library, because the web
doesn't need pandas.
'''
import re
import unicodedata

#FIDE tells namesakes apart adding the birth year to the name, sometimes with
#a roman numeral: "Soto Rey, Ana 1987", "Lago Pena, Luis 1967 II"
NAMESAKE_SUFFIX = re.compile(r"\s+\d{4}(\s+[ivx]+)?$")

def normalize_name(name):
    '''
    Returns a version of the name which is only useful to compare names:
    lowercase, no accents, no "ñ", and without the FIDE namesake suffix.
    '''
    name = name.lower().replace("mª", "maria")
    name = re.sub(r"\bfco\b\.?", "francisco", name)
    #Split letters from their accents, then drop the accents
    decomposed = unicodedata.normalize("NFKD", name)
    name = "".join(char for char in decomposed if not unicodedata.combining(char))
    name = re.sub(r"\s*,\s*", ", ", name)
    name = " ".join(name.split())
    return NAMESAKE_SUFFIX.sub("", name)


def add_missing_comma(name):
    '''
    Some names in the Basque list have no comma. Assumes the last word is the
    first name: "Perez Lopez Juan" becomes "Perez Lopez, Juan"
    '''
    words = name.split()
    if "," in name or len(words) < 2:
        return name
    return " ".join(words[:-1]) + ", " + words[-1]
