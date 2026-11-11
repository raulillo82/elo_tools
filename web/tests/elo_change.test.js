// Run with: node --test "web/tests/*.test.js"
"use strict";
const assert = require("node:assert");
const {test} = require("node:test");
const {eloChange} = require("../static/elo_change.js");

test("a rise and a fall, with their signs", () => {
  assert.deepEqual(eloChange(2000, 1955), {kind: "up", text: "+45"});
  assert.deepEqual(eloChange(1955, 2000), {kind: "down", text: "−45"});
});

test("the same rating is a zero", () => {
  assert.deepEqual(eloChange(1800, 1800), {kind: "same", text: "0"});
});

test("rated now but not in January is new", () => {
  assert.deepEqual(eloChange(1500, null), {kind: "new", text: null});
});

test("nothing without a January list or without a rating now", () => {
  assert.equal(eloChange(2000, undefined), null);
  assert.equal(eloChange(null, 1900), null);
  assert.equal(eloChange(null, null), null);
});
