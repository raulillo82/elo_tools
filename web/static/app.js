// The board order only lives here, in the browser. The server gets the FIDE
// IDs to check them and doesn't keep them. Players typed by hand are sent as
// null, so their names never leave this device.
"use strict";
const csrf = document.querySelector('meta[name="csrf"]').content;
const $ = (id) => document.getElementById(id);
const userId = $("list-label").dataset.user;
const SAVE_KEY = `elo-orders-${userId}`;
const ENABLED_KEY = `elo-save-${userId}`;
const MAX_PLAYERS = 30;
let team = []; // {id, name, rating, inactive}. id is null for players typed by hand
let searchTimer = null;
let roster = []; // Last season's players of the club of this user

async function post(path, body) {
  const base = location.pathname.replace(/\/$/, "");
  const response = await fetch(`${base}/api/${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRF": csrf},
    body: JSON.stringify(body),
  });
  if (response.status === 429) throw new Error("Demasiadas peticiones, espera un minuto");
  if (response.status === 401) { location.reload(); throw new Error("Sesión caducada"); }
  if (!response.ok) throw new Error("Error del servidor");
  return response.json();
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function button(text, title, action) {
  const node = element("button", text);
  node.type = "button";
  node.title = title;
  node.setAttribute("aria-label", title);
  node.addEventListener("click", action);
  return node;
}

function clearVerdict() {
  $("verdict").replaceChildren();
}

function move(index, step) {
  const target = index + step;
  if (target < 0 || target >= team.length) return;
  [team[index], team[target]] = [team[target], team[index]];
  clearVerdict();
  render();
}

function render(wrong = new Set()) {
  const list = $("players");
  list.replaceChildren();
  team.forEach((player, index) => {
    const row = element("li");
    if (wrong.has(index + 1)) row.classList.add("wrong");
    row.append(element("span", index + 1, "board"));
    const who = element("div", player.name, "who");
    const parts = [player.rating ?? "sin ELO"];
    if (player.id) parts.push(`ID ${player.id}`);
    if (player.inactive) parts.push("inactivo");
    who.append(element("small", parts.join(" · ")));
    row.append(who);
    const tools = element("div", undefined, "tools");
    tools.append(button("↑", `Subir a ${player.name}`, () => move(index, -1)),
                 button("↓", `Bajar a ${player.name}`, () => move(index, 1)),
                 button("✕", `Quitar a ${player.name}`, () => {
                   team.splice(index, 1); clearVerdict(); render();
                 }));
    row.append(tools);
    list.append(row);
  });
  $("empty").hidden = team.length > 0;
  showRoster();
}

function buildRoster() {
  const area = $("roster");
  area.replaceChildren();
  roster.forEach((player) => {
    const label = element("label", undefined, "check");
    const box = element("input");
    box.type = "checkbox";
    box.dataset.id = player.id;
    box.addEventListener("change", () => {
      if (box.checked) {
        add(player);
      } else {
        team = team.filter((other) => other.id !== player.id);
        clearVerdict();
        render();
      }
    });
    label.append(box, element("span", `${player.name} · ${player.rating ?? "sin ELO"}`));
    area.append(label);
  });
  showRoster();
}

// Rebuilding the list would lose the place in it, so only the marks change
function showRoster() {
  document.querySelectorAll("#roster input").forEach((box) => {
    box.checked = team.some((other) => other.id === Number(box.dataset.id));
  });
}

async function loadRoster() {
  try {
    const answer = await post("roster", {});
    roster = answer.players;
    if (roster.length) {
      $("roster-title").textContent = `Jugadores de tu club en ${answer.season} (${roster.length})`;
      $("roster-area").hidden = false;
      buildRoster();
    }
  } catch {
    // The list is only a help: everything else works without it
  }
}

function add(player) {
  if (team.length >= MAX_PLAYERS) return alert(`Máximo ${MAX_PLAYERS} jugadores`);
  if (player.id && team.some((other) => other.id === player.id)) return;
  team.push(player);
  clearVerdict();
  render();
}

async function search() {
  const text = $("search").value.trim();
  const area = $("results");
  if (text.split(/\s+/).filter((word) => word.length > 1).length < 2) return area.replaceChildren();
  try {
    const answer = await post("search", {text});
    area.replaceChildren();
    if (!answer.results.length) {
      area.append(element("p", "Nada con esas palabras. Prueba con otras, o añádelo sin ELO.", "hint"));
    }
    answer.results.forEach((player) => {
      const option = element("button", undefined, "result");
      option.type = "button";
      const rating = player.rating ?? "sin ELO";
      option.textContent = `${player.name} · ${rating} · ID ${player.id}`;
      option.addEventListener("click", () => {
        add(player);
        $("search").value = "";
        area.replaceChildren();
      });
      area.append(option);
      const link = element("a", "Ver ficha en FIDE", "hint");
      link.href = `https://ratings.fide.com/profile/${player.id}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      area.append(link);
    });
    if (answer.more) area.append(element("p", "Hay más resultados: añade otra palabra.", "hint"));
  } catch (error) {
    area.replaceChildren(element("p", error.message, "hint"));
  }
}

