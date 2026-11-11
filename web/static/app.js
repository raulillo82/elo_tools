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
const MARGIN = Number($("list-label").dataset.margin);
const TEXTS = JSON.parse($("texts").textContent);
const JANUARY = Number($("list-label").dataset.january) || null; // The year of the January compared with
let team = []; // {id, name, rating, inactive}. id is null for players typed by hand
// FIDE ID -> January rating, or null if they had none. Only in memory, so
// saved teams never keep an old one
const januaries = new Map();
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

// Takes "january" out of the players the server sends, into januaries
function remember(players) {
  players.forEach((player) => {
    if ("january" in player) januaries.set(player.id, player.january);
    delete player.january;
  });
  return players;
}

function rememberChecked(players, answer) {
  if (!answer.januaries) return;
  players.forEach((player, index) => { if (player.id) januaries.set(player.id, answer.januaries[index]); });
}

// "(+45)" in green, "(−30)" in red. The notice at the top says since when
function changeTag(player) {
  if (!player.id || !januaries.has(player.id)) return null;
  const january = januaries.get(player.id);
  const change = eloChange(player.rating, january);
  if (!change) return null;
  const tag = element("span", `(${change.text ?? t("new_rating")})`, `change ${change.kind}`);
  tag.title = january === null ? t("no_january", {year: JANUARY})
    : t("january_was", {year: JANUARY, rating: january});
  return tag;
}

function withChange(node, player) {
  const tag = changeTag(player);
  if (tag) node.append(" ", tag);
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

function rangeTag({first, last}) {
  const tag = element("span", `↕ ${first}–${last}`);
  tag.setAttribute("role", "img");
  tag.title = t("range", {first, last});
  tag.setAttribute("aria-label", tag.title);
  return tag;
}

// The arrow stays usable when it breaks the rule, or a wrong order couldn't be
// fixed step by step: it only looks faded
function arrow(text, title, index, step, range) {
  const board = index + 1 + step;
  const edge = board < 1 || board > team.length;
  const breaks = range !== null && !edge && (board < range.first || board > range.last);
  const node = button(text, breaks ? `${title}: ${t("breaks_rule")}` : title, () => move(index, step));
  if (edge || breaks) node.classList.add("faded");
  return node;
}

// Drag a row by its grip to any board. Pointer events work with a mouse and a
// finger alike. A faded copy of the row follows the pointer, and the row
// itself waits as a gap where it would land. The copy shows in yellow while
// that place breaks the rule, but it can be dropped there, like with the
// arrows. Keyboards use the arrows
function startDrag(event, from) {
  if (event.button !== 0) return;
  event.preventDefault();
  const list = $("players");
  const rows = [...list.children];
  const dragged = rows[from];
  const others = rows.filter((row) => row !== dragged);
  const ratings = team.map((player) => player.rating ?? null);
  const done = new AbortController();
  let to = from;
  const {pointerId} = event;
  // The finger hides the row on a phone, so the line under the list says it too
  const status = $("live-status");
  const before = [status.textContent, status.hidden, status.classList.contains("warning")];
  const tell = (breaks) => {
    status.hidden = false;
    status.classList.toggle("warning", breaks);
    status.textContent = breaks ? t("drag_breaks", {margin: MARGIN}) : t("drag_fine");
  };
  // Positions set from here are allowed by the CSP, unlike style attributes
  const box = dragged.getBoundingClientRect();
  const grab = event.clientY - box.top;
  const ghost = element("ol", undefined, "ghost");
  ghost.setAttribute("aria-hidden", "true");
  ghost.append(dragged.cloneNode(true));
  ghost.style.left = `${box.left}px`;
  ghost.style.width = `${box.width}px`;
  ghost.style.top = `${box.top}px`;
  document.body.append(ghost);
  dragged.classList.add("dragging");
  tell(false);
  // On the window: moving the row in the page drops a capture on the grip
  addEventListener("pointermove", ({clientY, pointerId: id}) => {
    if (id !== pointerId) return;
    ghost.style.top = `${clientY - grab}px`;
    if (clientY < 40) scrollBy(0, -12);
    else if (clientY > innerHeight - 40) scrollBy(0, 12);
    let place = others.findIndex((row) => {
      const box = row.getBoundingClientRect();
      return clientY < box.top + box.height / 2;
    });
    if (place === -1) place = others.length;
    if (place === to) return;
    to = place;
    list.insertBefore(dragged, others[place] ?? null);
    [...list.children].forEach((row, index) => { row.querySelector(".board").textContent = index + 1; });
    const breaks = moveBreaks(ratings, from, to, MARGIN);
    ghost.firstChild.classList.toggle("breaks", breaks);
    ghost.firstChild.querySelector(".board").textContent = to + 1;
    tell(breaks);
  }, {signal: done.signal});
  const drop = ({type, pointerId: id}) => {
    if (id !== pointerId) return;
    done.abort();
    ghost.remove();
    if (type === "pointerup" && to !== from) {
      team = moveTo(team, from, to);
      clearVerdict();
      render();
    } else if (to !== from) {
      render();
    } else {
      dragged.classList.remove("dragging");
      [status.textContent, status.hidden] = before;
      status.classList.toggle("warning", before[2]);
    }
  };
  addEventListener("pointerup", drop, {signal: done.signal});
  addEventListener("pointercancel", drop, {signal: done.signal});
}

// The quiet help while building a team. The result of Comprobar takes its place
function showLiveStatus(problems, checked) {
  const status = $("live-status");
  status.hidden = checked || team.length < 2;
  status.classList.toggle("warning", problems.count > 0);
  status.textContent = problems.count ? t("live_wrong", {n: problems.count}) : t("live_right");
}

// wrong has the boards that the server rejected, once it has checked them
function render(wrong = null) {
  const list = $("players");
  list.replaceChildren();
  const ratings = team.map((player) => player.rating ?? null);
  const right = orderIsRight(ratings, MARGIN); // Otherwise the ranges mean nothing
  const problems = orderProblems(ratings, MARGIN);
  let anyRange = false;
  team.forEach((player, index) => {
    const range = right ? boardRange(ratings, index, MARGIN) : null;
    const row = element("li");
    if (wrong?.has(index + 1)) row.classList.add("wrong");
    if (!wrong && problems.boards.has(index + 1)) row.classList.add("doubtful");
    const grip = element("span", "⠿", "grip");
    grip.title = t("drag", {name: player.name});
    grip.setAttribute("aria-hidden", "true");
    grip.addEventListener("pointerdown", (event) => startDrag(event, index));
    row.append(grip, element("span", index + 1, "board"));
    const who = element("div", player.name, "who");
    const details = withChange(element("small", player.rating ?? t("no_elo")), player);
    if (range && range.first < range.last) {
      anyRange = true;
      details.append(" · ", rangeTag(range));
    }
    const parts = [];
    if (player.id) parts.push(`ID ${player.id}`);
    if (player.inactive) parts.push(t("inactive"));
    details.append(parts.map((part) => ` · ${part}`).join(""));
    who.append(details);
    row.append(who);
    const tools = element("div", undefined, "tools");
    tools.append(arrow("↑", t("move_up", {name: player.name}), index, -1, range),
                 arrow("↓", t("move_down", {name: player.name}), index, 1, range),
                 button("✕", t("remove", {name: player.name}), () => {
                   team.splice(index, 1); clearVerdict(); render();
                 }));
    row.append(tools);
    list.append(row);
  });
  $("empty").hidden = team.length > 0;
  $("range-hint").hidden = !anyRange;
  showLiveStatus(problems, wrong !== null);
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
        const {leagues, ...saved} = player; // Teams keep what they always had
        add(saved);
      } else {
        team = team.filter((other) => other.id !== player.id);
        clearVerdict();
        render();
      }
    });
    label.dataset.leagues = player.leagues.join(" ");
    label.append(box, withChange(element("span", `${player.name} · ${player.rating ?? t("no_elo")}`), player));
    if (hasBasqueLeague(roster)) {
      label.append(element("small", player.leagues.map((league) => t(`tag_${league}`)).join(" · ")));
    }
    area.append(label);
  });
  showRoster();
}

