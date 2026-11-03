// How far each player can move inside a right order. Ratings go in board order,
// and null means the player has no FIDE ELO. It's only a help: the server has
// the last word when the order is checked.
"use strict";

function canGoAbove(upper, lower, margin) {
  if (lower === null) return true;
  if (upper === null) return false;
  return lower - upper <= margin;
}

function orderIsRight(ratings, margin) {
  return ratings.every((upper, index) =>
    ratings.slice(index + 1).every((lower) => canGoAbove(upper, lower, margin)));
}

// Which boards break the rule, and how many pairs do. It counts like the server
function orderProblems(ratings, margin) {
  const boards = new Set();
  let count = 0;
  ratings.forEach((upper, index) => {
    ratings.slice(index + 1).forEach((lower, offset) => {
      if (canGoAbove(upper, lower, margin)) return;
      count++;
      boards.add(index + 1).add(index + 2 + offset);
    });
  });
  return {count, boards};
}

// The first and last boards of a player if the others stay in place, numbered from 1
function boardRange(ratings, index, margin) {
  const rating = ratings[index];
  let first = index;
  while (first > 0 && canGoAbove(rating, ratings[first - 1], margin)) first--;
  let last = index;
  while (last < ratings.length - 1 && canGoAbove(ratings[last + 1], rating, margin)) last++;
  return {first: first + 1, last: last + 1};
}

if (typeof module !== "undefined") module.exports = {orderIsRight, orderProblems, boardRange};
