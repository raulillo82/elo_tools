// Run with: node --test "web/tests/*.test.js"
"use strict";
const assert = require("node:assert");
const {test} = require("node:test");
const {hasBasqueLeague, inLeagues} = require("../static/roster_filter.js");

test("the filter is only for clubs with Basque league players", () => {
  assert.equal(hasBasqueLeague([{leagues: ["alava"]}]), false);
  assert.equal(hasBasqueLeague([{leagues: ["alava"]}, {leagues: ["honor"]}]), true);
  assert.equal(hasBasqueLeague([]), false);
});

const CASES = [
  [["alava"], "alava", true], [["alava"], "basque", false], [["alava"], "both", true],
  [["honor"], "alava", false], [["primera"], "basque", true], [["honor"], "both", true],
  [["alava", "honor"], "alava", true], [["alava", "honor"], "basque", true],
];
for (const [leagues, choice, shown] of CASES) {
  test(`${leagues} with ${choice}`, () => assert.equal(inLeagues(leagues, choice), shown));
}
