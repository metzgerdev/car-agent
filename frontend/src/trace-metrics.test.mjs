import assert from "node:assert/strict";
import test from "node:test";
import { summarizeTrace } from "./trace-metrics.js";

test("summarizes trace count, phases, and completed latency", () => {
  const metrics = summarizeTrace([
    { phase: "retrieve", duration_ms: 12.6 },
    { phase: "retrieve", duration_ms: 4.2 },
    { phase: "evaluate", duration_ms: 0.4 },
    { phase: "act", duration_ms: null },
  ]);

  assert.deepEqual(metrics, {
    callCount: 4,
    durationMs: 17.2,
    groundedCallCount: 2,
    phaseCounts: { retrieve: 2, evaluate: 1, act: 1 },
  });
});
