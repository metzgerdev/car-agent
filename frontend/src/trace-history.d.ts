export declare function mergeTraceHistory<T>(
  currentTrace: readonly T[],
  streamedTurnCount: number,
  responseTrace: readonly T[],
): T[];
