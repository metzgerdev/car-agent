import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const threadSource = readFileSync(new URL("./components/assistant-ui/elements/thread.tsx", import.meta.url), "utf8");
const stylesSource = readFileSync(new URL("./styles.css", import.meta.url), "utf8");

test("the thread follows new messages with a bottom-anchored viewport", () => {
  assert.match(threadSource, /className="aui-styled-viewport"[\s\S]*autoScroll[\s\S]*turnAnchor="bottom"/);
  assert.match(threadSource, /scrollToBottomOnRunStart/);
  assert.match(threadSource, /scrollToBottomOnInitialize/);
});

test("the composer is outside the scrolling message viewport", () => {
  assert.match(threadSource, /<\/ThreadPrimitive\.Viewport>\s*<div className="aui-styled-footer">\s*<Composer \/>/);
  assert.doesNotMatch(threadSource, /ThreadPrimitive\.ViewportFooter/);
  assert.match(stylesSource, /\.conversation-card\s*\{[\s\S]*height: 720px;[\s\S]*overflow: hidden;/);
  assert.match(stylesSource, /\.aui-styled-viewport\s*\{[\s\S]*flex: 1 1 auto;[\s\S]*overflow-x: hidden;[\s\S]*overflow-y: auto;/);
  assert.match(stylesSource, /\.aui-styled-footer\s*\{[\s\S]*flex: 0 0 auto;[\s\S]*margin: 0 auto;/);
});
