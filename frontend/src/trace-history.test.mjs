import assert from "node:assert/strict";
import test from "node:test";
import { mergeTraceHistory } from "./trace-history.js";

const call = (name, vehicle) => ({ name, vehicle });

test("preserves all calls from multiple turns", () => {
  const firstTurn = [call("search_inventory", "s2000"), call("get_vehicle", "s2000")];
  const secondTurn = [call("get_vehicle", "rx7"), call("get_vehicle", "rx7")];

  const history = mergeTraceHistory([], 0, firstTurn);
  const updated = mergeTraceHistory([...history, ...secondTurn], secondTurn.length, secondTurn);

  assert.deepEqual(updated, [...firstTurn, ...secondTurn]);
});

test("retains repeated same-name calls as separate history entries", () => {
  const repeated = [call("get_vehicle", "rx7"), call("get_vehicle", "rx7")];

  const updated = mergeTraceHistory(repeated, repeated.length, repeated);

  assert.equal(updated.length, 2);
  assert.notStrictEqual(updated[0], updated[1]);
});

test("backfills a completion missing from the live event stream", () => {
  const streamed = [call("search_inventory", "s2000")];
  const finalResponseTrace = [
    call("search_inventory", "s2000"),
    call("get_vehicle", "s2000"),
  ];

  const updated = mergeTraceHistory(streamed, streamed.length, finalResponseTrace);

  assert.deepEqual(updated, finalResponseTrace);
});

test("keeps prior history when the next turn has no tool calls", () => {
  const priorHistory = [call("get_vehicle", "s2000")];

  const updated = mergeTraceHistory(priorHistory, 0, []);

  assert.deepEqual(updated, priorHistory);
});
