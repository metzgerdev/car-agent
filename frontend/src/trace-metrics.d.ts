export type TraceMetricCall = {
  phase?: "retrieve" | "evaluate" | "act";
  duration_ms?: number | null;
};

export type TraceMetrics = {
  callCount: number;
  durationMs: number;
  groundedCallCount: number;
  phaseCounts: Record<"retrieve" | "evaluate" | "act", number>;
};

export declare function summarizeTrace(trace: readonly TraceMetricCall[]): TraceMetrics;
