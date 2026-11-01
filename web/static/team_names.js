// Team names. Without anything from the page, so tests can run it with node.
"use strict";

// Finds the club at the start of a name, whatever its case, accents or spaces
function clubPrefix(club) {
  const words = club.split(/\s+/).map((word) => [...word].map((letter) =>
    `${letter.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\p{M}*`).join(""));
  return new RegExp(`^${words.join("\\s*")}(?=\\s|$)`, "iu");
}

// A word all in capitals keeps only the first one: "REY" becomes "Rey". Single
// letters and words with numbers, like "B2", stay as they are
function softenCapitals(word) {
  if (!/^\p{Lu}{2,}$/u.test(word)) return word;
  return `${word[0]}${word.slice(1).toLocaleLowerCase("es")}`;
}

// "rey", "san viator rey" and "SAN VIATOR Rey" all become "San Viator Rey".
// Returns "" if there's nothing but the club, which means the default name
function fullTeamName(text, club) {
  const clean = text.normalize("NFD").trim().replace(clubPrefix(club), "").trim()
    .replace(/\s+/g, " ");
  const label = clean.normalize("NFC").split(" ").map(softenCapitals).join(" ");
  if (!label) return "";
  return `${club} ${label[0].toLocaleUpperCase("es")}${label.slice(1)}`;
}

// The first letter not used by a saved team, so a saved "B" leaves "A" free
function nextTeamName(club, savedNames) {
  const used = new Set(savedNames.map((name) => name.trim().toUpperCase()));
  const clubName = club.toUpperCase();
  for (const letter of "ABCDEFGHIJKLMNOPQRSTUVWXYZ") {
    if (!used.has(letter) && !used.has(`${clubName} ${letter}`)) return `${club} ${letter}`;
  }
  return club;
}

if (typeof module !== "undefined") module.exports = {fullTeamName, nextTeamName};
