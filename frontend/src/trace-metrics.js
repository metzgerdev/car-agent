const PHASES = ["retrieve", "evaluate", "act"];

export function summarizeTrace(trace) {
  const phaseCounts = Object.fromEntries(PHASES.map((phase) => [phase, 0]));
  let durationMs = 0;

  for (const call of trace) {
    if (Object.hasOwn(phaseCounts, call.phase)) phaseCounts[call.phase] += 1;
    if (typeof call.duration_ms === "number") durationMs += Math.max(0, call.duration_ms);
  }

  return {
    callCount: trace.length,
    durationMs,
    groundedCallCount: phaseCounts.retrieve,
    phaseCounts,
  };
}