async function addIds() {
  const ids = [...new Set($("ids").value.split(/[\s,;]+/).filter(Boolean))];
  if (ids.some((id) => !/^\d+$/.test(id))) return alert("Solo números, por favor");
  try {
    const answer = await post("lookup", {ids: ids.map(Number)});
    const byId = new Map(answer.players.map((player) => [player.id, player]));
    ids.map(Number).forEach((id) => { if (byId.has(id)) add(byId.get(id)); });
    $("ids").value = answer.missing.join(" ");
    if (answer.missing.length) alert(`IDs no encontrados, se quedan en la casilla: ${answer.missing.join(", ")}`);
  } catch (error) {
    alert(error.message);
  }
}

function addManual() {
  const name = $("manual").value.trim();
  if (!name) return;
  add({id: null, name, rating: null, inactive: false});
  $("manual").value = "";
}

function sortByElo() {
  const rated = team.filter((player) => player.rating !== null);
  const unrated = team.filter((player) => player.rating === null);
  rated.sort((one, other) => other.rating - one.rating);
  team = [...rated, ...unrated];
  clearVerdict();
  render();
}

async function check() {
  const verdict = $("verdict");
  if (!team.length) return;
  try {
    const answer = await post("check", {entries: team.map((player) => player.id)});
    answer.ratings.forEach((rating, index) => {
      if (team[index].id) team[index].rating = rating;
    });
    const wrong = new Set(answer.errors.flatMap((error) => [error.upper, error.lower]));
    render(wrong);
    verdict.replaceChildren();
    const ok = answer.errors.length === 0;
    verdict.append(element("p", ok ? "✓ El orden es correcto" : "✗ El orden no es válido", ok ? "good" : "bad"));
    if (!ok) {
      const list = element("ul");
      answer.errors.forEach((error) => {
        list.append(element("li", error.difference === null
          ? `Tablero ${error.upper} (sin ELO) por delante de tablero ${error.lower} (${error.lower_rating})`
          : `Tablero ${error.upper} (${error.upper_rating}) por delante de tablero ${error.lower} (${error.lower_rating}): ${error.difference} puntos`));
      });
      verdict.append(list);
    }
    verdict.append(element("p", `Comprobado con la lista FIDE de ${answer.list.text}.`, "hint"));
  } catch (error) {
    verdict.replaceChildren(element("p", error.message, "bad"));
  }
}

function savedOrders() {
  return JSON.parse(localStorage.getItem(SAVE_KEY) || "{}");
}

function writeOrders(orders) {
  localStorage.setItem(SAVE_KEY, JSON.stringify(orders));
  showSaved();
}

