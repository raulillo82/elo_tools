'''
The texts of the web in Basque and Spanish. Each key has (Basque, Spanish).
Basque goes first and is the default language. Terms follow the Basque version
of the championship rules: "orden de fuerzas" is "taulen ordena".
'''
LANGUAGES = ("eu", "es")
DEFAULT_LANGUAGE = "eu"
MONTHS = {
    "eu": ["urtarrila", "otsaila", "martxoa", "apirila", "maiatza", "ekaina", "uztaila",
           "abuztua", "iraila", "urria", "azaroa", "abendua"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"]}

TEXTS = {
    #Common
    "brand": ("Taulen ordena", "Orden de fuerzas"),
    "access": ("Sarbideak", "Accesos"),
    "logout": ("Irten", "Salir"),
    "privacy": ("Pribatutasuna", "Privacidad"),
    "language": ("Hizkuntza", "Idioma"),
    #Login and invitations
    "hello": ("Kaixo, {name}", "Hola, {name}"),
    "password": ("Pasahitza", "Contraseña"),
    "enter": ("Sartu", "Entrar"),
    "wrong_password": ("Pasahitz okerra", "Contraseña incorrecta"),
    "invite_only": ("Gonbidapen bidezko sarbidea soilik", "Acceso solo por invitación"),
    "invite_only_text": ("Gailu honek ez du baimenik. Klub bateko arduraduna bazara, eskatu "
                         "gonbidapen bat.",
                         "Este dispositivo no está autorizado. Si eres responsable de un club, "
                         "pide una invitación."),
    "invite_for": ("{club} klubaren gonbidapena. Gailu honi lotuta geratuko da.",
                   "Invitación para {club}. Quedará vinculada a este dispositivo."),
    "your_password": ("Zure pasahitza", "Tu contraseña"),
    "choose_password": ("Aukeratu pasahitz bat (gutxienez {n} karaktere)",
                        "Elige una contraseña (mínimo {n} caracteres)"),
    "activate": ("Aktibatu", "Activar"),
    "invite_used_title": ("Gonbidapenak ez du balio", "Invitación no válida"),
    "invite_used_text": ("Gonbidapena erabili da dagoeneko edo iraungi egin da.",
                         "La invitación ya se ha usado o ha caducado."),
    #Account errors
    "invite_invalid": ("Gonbidapenak ez du balio edo iraungi egin da",
                       "La invitación no es válida o ha caducado"),
    "password_short": ("Pasahitzak gutxienez {n} karaktere izan behar ditu",
                       "La contraseña debe tener al menos {n} caracteres"),
    "too_many_devices": ("Kontu honek {n} gailu ditu dagoeneko",
                         "Esta cuenta ya tiene {n} dispositivos"),
    "no_such_club": ("Klub hori ez dago", "Ese club no existe"),
    "club_taken": ("Klub horrek badu arduraduna", "Ese club ya tiene responsable"),
    "admin_kept": ("Ezin da administratzailea ezabatu", "No se puede borrar al administrador"),
    "name_missing": ("Izena falta da", "Falta el nombre"),
    #The tool
    "list_is": ("FIDE zerrenda: {list}.", "Lista FIDE de {list}."),
    "provisional": ("Behin-behinekoa:", "Provisional:"),
    "provisional_text": ("ordena ofiziala urtarrileko zerrendarekin egiten da, urte bakoitzeko "
                         "oinarrien arabera.",
                         "el orden oficial se hace con la lista de enero, según las bases del año."),
    "team": ("Taldea", "Equipo"),
    "last_season": ("Aurreko denboraldiko jokalariak", "Jugadores de la temporada pasada"),
    "roster_hint": ("Markatu talde honetan nahi dituzunak. Zure klubekoak bakarrik ikusten dituzu.",
                    "Marca los que quieras en este equipo. Solo ves a los de tu club."),
    "add_by_name": ("Gehitu jokalaria izenez", "Añadir jugador por nombre"),
    "name_placeholder": ("Abizena eta izena", "Apellido y nombre"),
    "search_hint": ("Idatzi gutxienez bi hitz oso, adibidez abizen bat eta izena.",
                    "Escribe al menos dos palabras completas, por ejemplo un apellido y el nombre."),
    "more_ways": ("Gehitzeko beste modu batzuk", "Más formas de añadir"),
    "fide_ids": ("FIDE IDak (zuriunez edo komaz bereizita)",
                 "IDs FIDE (separados por espacios o comas)"),
    "add_ids": ("Gehitu IDak", "Añadir IDs"),
    "no_fide_id": ("FIDE IDrik gabeko jokalaria", "Jugador sin ID FIDE"),
    "name": ("Izena", "Nombre"),
    "add_no_elo": ("Gehitu ELOrik gabe", "Añadir sin ELO"),
    "stays_here": ("Izen hau ez da zure gailutik ateratzen.",
                   "Este nombre no sale de tu dispositivo."),
    "boards": ("Taulak", "Tableros"),
    "no_players": ("Oraindik ez dago jokalaririk.", "Todavía no hay jugadores."),
    "sort": ("Ordenatu ELOaren arabera", "Ordenar por ELO"),
    "check": ("Egiaztatu", "Comprobar"),
    "clear": ("Hustu", "Vaciar"),
    "excel": ("Deskargatu Excel", "Descargar Excel"),
    "save_toggle": ("Gorde nire ordenak gailu honetan", "Guardar mis órdenes en este dispositivo"),
    "save_hint": ("Nabigatzaile honetan bakarrik gordetzen dira, inoiz ez zerbitzarian: beste "
                  "inork ezin ditu ikusi, eta ez dira zure beste gailuetara pasatzen. Excel "
                  "fitxategia Google Sheets eta LibreOffice programetan ere irekitzen da.",
                  "Solo se guardan en este navegador, nunca en el servidor: nadie más puede "
                  "verlos, y no pasan a tus otros dispositivos. El fichero Excel también se abre "
                  "en Google Sheets y LibreOffice."),
    "save_team": ("Gorde talde hau", "Guardar este equipo"),
    "excel_all": ("Guztien Excela", "Excel de todos"),
    "move_teams": ("Eraman nire taldeak beste gailu batera",
                   "Pasar mis equipos a otro dispositivo"),
    "move_step1": ("Hemen, sakatu <strong>Deskargatu kopia</strong>: gordetako talde guztiak "
                   "dituen <code>.json</code> fitxategi bat lortuko duzu.",
                   "Aquí, pulsa <strong>Descargar copia</strong>: obtienes un fichero "
                   "<code>.json</code> con todos tus equipos guardados."),
    "move_step2": ("Eraman fitxategi hori beste gailura.", "Pasa ese fichero al otro dispositivo."),
    "move_step3": ("Han, aktibatu gordetzea, sakatu <strong>Leheneratu kopia</strong> eta "
                   "aukeratu fitxategia.",
                   "Allí, activa el guardado, pulsa <strong>Restaurar copia</strong> y elige el "
                   "fichero."),
    "move_hint": ("Fitxategi horrek bakarrik balio du, ez Excel batek. Izen bereko taldeak "
                  "ordeztu egiten dira.",
                  "Solo vale ese fichero, no un Excel. Los equipos con el mismo nombre se "
                  "sustituyen."),
    "download_copy": ("Deskargatu kopia", "Descargar copia"),
    "restore_copy": ("Leheneratu kopia", "Restaurar copia"),
    #Administration
    "invite_link": ("Gonbidapen-esteka, 72 orduz eta behin bakarrik balio duena. Orain bakarrik "
                    "erakusten da:",
                    "Enlace de invitación, válido 72 horas y un solo uso. Solo se muestra ahora:"),
    "new_person": ("Pertsona berria", "Nueva persona"),
    "first_name": ("Izena", "Nombre de pila"),
    "club": ("Kluba", "Club"),
    "create_invite": ("Sortu gonbidapena", "Crear invitación"),
    "people": ("Pertsonak", "Personas"),
    "devices": ("{n} gailu", "{n} dispositivo(s)"),
    "invite_device": ("Gonbidatu beste gailu bat", "Invitar otro dispositivo"),
    "remove_devices": ("Kendu gailuak", "Quitar dispositivos"),
    "delete": ("Ezabatu", "Borrar"),
    #Privacy
    "privacy_intro": ("Tresna honek Arabako klubetako arduradunei taulen ordena egiaztatzen "
                      "laguntzen die. Ez da federazioaren zerbitzua, eta bidalketa ofiziala "
                      "posta elektronikoz egiten da oraindik ere.",
                      "Esta herramienta ayuda a responsables de clubes alaveses a comprobar un "
                      "orden de fuerzas. No es un servicio de la federación, y el envío oficial "
                      "sigue siendo por correo."),
    "privacy_players": ("<strong>Jokalariak:</strong> izena, ELOa, egoera eta IDa, FIDEren "
                        "zerrenda publikotik hartuta. Ez da jaiotze-urterik ez sexurik gordetzen.",
                        "<strong>Jugadores:</strong> nombre, ELO, estado e ID, tomados de la lista "
                        "pública de la FIDE. No se guarda el año de nacimiento ni el sexo."),
    "privacy_orders": ("<strong>Taulen ordenak:</strong> zerbitzariak egiaztatu egiten ditu, "
                       "baina ez ditu gordetzen. Gordetzea aktibatzen baduzu, gailu honetan "
                       "bakarrik geratzen dira.",
                       "<strong>Órdenes de fuerzas:</strong> el servidor los comprueba y no los "
                       "conserva. Si activas el guardado, se quedan solo en este dispositivo."),
    "privacy_accounts": ("<strong>Kontuak:</strong> izena, kluba eta zifratutako pasahitza.",
                         "<strong>Cuentas:</strong> nombre de pila, club y contraseña cifrada."),
    "privacy_language": ("<strong>Hizkuntza:</strong> cookie batek gogoratzen du zein hizkuntza "
                         "aukeratu duzun.",
                         "<strong>Idioma:</strong> una cookie recuerda el idioma que has elegido."),
    "privacy_contact": ("Datuak zuzendu edo kentzeko, hitz egin sarbidea eman dizun pertsonarekin.",
                        "Para corregir o retirar datos, habla con la persona que te dio acceso."),
}

#Texts used by the browser, in app.js
BROWSER_TEXTS = {
    "no_elo": ("ELOrik gabe", "sin ELO"),
    "inactive": ("ez-aktiboa", "inactivo"),
    "move_up": ("Igo: {name}", "Subir a {name}"),
    "move_down": ("Jaitsi: {name}", "Bajar a {name}"),
    "remove": ("Kendu: {name}", "Quitar a {name}"),
    "max_players": ("Gehienez {n} jokalari", "Máximo {n} jugadores"),
    "too_many_requests": ("Eskaera gehiegi, itxaron minutu bat",
                          "Demasiadas peticiones, espera un minuto"),
    "session_expired": ("Saioa iraungi da", "Sesión caducada"),
    "server_error": ("Zerbitzariaren errorea", "Error del servidor"),
    "nothing_found": ("Ez dago ezer hitz horiekin. Saiatu beste batzuekin, edo gehitu ELOrik gabe.",
                      "Nada con esas palabras. Prueba con otras, o añádelo sin ELO."),
    "fide_profile": ("Ikusi FIDEko fitxa", "Ver ficha en FIDE"),
    "more_results": ("Emaitza gehiago daude: gehitu beste hitz bat.",
                     "Hay más resultados: añade otra palabra."),
    "numbers_only": ("Zenbakiak bakarrik, mesedez", "Solo números, por favor"),
    "ids_missing": ("Aurkitu ez diren IDak laukian geratzen dira: {ids}",
                    "IDs no encontrados, se quedan en la casilla: {ids}"),
    "order_right": ("✓ Ordena zuzena da", "✓ El orden es correcto"),
    "order_wrong": ("✗ Ordenak ez du balio", "✗ El orden no es válido"),
    "error_no_elo": ("{upper}. taula (ELOrik gabe) {lower}. taularen aurretik ({rating})",
                     "Tablero {upper} (sin ELO) por delante de tablero {lower} ({rating})"),
    "error_points": ("{upper}. taula ({upper_rating}) {lower}. taularen aurretik "
                     "({lower_rating}): {points} puntu",
                     "Tablero {upper} ({upper_rating}) por delante de tablero {lower} "
                     "({lower_rating}): {points} puntos"),
    "checked_with": ("FIDE zerrendarekin egiaztatuta: {list}.",
                     "Comprobado con la lista FIDE de {list}."),
    "club_players": ("Zure klubeko jokalariak, {season} ({n})",
                     "Jugadores de tu club en {season} ({n})"),
    "open": ("Ireki", "Abrir"),
    "open_team": ("Ireki: {name}", "Abrir {name}"),
    "delete_team": ("Ezabatu: {name}", "Borrar {name}"),
    "delete_label": ("Ezabatu", "Borrar"),
    "confirm_delete": ("Gailu honetan gordetako {n} talde ezabatuko dira. Jarraitu?",
                       "Se borrarán {n} equipos guardados en este dispositivo. ¿Seguir?"),
    "team_needs_name": ("Jarri izena taldeari", "Ponle un nombre al equipo"),
    "team_empty": ("Taldea hutsik dago", "El equipo está vacío"),
    "no_saved_teams": ("Ez dago gordetako talderik", "No hay equipos guardados"),
    "restored": ("{n} talde leheneratu dira", "Restaurados {n} equipos"),
    "bad_file": ("Fitxategi horrek ez du balio: aukeratu Deskargatu kopia sakatuta lortu duzun "
                 ".json fitxategia",
                 "Ese fichero no sirve: elige el .json que obtuviste con Descargar copia"),
    "column_team": ("Taldea", "Equipo"),
    "column_board": ("Taula", "Tablero"),
    "column_player": ("Jokalaria", "Jugador"),
    "default_team": ("Taldea", "Equipo"),
    "excel_file": ("taulen-ordena.xlsx", "ordenes-de-fuerzas.xlsx"),
    "sheet_name": ("Taldeak", "Equipos"),
}


def text(language, key, **values):
    '''
    Returns a text in a language, with its {values} filled in
    '''
    pair = TEXTS.get(key) or BROWSER_TEXTS[key]
    return pair[LANGUAGES.index(language)].format(**values)


def browser_texts(language):
    '''
    Returns the texts the browser needs, with their {values} left for it
    '''
    return {key: pair[LANGUAGES.index(language)] for key, pair in BROWSER_TEXTS.items()}


def month_label(language, year, month):
    '''
    Returns a month in words: "2026ko urria" or "octubre de 2026"
    '''
    name = MONTHS[language][month - 1]
    return f"{year}ko {name}" if language == "eu" else f"{name} de {year}"
