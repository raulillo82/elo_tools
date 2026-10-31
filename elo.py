'''
Console for the ELO lists. Only shows things on screen: the work is done in
elo_reports.py. Without arguments it shows a menu, otherwise:

    python3 elo.py jugadores
    python3 elo.py club "san viator" --activos --solo-fide --csv
    python3 elo.py buscar mata
'''
import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import elo_reports
from elo_basque import ELOVASCO_DATE

#Shown when pressing Enter at the "club" option
DEFAULT_CLUBS = ["SAN VIATOR", "MARTINTXO"]
EXPORT_FOLDER = Path(__file__).parent / "exports"

PLAYERS_FILE_HELP = """Por favor, crea un archivo con los jugadores
Nombre del archivo: 'players.txt'
Formato del archivo, un jugador por línea, con su nombre o su ID FIDE:

Apellido1 Apellido2, Nombre
12345678  # Lo que va detrás de una almohadilla es un comentario"""


@dataclass
class Options:
    '''
    What to show. The menu can change them while it's running
    '''
    show_inactive: bool = True
    show_without_fide: bool = True
    export: bool = False


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


def basque_cell(row):
    '''
    Returns the text for the Basque ELO. "?" means it has to be double checked
    '''
    if row["basque_elo"] is None:
        return "-"
    return row["basque_elo"] if row["basque_confirmed"] else f"{row['basque_elo']}?"


def change_cell(row):
    '''
    Returns the text for the change of the FIDE ELO, like "+12"
    '''
    if len(row["candidates"]) != 1 or row["candidates"][0]["change"] is None:
        return ""
    return f"{row['candidates'][0]['change']:+d}" if row["candidates"][0]["change"] else "="


def player_cells(row):
    '''
    Returns the cells of a player: the status needs a single FIDE candidate
    '''
    single = row["candidates"][0] if len(row["candidates"]) == 1 else None
    return [row["name"], basque_cell(row), fide_cell(row), change_cell(row),
            single["status"] if single else ""]


def format_doubts(rows):
    '''
    Returns the text explaining which matches have to be double checked
    '''
    text = ""
    for row in rows:
        if row["basque_elo"] is not None and not row["basque_confirmed"]:
            text += f"\n  {row['name']}:\n    ¿Es {row['basque_name']} en la lista vasca?"
        if row["candidates"] and not row["confirmed"]:
            text += f"\n  {row['name']}:"
            for fide in row["candidates"]:
                text += (f"\n    ¿Es {fide['name']}? (nacido en {fide['birth_year'] or '?'})"
                         f" - ELO FIDE: {fide['rating']} - {fide['status']}")
    if text:
        return "\n\nA revisar (el nombre no coincide del todo, o hay homónimos):" + text
    return ""


def format_players(title, rows, previous_date=None):
    '''
    Returns the text of a table of player rows, and the doubts below it
    '''
    change = f"Var. desde {previous_date}" if previous_date else "Var."
    headers = [title, "ELO vasco", "ELO FIDE", change, "Estado"]
    text = format_table(headers, [player_cells(row) for row in rows])
    return text + format_doubts(rows)


def export_rows(title, rows, previous_date):
    '''
    Saves the player rows to a CSV file. utf-8-sig lets Excel read accents
    '''
    EXPORT_FOLDER.mkdir(exist_ok=True)
    name = re.sub(r"\W+", "_", title.lower()).strip("_")
    path = EXPORT_FOLDER / f"{name}.csv"
    path.write_text(elo_reports.to_csv(rows, previous_date), encoding="utf-8-sig")
    print(f"Guardado en {path}")


def show_rows(data, title, rows, options):
    rows = elo_reports.filter_rows(rows, options.show_inactive, options.show_without_fide)
    print(format_players(title, rows, data.previous_date))
    print()
    if options.export:
        export_rows(title, rows, data.previous_date)


def show_my_players(data, options):
    players = elo_reports.read_players_file()
    if players is None:
        print(PLAYERS_FILE_HELP)
    else:
        show_rows(data, "JUGADOR", elo_reports.my_players_table(data, players), options)


def show_clubs(data, clubs, options):
    for club in clubs:
        show_rows(data, club["name"], elo_reports.club_table(data, club["id"]), options)


def show_club_search(data, text, options):
    clubs = elo_reports.find_clubs(data, text)
    if not clubs:
        print(f"No hay ningún club con '{text}' en el nombre")
    elif len(clubs) == 1:
        show_clubs(data, clubs, options)
    else:
        print("Hay varios clubes, afina más:")
        for club in clubs:
            print(f"  {club['name']} ({club['town']})")


def show_default_clubs(data, options):
    for name in DEFAULT_CLUBS:
        show_clubs(data, [club for club in elo_reports.find_clubs(data, name)
                          if club["name"] == name], options)


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


def yes_no(value):
    return "sí" if value else "no"


def print_menu(options):
    print(f"""
1. Mis jugadores
2. Clubes
3. Buscar jugador
4. Mostrar inactivos: {yes_no(options.show_inactive)}
5. Mostrar jugadores sin ELO FIDE: {yes_no(options.show_without_fide)}
6. Guardar los listados en CSV: {yes_no(options.export)}
7. Salir""")


def menu(data, options):
    while True:
        print_menu(options)
        try:
            option = input("Opción: ").strip()
            print()
            if option == "1":
                show_my_players(data, options)
            elif option == "2":
                text = input(f"Club (Enter para {' y '.join(DEFAULT_CLUBS)}): ").strip()
                print()
                if text:
                    show_club_search(data, text, options)
                else:
                    show_default_clubs(data, options)
            elif option == "3":
                show_search(data, input("Nombre o ID FIDE: "))
            elif option == "4":
                options.show_inactive = not options.show_inactive
            elif option == "5":
                options.show_without_fide = not options.show_without_fide
            elif option == "6":
                options.export = not options.export
            elif option == "7":
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
    parser.add_argument("--activos", action="store_true", help="oculta a los inactivos")
    parser.add_argument("--solo-fide", action="store_true",
                        help="oculta a los jugadores sin ELO FIDE")
    parser.add_argument("--csv", action="store_true", help="guarda el listado en exports/")
    args = parser.parse_args()
    if args.action in ("club", "buscar") and not args.text:
        parser.error(f"'{args.action}' necesita un texto")

    options = Options(not args.activos, not args.solo_fide, args.csv)
    data = elo_reports.load_data()
    print(f"ELOs FIDE a fecha de {data.fide_date}. "
          f"ELOs vascos de {ELOVASCO_DATE}, no se comprueba si hay alguno más reciente.")
    if data.fide_warning:
        print(f"AVISO: {data.fide_warning}")
    print()
    if args.action == "jugadores":
        show_my_players(data, options)
    elif args.action == "club":
        show_club_search(data, args.text, options)
    elif args.action == "buscar":
        show_search(data, args.text)
    else:
        menu(data, options)


if __name__ == "__main__":
    main()