function showSaved() {
  const enabled = localStorage.getItem(ENABLED_KEY) === "1";
  $("save-enabled").checked = enabled;
  $("saved-area").hidden = !enabled;
  const list = $("saved");
  list.replaceChildren();
  if (!enabled) return;
  Object.entries(savedOrders()).forEach(([name, players]) => {
    const row = element("li");
    row.append(element("span", `${name} (${players.length})`));
    const tools = element("div", undefined, "row");
    tools.append(button("Abrir", `Abrir ${name}`, () => {
      team = players.map((player) => ({...player}));
      $("team-name").value = name;
      clearVerdict();
      render();
    }), button("Borrar", `Borrar ${name}`, () => {
      const orders = savedOrders();
      delete orders[name];
      writeOrders(orders);
    }));
    row.append(tools);
    list.append(row);
  });
}

function setSaving() {
  if ($("save-enabled").checked) {
    localStorage.setItem(ENABLED_KEY, "1");
  } else {
    const count = Object.keys(savedOrders()).length;
    if (count && !confirm(`Se borrarán ${count} equipos guardados en este dispositivo. ¿Seguir?`)) {
      $("save-enabled").checked = true;
      return;
    }
    localStorage.removeItem(SAVE_KEY);
    localStorage.removeItem(ENABLED_KEY);
  }
  showSaved();
}

function saveTeam() {
  const name = $("team-name").value.trim();
  if (!name) return alert("Ponle un nombre al equipo");
  if (!team.length) return alert("El equipo está vacío");
  writeOrders({...savedOrders(), [name]: team});
}

function exportOrders() {
  const link = element("a");
  link.href = URL.createObjectURL(new Blob([JSON.stringify(savedOrders(), null, 2)],
                                           {type: "application/json"}));
  link.download = "ordenes-de-fuerzas.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

function downloadExcel(teams, name) {
  const header = ["Equipo", "Tablero", "Jugador", "ELO FIDE", "ID FIDE"];
  const rows = Object.entries(teams).flatMap(([teamName, players]) => players.map(
    (player, index) => [teamName, index + 1, player.name, player.rating, player.id]));
  const link = element("a");
  link.href = URL.createObjectURL(makeXlsx([header, ...rows], [24, 9, 36, 10, 12]));
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportTeam() {
  if (!team.length) return alert("El equipo está vacío");
  const name = $("team-name").value.trim() || "Equipo";
  downloadExcel({[name]: team}, `${name.replace(/[^\p{L}\p{N}]+/gu, "-")}.xlsx`);
}

function exportAll() {
  const orders = savedOrders();
  if (!Object.keys(orders).length) return alert("No hay equipos guardados");
  downloadExcel(orders, "ordenes-de-fuerzas.xlsx");
}

function validPlayer(player) {
  return player && typeof player.name === "string" && (player.id === null || Number.isInteger(player.id))
    && (player.rating === null || Number.isInteger(player.rating));
}

async function importOrders(event) {
  const [file] = event.target.files;
  if (!file) return;
  try {
    const orders = JSON.parse(await file.text());
    const fine = Object.values(orders).every((players) => Array.isArray(players) && players.every(validPlayer));
    if (!fine) throw new Error();
    writeOrders({...savedOrders(), ...orders});
    alert(`Restaurados ${Object.keys(orders).length} equipos`);
  } catch {
    alert("Ese fichero no sirve: elige el .json que obtuviste con Descargar copia");
  }
  event.target.value = "";
}

$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(search, 400);
});
$("add-ids").addEventListener("click", addIds);
$("add-manual").addEventListener("click", addManual);
$("sort").addEventListener("click", sortByElo);
$("check").addEventListener("click", check);
$("clear").addEventListener("click", () => { team = []; clearVerdict(); render(); });
$("save-enabled").addEventListener("change", setSaving);
$("save").addEventListener("click", saveTeam);
$("export").addEventListener("click", exportOrders);
$("excel").addEventListener("click", exportTeam);
$("excel-all").addEventListener("click", exportAll);
$("import").addEventListener("change", importOrders);
render();
showSaved();
loadRoster();
