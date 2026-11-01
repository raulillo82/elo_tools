// Run with: node --test "web/tests/*.test.js"
"use strict";
const assert = require("node:assert");
const {test} = require("node:test");
const {fullTeamName, nextTeamName} = require("../static/team_names.js");

const SAN_VIATOR = [
  // Only a letter or a name
  ["a", "San Viator A"],
  ["A", "San Viator A"],
  ["z", "San Viator Z"],
  ["rey", "San Viator Rey"],
  ["Rey", "San Viator Rey"],
  ["dama", "San Viator Dama"],
  ["zaldi", "San Viator Zaldi"],
  // Words all in capitals keep only the first one
  ["REY", "San Viator Rey"],
  ["DAMA", "San Viator Dama"],
  ["CABALLO NEGRO", "San Viator Caballo Negro"],
  ["caballo NEGRO", "San Viator Caballo Negro"],
  ["ABC", "San Viator Abc"],
  ["SAN VIATOR REY", "San Viator Rey"],
  // Everything else stays as it was written
  ["reY", "San Viator ReY"],
  ["caballo negro", "San Viator Caballo negro"],
  ["Caballo Negro", "San Viator Caballo Negro"],
  ["caballo Negro", "San Viator Caballo Negro"],
  ["b2", "San Viator B2"],
  ["B2", "San Viator B2"],
  ["A2B", "San Viator A2B"],
  ["A", "San Viator A"],
  ["a b", "San Viator A b"],
  ["2", "San Viator 2"],
  ["1º", "San Viator 1º"],
  // Spaces
  ["  rey  ", "San Viator Rey"],
  ["caballo   negro", "San Viator Caballo negro"],
  ["\trey\n", "San Viator Rey"],
  // The club, in any case
  ["San Viator A", "San Viator A"],
  ["san viator a", "San Viator A"],
  ["SAN VIATOR A", "San Viator A"],
  ["sAn vIaToR a", "San Viator A"],
  ["san viator rey", "San Viator Rey"],
  ["SAN VIATOR Rey", "San Viator Rey"],
  // The club with spaces or accents
  ["san  viator a", "San Viator A"],
  ["  san viator   a  ", "San Viator A"],
  ["sanviator a", "San Viator A"],
  ["sán viátor a", "San Viator A"],
  // Accents and enye in the name
  ["ñandú", "San Viator Ñandú"],
  ["ÑANDÚ", "San Viator Ñandú"],
  ["águila", "San Viator Águila"],
  ["san viator águila", "San Viator Águila"],
  // Words which only start like the club
  ["san viatorko a", "San Viator San viatorko a"],
  ["san", "San Viator San"],
  ["viator", "San Viator Viator"],
  // Only the first club is taken away
  ["san viator san viator", "San Viator San viator"],
  // Other clubs can't be told apart: a known limit
  ["Martintxo Z", "San Viator Martintxo Z"],
  // Nothing but the club: the default name
  ["", ""],
  ["   ", ""],
  ["san viator", ""],
  ["SAN VIATOR", ""],
  ["  San  Viator  ", ""],
];

for (const [text, expected] of SAN_VIATOR) {
  test(`San Viator: ${JSON.stringify(text)}`, () => {
    assert.strictEqual(fullTeamName(text, "San Viator"), expected);
  });
}

test("clubs with one word", () => {
  assert.strictEqual(fullTeamName("martintxo a", "Martintxo"), "Martintxo A");
  assert.strictEqual(fullTeamName("MARTINTXO gazte", "Martintxo"), "Martintxo Gazte");
  assert.strictEqual(fullTeamName("martintxoko", "Martintxo"), "Martintxo Martintxoko");
  assert.strictEqual(fullTeamName("laudio", "Laudio"), "");
});

test("the result stays the same when it's processed again", () => {
  for (const [text] of SAN_VIATOR) {
    const once = fullTeamName(text, "San Viator");
    assert.strictEqual(fullTeamName(once, "San Viator"), once, text);
  }
});

test("all the clubs", () => {
  for (const club of ["Amurrio", "Buztinzuri", "Calasanz", "Danubio", "Eguidazu", "Kursaal",
                      "Laudio", "Marianistas", "Martintxo", "San Viator"]) {
    assert.strictEqual(fullTeamName("a", club), `${club} A`);
    assert.strictEqual(fullTeamName(`${club.toLowerCase()} rey`, club), `${club} Rey`);
    assert.strictEqual(fullTeamName(club.toUpperCase(), club), "");
  }
});

test("default name", () => {
  assert.strictEqual(nextTeamName("San Viator", []), "San Viator A");
  assert.strictEqual(nextTeamName("San Viator", ["San Viator B"]), "San Viator A");
  assert.strictEqual(nextTeamName("San Viator", ["San Viator A", "San Viator B"]), "San Viator C");
  assert.strictEqual(nextTeamName("San Viator", ["San Viator A", "San Viator C"]), "San Viator B");
  assert.strictEqual(nextTeamName("San Viator", ["San Viator Rey"]), "San Viator A");
  assert.strictEqual(nextTeamName("San Viator", ["san viator a"]), "San Viator B");
  assert.strictEqual(nextTeamName("San Viator", ["A", "B"]), "San Viator C");
});

test("default name with every letter taken", () => {
  const taken = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"].map((letter) => `San Viator ${letter}`);
  assert.strictEqual(nextTeamName("San Viator", taken), "San Viator");
});
