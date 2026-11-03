// Run with: node --test "web/tests/*.test.js"
"use strict";
const assert = require("node:assert");
const {test} = require("node:test");
const {orderIsRight, orderProblems, boardRange} = require("../static/board_moves.js");

const ranges = (ratings, margin = 50) =>
  ratings.map((_, index) => boardRange(ratings, index, margin)).map(({first, last}) => [first, last]);

test("each player gets the boards they can reach", () => {
  assert.deepEqual(ranges([1900, 1870, 1840, 1700, 1690]),
                   [[1, 2], [1, 3], [2, 3], [4, 5], [4, 5]]);
});

test("exactly the margin is allowed, and one more point isn't", () => {
  assert.deepEqual(ranges([1850, 1800]), [[1, 2], [1, 2]]);
  assert.deepEqual(ranges([1851, 1800]), [[1, 1], [2, 2]]);
});

test("a player can jump several boards, even above a lower rating", () => {
  assert.deepEqual(ranges([1800, 1810, 1820]), [[1, 3], [1, 3], [1, 3]]);
});

test("players without ELO only move among themselves", () => {
  assert.deepEqual(ranges([1500, null, null]), [[1, 1], [2, 3], [2, 3]]);
});

test("a single player stays on board 1", () => {
  assert.deepEqual(ranges([1500]), [[1, 1]]);
  assert.deepEqual(ranges([null]), [[1, 1]]);
});

test("the margin can change", () => {
  assert.deepEqual(ranges([1900, 1870], 20), [[1, 1], [2, 2]]);
});

const ORDERS = [
  [[], true], [[1500], true], [[1900, 1850], true], [[1850, 1900], true],
  [[1849, 1900], false], [[1500, null], true], [[null, null], true], [[null, 1500], false],
];
for (const [ratings, right] of ORDERS) {
  test(`order ${ratings}`, () => assert.equal(orderIsRight(ratings, 50), right));
}

test("problems are counted by pairs, with their boards", () => {
  const {count, boards} = orderProblems([1500, 1600, 1700], 50);
  assert.equal(count, 3);
  assert.deepEqual([...boards], [1, 2, 3]);
});

test("only the boards involved are marked", () => {
  const {count, boards} = orderProblems([1900, 1500, 1800, null, 1400], 50);
  assert.equal(count, 2);
  assert.deepEqual([...boards].sort(), [2, 3, 4, 5]);
});

test("a right order has no problems", () => {
  assert.deepEqual(orderProblems([1900, 1880, null], 50), {count: 0, boards: new Set()});
});

test("moving inside a range always gives a right order", () => {
  const ratings = [1900, 1870, 1840, 1835, 1700, null, null];
  ratings.forEach((rating, index) => {
    const {first, last} = boardRange(ratings, index, 50);
    for (let board = 1; board <= ratings.length; board++) {
      const others = ratings.filter((_, other) => other !== index);
      others.splice(board - 1, 0, rating);
      assert.equal(orderIsRight(others, 50), board >= first && board <= last);
    }
  });
});
