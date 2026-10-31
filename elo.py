'''
Console for the ELO lists. Only shows things on screen: the work is done in
elo_reports.py. Without arguments it shows a menu, otherwise:

    python3 elo.py jugadores
    python3 elo.py club "san viator"
    python3 elo.py buscar mata
'''
import argparse

import elo_reports
from elo_basque import ELOVASCO_DATE

#Shown when pressing Enter at the "club" option
DEFAULT_CLUBS = ["SAN VIATOR", "MARTINTXO"]

PLAYERS_FILE_HELP = """Por favor, crea un archivo con los jugadores
Nombre del archivo: 'players.py'
Formato del archivo:

players = [
"Apellido1 Apellido2, Nombre",
"Apellido1 Apellido2, Nombre",
]"""


def format_table(headers, rows):
    '''
    Returns the text of a table with columns as wide as their content. The
    first column is aligned to the left and the rest to the right
    '''
    columns = list(zip(headers, *rows))
    widths = [max(len(str(cell)) for cell in column) for column in columns]

    def line(cells):
        texts = [str(cell).rjust(width) for cell, width in zip(cells, widths)]
        texts[0] = str(cells[0]).ljust(widths[0])
        return "  ".join(texts)
    return "\n".join(line(cells) for cells in [headers, *rows])


def fide_cell(row):
    '''
    Returns the text for the FIDE ELO. "?" means it has to be double checked
    '''
    if not row["candidates"]:
        return "-"
    if len(row["candidates"]) > 1:
        return "varios?"
    rating = row["candidates"][0]["rating"]
    return rating if row["confirmed"] else f"{rating}?"


def player_cells(row):
    '''
    Returns the cells of a player: the status needs a single FIDE candidate
    '''
    single = row["candidates"][0] if len(row["candidates"]) == 1 else None
    return [row["name"],
            "-" if row["basque_elo"] is None else row["basque_elo"],
            fide_cell(row),
            single["status"] if single else ""]


def format_players(title, rows):
    '''
    Returns the text of a table of player rows, and the doubts below it
    '''
    headers = [title, "ELO vasco", "ELO FIDE", "Estado"]
    text = format_table(headers, [player_cells(row) for row in rows])
    doubts = [row for row in rows if row["candidates"] and not row["confirmed"]]
    if doubts:
        text += "\n\nA revisar (el nombre no coincide del todo, o hay homónimos):"
    for row in doubts:
        text += f"\n  {row['name']}:"
        for fide in row["candidates"]:
            text += (f"\n    ¿Es {fide['name']}? (nacido en {fide['birth_year'] or '?'})"
                     f" - ELO FIDE: {fide['rating']} - {fide['status']}")
    return text


def show_my_players(data):
    try:
        from players import players
    except ModuleNotFoundError:
        print(PLAYERS_FILE_HELP)
        return
    print(format_players("JUGADOR", elo_reports.my_players_table(data, players)))


def show_clubs(data, clubs):
    for club in clubs:
        print(format_players(club["name"], elo_reports.club_table(data, club["id"])))
        print()


def show_club_search(data, text):
    clubs = elo_reports.find_clubs(data, text)
    if not clubs:
        print(f"No hay ningún club con '{text}' en el nombre")
    elif len(clubs) == 1:
        show_clubs(data, clubs)
    else:
        print("Hay varios clubes, afina más:")
        for club in clubs:
            print(f"  {club['name']} ({club['town']})")


def show_default_clubs(data):
    for name in DEFAULT_CLUBS:
        show_clubs(data, [club for club in elo_reports.find_clubs(data, name)
                          if club["name"] == name])


def show_search(data, text):
    results = elo_reports.search_players(data, text)
    if results["fide"]:
        print(format_table(["LISTA FIDE", "ELO FIDE", "Estado", "Nacido", "ID FIDE"],
                           [[fide["name"], fide["rating"], fide["status"],
                             fide["birth_year"] or "?", fide["fide_id"]]
                            for fide in results["fide"]]))
        print()
    if results["basque"]:
        print(format_table(["LISTA VASCA", "ELO vasco", "Club"],
                           [[player["name"], player["elo"], player["club"]]
                            for player in results["basque"]]))
        print()
    if not results["fide"] and not results["basque"]:
        print(f"No se ha encontrado '{text}'")
    if results["too_many"]:
        print(f"Hay más resultados, se muestran {elo_reports.MAX_SEARCH_RESULTS}: afina más")


def menu(data):
    while True:
        print("\n1. Mis jugadores\n2. Clubes\n3. Buscar jugador\n4. Salir")
        try:
            option = input("Opción: ").strip()
            print()
            if option == "1":
                show_my_players(data)
            elif option == "2":
                text = input(f"Club (Enter para {' y '.join(DEFAULT_CLUBS)}): ").strip()
                print()
                if text:
                    show_club_search(data, text)
                else:
                    show_default_clubs(data)
            elif option == "3":
                show_search(data, input("Nombre o ID FIDE: "))
            elif option == "4":
                return
            else:
                print("Opción no válida")
        #Ctrl+D or Ctrl+C
        except (EOFError, KeyboardInterrupt):
            print()
            return


def main():
    parser = argparse.ArgumentParser(description="Consulta los ELOs FIDE y vasco")
    parser.add_argument("action", nargs="?", choices=["jugadores", "club", "buscar"])
    parser.add_argument("text", nargs="?", help="nombre del club o del jugador")
    args = parser.parse_args()
    if args.action in ("club", "buscar") and not args.text:
        parser.error(f"'{args.action}' necesita un texto")

    data = elo_reports.load_data()
    print(f"ELOs FIDE a fecha de {data.fide_date}. "
          f"ELOs vascos de {ELOVASCO_DATE}, no se comprueba si hay alguno más reciente.")
    if data.fide_warning:
        print(f"AVISO: {data.fide_warning}")
    print()
    if args.action == "jugadores":
        show_my_players(data)
    elif args.action == "club":
        show_club_search(data, args.text)
    elif args.action == "buscar":
        show_search(data, args.text)
    else:
        menu(data)


if __name__ == "__main__":
    main()
