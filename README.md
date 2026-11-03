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
- `Var. desde octubre de 2026` es la diferencia de ELO FIDE con la lista de ese mes,
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
  pueden descargar en Excel, también para Google Sheets, o en una copia de seguridad
  para pasarlos a otro dispositivo.
- **Liga Vasca:** `web/rosters.py` añade quienes jugaron División de Honor y Primera,
  según Chess Results, en `rosters_basque.json`. Cada club ve el filtro solo si tiene datos.
- **Jugadores de la temporada pasada:** `web/rosters.py` guarda club e ID, y cada
  responsable solo ve los de su club. Cada año hay que cambiar en ese archivo la
  temporada y los torneos, y ejecutarlo.
- **Nombre del equipo:** basta con escribir `a` o `rey`: se añade el club y la
  mayúscula. Si se deja vacío, toma la primera letra libre entre los equipos
  guardados en ese dispositivo.
- **Idiomas:** euskera, que es el idioma por defecto, y castellano. La web recuerda
  el que eligió cada persona. Los textos están en `web/i18n.py`.
- **Modo nocturno:** sigue el ajuste del dispositivo hasta que la persona elige
  claro u oscuro en la cabecera. Esa elección se recuerda igual que el idioma.
- **Accesos:** solo por invitación de un uso. Cada persona tiene hasta dos
  dispositivos y un club, y cada club una persona.

### Comandos en el servidor

```
python3 -m web.manage invite /data Nombre "Club"   # nueva persona
python3 -m web.manage device /data "Club"          # invitación para otro dispositivo
python3 -m web.manage reset /data "Club"           # olvida sus dispositivos
```

La configuración de despliegue está en `web/deploy/`.

### Despliegue automático

`main` no acepta cambios sin una PR con los tests en verde. El servidor consulta
`main` cada 5 minutos con `elo-deploy.timer` y despliega si ha cambiado algo de la
web. Si la versión nueva no responde, vuelve a la anterior. Es el servidor quien
pregunta, así que GitHub no puede ejecutar nada en él. El script vive en
`~/.local/bin`: si cambia, hay que copiarlo a mano.

### Staging

Entorno de pruebas en `https://staging.raulillo82.duckdns.org/elo/`, separado de
producción por el navegador: otro dominio, así que no ve sus cookies ni los equipos
guardados.

- **Qué se despliega:** la rama `staging` si existe, y `main` si no. Para probar algo,
  `git push origin feat/x:staging`, o `--force` para sustituir lo que haya. Al acabar,
  `git push origin --delete staging`. La Pi lo comprueba cada 5 minutos.
- **Acceso:** se da desde `Accesos` en producción, por días. Quien lo tiene ve el enlace
  `Pruebas` y entra sin contraseña: producción firma un permiso de un solo uso que dura
  un minuto. Para cortar una sesión ya abierta, borra la cuenta en el admin de staging.
- **Datos:** copias de las listas de producción, nunca `accounts.db`.
- **Límites:** `elo-staging-deploy.sh` nunca instala nada del repositorio fuera de la
  imagen, porque staging ejecuta código sin fusionar.

Se monta una vez en el servidor:

```bash
mkdir -p ~/elo-web-staging/data ~/elo-web-staging/secrets
git clone https://github.com/raulillo82/elo_tools.git ~/elo-web-staging/repo
openssl rand -hex 32 > ~/elo-web-staging/secrets/secret.key
openssl rand -hex 32 > ~/elo-web-staging/secrets/staging.key
cp ~/elo-web-staging/secrets/staging.key ~/elo-web/secrets/
chmod 600 ~/elo-web-staging/secrets/* ~/elo-web/secrets/staging.key
cp ~/elo-web-staging/repo/web/deploy/elo-staging-deploy.sh ~/.local/bin/
systemctl --user enable --now elo-staging-deploy.timer
systemctl --user enable elo-staging.service
```

Además hacen falta el certificado de `staging.raulillo82.duckdns.org` y
`web/deploy/nginx-staging.conf` en `/etc/nginx/conf.d/`.

## Tests

```
python3 -m unittest
node --test "web/tests/*.test.js"
```

GitHub los ejecuta en cada PR, en sus propias máquinas. Para los de la web hacen
falta las librerías de `web/requirements.txt`.
