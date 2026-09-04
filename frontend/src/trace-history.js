export function mergeTraceHistory(currentTrace, streamedTurnCount, responseTrace) {
  const streamedCount = Math.min(
    Math.max(streamedTurnCount, 0),
    currentTrace.length,
  );
  const previousTraceLength = currentTrace.length - streamedCount;
  const previousTrace = currentTrace.slice(0, previousTraceLength);
  const streamedTurnTrace = currentTrace.slice(previousTraceLength);
  const completeTurnTrace = streamedTurnTrace.length >= responseTrace.length
    ? streamedTurnTrace
    : [...streamedTurnTrace, ...responseTrace.slice(streamedTurnTrace.length)];
  return [...previousTrace, ...completeTurnTrace];
}
