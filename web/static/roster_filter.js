// Which players of the list of the club are shown for each choice of the filter
"use strict";

function hasBasqueLeague(players) {
  return players.some((player) => player.leagues.some((league) => league !== "alava"));
}

function inLeagues(leagues, choice) {
  if (choice === "alava") return leagues.includes("alava");
  if (choice === "basque") return leagues.some((league) => league !== "alava");
  return true;
}

if (typeof module !== "undefined") module.exports = {hasBasqueLeague, inLeagues};
