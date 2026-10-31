import pandas
from elo_common import EXACT, POSSIBLE, load_fide_list, find_player
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
    raise SystemExit(1)

COLUMNS = ["fideid", "name", "country", "sex", "title", "rating", "games",
           "birthday", "flag"]


def main():
    df_fide = load_fide_list()
    found, possible, not_found = [], [], []
    for player in players:
        result, rows = find_player(df_fide, player)
        if result == EXACT:
            found.append(rows)
            if len(rows) > 1:
                print(f"AVISO: {len(rows)} jugadores se llaman '{player}'")
        elif result == POSSIBLE:
            possible.append((player, rows))
        else:
            not_found.append(player)

    #Sort by rating, top to bottom. Remove the index column (misleading for
    #non-developers)
    if found:
        table = pandas.concat(found).sort_values(by="rating", ascending=False)
        print(table[COLUMNS].to_string(index=False))
    for player, rows in possible:
        print(f"\nPosibles coincidencias para '{player}' (no incluidas arriba):")
        print(rows[COLUMNS].to_string(index=False))
    if not_found:
        print("\nNo encontrados en la lista FIDE:")
        for player in not_found:
            print(f"  {player}")


if __name__ == "__main__":
    main()
