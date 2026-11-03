// Run with: node --test "web/tests/*.test.js"
"use strict";
const assert = require("node:assert");
const {test} = require("node:test");
const {orderIsRight, orderProblems, boardRange, moveTo, moveBreaks} = require("../static/board_moves.js");

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

test("moving puts the player on the chosen board and keeps the rest in order", () => {
  const list = ["a", "b", "c", "d"];
  assert.deepEqual(moveTo(list, 0, 2), ["b", "c", "a", "d"]);
  assert.deepEqual(moveTo(list, 3, 0), ["d", "a", "b", "c"]);
  assert.deepEqual(moveTo(list, 1, 1), list);
  assert.deepEqual(list, ["a", "b", "c", "d"]);
});

test("a move breaks the rule exactly when it leaves the player's range", () => {
  const ratings = [1900, 1870, 1840, 1700, 1690];
  ratings.forEach((_, from) => {
    const {first, last} = boardRange(ratings, from, 50);
    ratings.forEach((_, to) => {
      const inside = to + 1 >= first && to + 1 <= last;
      assert.equal(moveBreaks(ratings, from, to, 50), !inside, `${from} to ${to}`);
      assert.equal(orderIsRight(moveTo(ratings, from, to), 50), inside, `${from} to ${to}`);
    });
  });
});

test("a move is judged on its own even in a wrong order", () => {
  const ratings = [1500, 1900, 1880, 1700];
  assert.equal(moveBreaks(ratings, 1, 0, 50), false);
  assert.equal(moveBreaks(ratings, 2, 1, 50), false);
  assert.equal(moveBreaks(ratings, 0, 3, 50), false);
  assert.equal(moveBreaks(ratings, 3, 0, 50), true);
});

test("players without ELO stay below rated ones", () => {
  assert.equal(moveBreaks([1500, null], 1, 0, 50), true);
  assert.equal(moveBreaks([null, 1500], 0, 1, 50), false);
  assert.equal(moveBreaks([null, null, 1500], 0, 1, 50), false);
});
