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

// The list with the item at from taken out and put back at to, both from 0
function moveTo(list, from, to) {
  const result = list.slice();
  result.splice(to, 0, ...result.splice(from, 1));
  return result;
}

// Whether that move breaks the rule by itself: it only looks at the players the
// moved one jumps over, so it means something even while the order is wrong
function moveBreaks(ratings, from, to, margin) {
  const rating = ratings[from];
  if (to < from) return ratings.slice(to, from).some((upper) => !canGoAbove(rating, upper, margin));
  return ratings.slice(from + 1, to + 1).some((lower) => !canGoAbove(lower, rating, margin));
}

if (typeof module !== "undefined") {
  module.exports = {orderIsRight, orderProblems, boardRange, moveTo, moveBreaks};
}
