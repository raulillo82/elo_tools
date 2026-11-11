// What goes in brackets next to a rating: the change since January. january
// is undefined when there's no January list, and null for a player who had no
// rating then
"use strict";

function eloChange(rating, january) {
  if (january === undefined || rating === null || rating === undefined) return null;
  if (january === null) return {kind: "new", text: null};
  const difference = rating - january;
  if (difference > 0) return {kind: "up", text: `+${difference}`};
  if (difference < 0) return {kind: "down", text: `−${-difference}`};
  return {kind: "same", text: "0"};
}

if (typeof module !== "undefined") module.exports = {eloChange};
