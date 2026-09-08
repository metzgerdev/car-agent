export const STREAM_CHUNK_SIZE = 18;
export const STREAM_TICK_MS = 35;

/**
 * Split an incoming response delta into display-sized pieces without cutting
 * at a word boundary when there is a natural whitespace boundary available.
 */
export function splitStreamDelta(text, maxChars = STREAM_CHUNK_SIZE) {
  if (!text) return [];
  if (maxChars < 1) throw new RangeError("maxChars must be positive");

  const chunks = [];
  let cursor = 0;
  while (cursor < text.length) {
    let end = Math.min(cursor + maxChars, text.length);
    if (end < text.length) {
      const boundary = text.lastIndexOf(" ", end);
      if (boundary > cursor) end = boundary + 1;
    }
    chunks.push(text.slice(cursor, end));
    cursor = end;
  }
  return chunks;
}

export function waitForStreamTick(delayMs = STREAM_TICK_MS, signal) {
  if (signal?.aborted) return Promise.reject(abortError());
  if (delayMs <= 0) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, delayMs);
    const onAbort = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      reject(abortError());
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function abortError() {
  const error = new Error("Response stream aborted");
  error.name = "AbortError";
  return error;
}