function filterRoster() {
  const choice = document.querySelector('input[name="roster-league"]:checked').value;
  document.querySelectorAll("#roster label").forEach((label) => {
    label.hidden = !inLeagues(label.dataset.leagues.split(" "), choice);
  });
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
    roster = remember(answer.players);
    if (roster.length) {
      $("roster-title").textContent = t("club_players", {season: answer.season, n: roster.length});
      $("roster-area").hidden = false;
      $("roster-filter").hidden = !hasBasqueLeague(roster);
      buildRoster();
      document.querySelectorAll('input[name="roster-league"]').forEach((radio) => {
        radio.addEventListener("change", filterRoster);
      });
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
    remember(answer.results);
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
    remember(answer.players);
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
    rememberChecked(team, answer);
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

function defaultTeamName() {
  return nextTeamName(club, Object.keys(savedOrders()));
}

function teamName() {
  return fullTeamName($("team-name").value, club) || defaultTeamName();
}

function showTeamHint() {
  const name = defaultTeamName();
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
      refreshRatings();
    }), button(t("delete_label"), t("delete_team", {name}), () => {
      const orders = savedOrders();
      delete orders[name];
      writeOrders(orders);
    }));
    row.append(tools);
    list.append(row);
  });
}

// A saved team can have old ELOs: without this, the quiet help would judge it
// with them. If it fails nothing changes, and Comprobar still gives the error
async function refreshRatings() {
  const players = team.filter((player) => player.id);
  if (!players.length) return;
  try {
    const answer = await post("check", {entries: players.map((player) => player.id)});
    players.forEach((player, index) => { player.rating = answer.ratings[index]; });
    rememberChecked(players, answer);
    if (!$("verdict").hasChildNodes()) render();
  } catch {
    // It's only a help
  }
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
  $("team-name").value = fullTeamName($("team-name").value, club);
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
// Changing the language or the theme reloads the page: keep the team being
// built. This copy only lasts until the page is back, and it's not the "save" option
for (const form of document.querySelectorAll(".languages, .themes")) {
  form.addEventListener("submit", () => {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({name: $("team-name").value, team}));
  });
}
const draft = sessionStorage.getItem(DRAFT_KEY);
sessionStorage.removeItem(DRAFT_KEY);
if (draft) {
  const restored = JSON.parse(draft);
  $("team-name").value = restored.name;
  team = restored.team;
}
render();
if (draft) refreshRatings(); // To show the changes since January again
showSaved();
loadRoster();
