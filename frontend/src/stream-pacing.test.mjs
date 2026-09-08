import assert from "node:assert/strict";
import test from "node:test";
import { splitStreamDelta } from "./stream-pacing.js";

test("splits response deltas into bounded display chunks", () => {
  const chunks = splitStreamDelta("The 2004 Honda S2000 is a high-revving roadster.", 18);

  assert.deepEqual(chunks, [
    "The 2004 Honda ",
    "S2000 is a ",
    "high-revving ",
    "roadster.",
  ]);
  assert.equal(chunks.join(""), "The 2004 Honda S2000 is a high-revving roadster.");
  assert.ok(chunks.every((chunk) => chunk.length <= 18));
});

test("preserves whitespace and empty delta behavior", () => {
  assert.deepEqual(splitStreamDelta(""), []);
  assert.deepEqual(splitStreamDelta("one two three", 7), ["one two ", "three"]);
});
