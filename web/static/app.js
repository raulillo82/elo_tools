// The board order only lives here, in the browser. The server gets the FIDE
// IDs to check them and doesn't keep them. Players typed by hand are sent as
// null, so their names never leave this device.
"use strict";
const csrf = document.querySelector('meta[name="csrf"]').content;
const $ = (id) => document.getElementById(id);
const userId = $("list-label").dataset.user;
const club = $("list-label").dataset.club;
const SAVE_KEY = `elo-orders-${userId}`;
const ENABLED_KEY = `elo-save-${userId}`;
const DRAFT_KEY = "elo-draft";
const MAX_PLAYERS = 30;
const TEXTS = JSON.parse($("texts").textContent);
let team = []; // {id, name, rating, inactive}. id is null for players typed by hand
let searchTimer = null;
let roster = []; // Last season's players of the club of this user
let openedTeam = null; // The saved team being edited, which can be saved again

function t(key, values = {}) {
  return TEXTS[key].replace(/\{(\w+)\}/g, (_, name) => values[name]);
}

async function post(path, body) {
  const base = location.pathname.replace(/\/$/, "");
  const response = await fetch(`${base}/api/${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRF": csrf},
    body: JSON.stringify(body),
  });
  if (response.status === 429) throw new Error(t("too_many_requests"));
  if (response.status === 401) { location.reload(); throw new Error(t("session_expired")); }
  if (!response.ok) throw new Error(t("server_error"));
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
    const parts = [player.rating ?? t("no_elo")];
    if (player.id) parts.push(`ID ${player.id}`);
    if (player.inactive) parts.push(t("inactive"));
    who.append(element("small", parts.join(" · ")));
    row.append(who);
    const tools = element("div", undefined, "tools");
    tools.append(button("↑", t("move_up", {name: player.name}), () => move(index, -1)),
                 button("↓", t("move_down", {name: player.name}), () => move(index, 1)),
                 button("✕", t("remove", {name: player.name}), () => {
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
    label.append(box, element("span", `${player.name} · ${player.rating ?? t("no_elo")}`));
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
      $("roster-title").textContent = t("club_players", {season: answer.season, n: roster.length});
      $("roster-area").hidden = false;
      buildRoster();
    }
  } catch {
    // The list is only a help: everything else works without it
  }
}

function add(player) {
  if (team.length >= MAX_PLAYERS) return alert(t("max_players", {n: MAX_PLAYERS}));
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
      area.append(element("p", t("nothing_found"), "hint"));
    }
    answer.results.forEach((player) => {
      const option = element("button", undefined, "result");
      option.type = "button";
      const rating = player.rating ?? t("no_elo");
      option.textContent = `${player.name} · ${rating} · ID ${player.id}`;
      option.addEventListener("click", () => {
        add(player);
        $("search").value = "";
        area.replaceChildren();
      });
      area.append(option);
      const link = element("a", t("fide_profile"), "hint");
      link.href = `https://ratings.fide.com/profile/${player.id}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      area.append(link);
    });
    if (answer.more) area.append(element("p", t("more_results"), "hint"));
  } catch (error) {
    area.replaceChildren(element("p", error.message, "hint"));
  }
}

async function addIds() {
  const ids = [...new Set($("ids").value.split(/[\s,;]+/).filter(Boolean))];
  if (ids.some((id) => !/^\d+$/.test(id))) return alert(t("numbers_only"));
  try {
    const answer = await post("lookup", {ids: ids.map(Number)});
    const byId = new Map(answer.players.map((player) => [player.id, player]));
    ids.map(Number).forEach((id) => { if (byId.has(id)) add(byId.get(id)); });
    $("ids").value = answer.missing.join(" ");
    if (answer.missing.length) alert(t("ids_missing", {ids: answer.missing.join(", ")}));
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
    verdict.append(element("p", t(ok ? "order_right" : "order_wrong"), ok ? "good" : "bad"));
    if (!ok) {
      const list = element("ul");
      answer.errors.forEach((error) => {
        list.append(element("li", error.difference === null
          ? t("error_no_elo", {upper: error.upper, lower: error.lower, rating: error.lower_rating})
          : t("error_points", {upper: error.upper, upper_rating: error.upper_rating,
                               lower: error.lower, lower_rating: error.lower_rating,
                               points: error.difference})));
      });
      verdict.append(list);
    }
    verdict.append(element("p", t("checked_with", {list: answer.list.text}), "hint"));
  } catch (error) {
    verdict.replaceChildren(element("p", error.message, "bad"));
  }
}

// The first letter not used by a saved team, so a saved "B" leaves "A" free
function nextTeamName() {
  const used = new Set(Object.keys(savedOrders()).map((name) => name.trim().toUpperCase()));
  const clubName = club.toUpperCase();
  for (const letter of "ABCDEFGHIJKLMNOPQRSTUVWXYZ") {
    if (!used.has(letter) && !used.has(`${clubName} ${letter}`)) return `${club} ${letter}`;
  }
  return club;
}

