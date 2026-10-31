# elo_tools

Consulta los ELOs de ajedrez de la lista FIDE y de la lista de la Federación
Vasca, y los muestra juntos. Son listas distintas con valores que no tienen
relación entre sí: el programa nunca compara un ELO con el otro.

## Instalación

Necesita Python 3.10 o superior y las librerías de `requirements.txt`. En
openSUSE:

```
sudo zypper install python313-pandas python313-lxml python313-pyarrow python313-dbfread
```

## Uso

Sin argumentos muestra un menú:

```
python3 elo.py
```

También se puede pedir un listado directamente:

```
python3 elo.py jugadores              # los jugadores de players.txt
python3 elo.py club "san viator"      # un club, sin importar las mayúsculas
python3 elo.py buscar mata            # busca en las dos listas
python3 elo.py buscar 12345678        # busca por ID FIDE
```

Opciones de los listados, que en el menú son las opciones 4, 5 y 6:

- `--activos`: oculta a quienes FIDE marca como inactivos.
- `--solo-fide`: oculta a quienes no tienen ELO FIDE.
- `--csv`: guarda el listado en `exports/`, listo para abrir con Excel.

Por ejemplo, una posible alineación de un club:

```
python3 elo.py club "san viator" --activos --solo-fide
```

## Cómo leer los listados

- Un `?` junto a un ELO indica que el nombre no coincide del todo, o que hay
  homónimos. Debajo de la tabla se explica cada caso, en "A revisar".
- `varios?` significa que hay más de un jugador FIDE posible.
- `Var. desde 29/9/2026` es la diferencia de ELO FIDE con la lista de esa fecha,
  y `=` que no ha cambiado. Se queda vacío para quien no estaba en esa lista como jugador
  español, porque el histórico solo guarda a los españoles.

## El archivo players.txt

Contiene los jugadores de "Mis jugadores", uno por línea, con su nombre tal como
aparece en FIDE o con su ID FIDE. Lo que va detrás de `#` es un comentario. No
se sube a GitHub.

```
Apellido1 Apellido2, Nombre
12345678  # Comentario para saber quién es
```

El ID FIDE es lo más seguro para homónimos o nombres mal escritos.

## Los datos

- **Lista FIDE:** se guarda procesada en `fide_cache.parquet`, y solo se vuelve
  a descargar si FIDE publica una nueva.
- **Histórico:** cada lista FIDE nueva guarda los ELOs de los jugadores
  españoles en `fide_history/`, con un archivo por lista. Sirve para calcular
  `Var.`, así que conviene no borrarlo.
- **Archivo:** `fide_archive/` guarda listas FIDE mensuales completas, tal como
  las publica FIDE. El programa no las usa por ahora.
- **Lista vasca:** es `elovasco.zip`, de enero de 2022. El programa no comprueba
  si hay otra más reciente.

### Actualizar la lista vasca

1. Sustituye `elovasco.zip` por el archivo nuevo.
2. Borra la carpeta que tenía extraída, por ejemplo `Enero2022/`.
3. Cambia `ELOVASCO_DATE` en `elo_basque.py`.

## Estructura

| Archivo | Qué hace |
|---|---|
| `elo.py` | La consola: menú, tablas y argumentos |
| `elo_reports.py` | Los listados, como datos. Una futura web usaría esto |
| `elo_common.py` | Descarga de la lista FIDE y búsqueda de nombres |
| `elo_basque.py` | Descarga y lectura de la lista vasca |
| `elo_history.py` | Histórico de ELOs FIDE |
| `elo_names.py` | Comparación de nombres, sin dependencias |
| `web/` | La web de orden de fuerzas |

## La web: orden de fuerzas

`web/` es una herramienta aparte para que cada responsable de club compruebe el
orden de fuerzas de sus equipos desde el móvil. No sustituye al envío oficial,
que sigue siendo por correo a la federación.

- **Reglas:** están en `web/rules.py`. Un jugador solo puede ir delante de otro
  con más ELO si la diferencia es de 50 puntos o menos, y los jugadores sin ELO
  van después de los que tienen ELO. El margen se cambia con `ELO_MARGIN`.
- **Comprobación por equipo:** los capitanes eligen libremente quién juega en
  cada equipo, así que no se comparan equipos entre sí.
- **Lista FIDE:** usa la más nueva, o la que indique `ELO_LIST` (por ejemplo
  `2027-01`). Solo contiene nombre, ELO, estado e ID: nunca el año de nacimiento
  ni el sexo. La actualiza cada noche `elo-list-update.timer`.
- **Órdenes de fuerzas:** el servidor los comprueba y no los guarda. El guardado
  es opcional, está desactivado por defecto y se queda en el navegador. Se
  pueden descargar en CSV para Excel o Google Sheets, o en una copia de seguridad
  para pasarlos a otro dispositivo.
- **Jugadores de la temporada pasada:** `web/rosters.py` guarda club e ID, y cada
  responsable solo ve los de su club. Cada año hay que cambiar en ese archivo la
  temporada y los torneos, y ejecutarlo.
- **Accesos:** solo por invitación de un uso. Cada persona tiene hasta dos
  dispositivos y un club, y cada club una persona.

### Comandos en el servidor

```
python3 -m web.manage invite /data Nombre "Club"   # nueva persona
python3 -m web.manage device /data "Club"          # invitación para otro dispositivo
python3 -m web.manage reset /data "Club"           # olvida sus dispositivos
```

La configuración de despliegue está en `web/deploy/`.

## Tests

```
python3 -m unittest
```

GitHub los ejecuta en cada PR, en sus propias máquinas. Para los de la web hacen
falta las librerías de `web/requirements.txt`.
