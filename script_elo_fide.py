#Use pandas library to work with csv's and xml's
import pandas
from io import BytesIO
from zipfile import ZipFile
from urllib.request import urlopen
try:
    from players import players
except ModuleNotFoundError:
    #Tell users to create the file with the playersinfo
    #Including the name of the file and its format
    print("Por favor, crea un archivo con los jugadores")
    print("Nombre del archivo: 'players.py'")
    print("Formato del archivo:")
    print("")
    print("players = [")
    print('"Apellido1 Apellido2, Nombre",')
    print('"Apellido1 Apellido2, Nombre",')
    print('"Apellido1 Apellido2, Nombre",')
    print("]")
    #Exit without running the actual program
    exit(1)

url_list_latest = "http://ratings.fide.com/download/standard_rating_list_xml.zip"
resp = urlopen(url_list_latest)

with ZipFile(BytesIO(resp.read())) as zipfile:
    #zipfile has only one compressed file:
    xml_file = zipfile.namelist()[0]
    #Get the date, it's a tuple
    date = zipfile.getinfo(xml_file).date_time
    #Time is not needed, just the date. Make it human readable
    human_date = str(date[2]) + "/" + str(date[1]) + "/" + str(date[0])
    #Some formatting, print the date of the list for users to see it
    print(f"ELOs FIDE a fecha de {human_date}:")
    #Read the whole XML into a pandas dataframe
    elos_df = pandas.read_xml(zipfile.open(xml_file))

#Search for the players in the list. Sort them by rating, top to bottom
player_ids = elos_df[elos_df.name.isin(players)].sort_values(by="rating", ascending=False)
#Print results. Remove the index column (misleading for non-developers)
print(player_ids.to_string(index=False))