// Finds the club at the start of a name, whatever its case, accents or spaces
function clubPrefix() {
  const words = club.split(/\s+/).map((word) => [...word].map((letter) =>
    `${letter.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\p{M}*`).join(""));
  return new RegExp(`^${words.join("\\s*")}(?=\\s|$)`, "iu");
}

// "rey", "san viator rey" and "SAN VIATOR Rey" all become "San Viator Rey".
// Returns "" if there's nothing but the club, which means the default name
function fullTeamName(text) {
  const clean = text.normalize("NFD").trim().replace(clubPrefix(), "").trim().replace(/\s+/g, " ");
  const label = clean.normalize("NFC");
  if (!label) return "";
  return `${club} ${label[0].toLocaleUpperCase("es")}${label.slice(1)}`;
}

function teamName() {
  return fullTeamName($("team-name").value) || nextTeamName();
}

function showTeamHint() {
  const name = nextTeamName();
  $("team-name").placeholder = name;
  $("team-hint").textContent = t("team_hint", {club, name});
}

function savedOrders() {
  return JSON.parse(localStorage.getItem(SAVE_KEY) || "{}");
}

function writeOrders(orders) {
  localStorage.setItem(SAVE_KEY, JSON.stringify(orders));
  showSaved();
}

function showSaved() {
  showTeamHint();
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
    tools.append(button(t("open"), t("open_team", {name}), () => {
      team = players.map((player) => ({...player}));
      $("team-name").value = name;
      openedTeam = name;
      clearVerdict();
      render();
    }), button(t("delete_label"), t("delete_team", {name}), () => {
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
    if (count && !confirm(t("confirm_delete", {n: count}))) {
      $("save-enabled").checked = true;
      return;
    }
    localStorage.removeItem(SAVE_KEY);
    localStorage.removeItem(ENABLED_KEY);
  }
  showSaved();
}

function saveTeam() {
  if (!team.length) return alert(t("team_empty"));
  const name = teamName();
  const exists = Object.hasOwn(savedOrders(), name);
  if (exists && name !== openedTeam && !confirm(t("confirm_replace", {name}))) return;
  $("team-name").value = name;
  openedTeam = name;
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

// FIDE adds the birth year to tell namesakes apart: "Soto, Ana 1987 II". The
// file has the FIDE ID for that. Names typed by hand are left as they are
function exportedName(player) {
  return player.id ? player.name.replace(/\s+\d{4}(\s+[IVX]+)?$/i, "") : player.name;
}

function downloadExcel(teams, name) {
  const header = [t("column_team"), t("column_board"), t("column_player"), "ELO FIDE", "ID FIDE"];
  const rows = Object.entries(teams).flatMap(([teamName, players]) => players.map(
    (player, index) => [teamName, index + 1, exportedName(player), player.rating, player.id]));
  const link = element("a");
  link.href = URL.createObjectURL(makeXlsx([header, ...rows], [24, 9, 36, 10, 12], t("sheet_name")));
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportTeam() {
  if (!team.length) return alert(t("team_empty"));
  const name = teamName();
  downloadExcel({[name]: team}, `${name.replace(/[^\p{L}\p{N}]+/gu, "-")}.xlsx`);
}

function exportAll() {
  const orders = savedOrders();
  if (!Object.keys(orders).length) return alert(t("no_saved_teams"));
  downloadExcel(orders, t("excel_file"));
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
    alert(t("restored", {n: Object.keys(orders).length}));
  } catch {
    alert(t("bad_file"));
  }
  event.target.value = "";
}

$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(search, 400);
});
$("team-name").addEventListener("change", () => {
  $("team-name").value = fullTeamName($("team-name").value);
});
$("add-ids").addEventListener("click", addIds);
$("add-manual").addEventListener("click", addManual);
$("sort").addEventListener("click", sortByElo);
$("check").addEventListener("click", check);
$("clear").addEventListener("click", () => {
  team = [];
  openedTeam = null;
  $("team-name").value = "";
  clearVerdict();
  render();
});
$("save-enabled").addEventListener("change", setSaving);
$("save").addEventListener("click", saveTeam);
$("export").addEventListener("click", exportOrders);
$("excel").addEventListener("click", exportTeam);
$("excel-all").addEventListener("click", exportAll);
$("import").addEventListener("change", importOrders);
// Changing the language reloads the page: keep the team being built. This
// copy only lasts until the page is back, and it's not the "save" option
document.querySelector(".languages").addEventListener("submit", () => {
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify({name: $("team-name").value, team}));
});
const draft = sessionStorage.getItem(DRAFT_KEY);
sessionStorage.removeItem(DRAFT_KEY);
if (draft) {
  const restored = JSON.parse(draft);
  $("team-name").value = restored.name;
  team = restored.team;
}
render();
showSaved();
loadRoster();
