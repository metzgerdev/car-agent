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

test("starter prompts remain enabled on an empty composer and send their text", () => {
  const starterPromptSource = threadSource.match(/function StarterPrompts\(\) \{[\s\S]*?\n\}/)?.[0] ?? "";

  assert.match(starterPromptSource, /const aui = useAui\(\);/);
  assert.match(starterPromptSource, /const \{ setText, isDisabled \} = unstable_useComposerInput\(\);/);
  assert.match(starterPromptSource, /if \(isDisabled\) return;/);
  assert.match(starterPromptSource, /setText\(prompt\);\s*aui\.composer\.send\(\);/);
  assert.match(starterPromptSource, /disabled=\{isDisabled\}/);
  assert.doesNotMatch(starterPromptSource, /disabled=\{!canSend\}/);

  for (const prompt of [
    "Find a weekend sports car",
    "Show me classic BMWs",
    "Tell me about the Honda S2000",
    "What ownership notes do you have on the Honda S2000?",
    "What do the magazine reviews say about the Mazda RX-7?",
    "Show me the service history for the BMW Z4 M Coupe",
    "Compare the Honda S2000 and Porsche 911 Carrera",
    "Do you have a 2011 BMW M3 in inventory?",
    "Tell me more about the 1999 Porsche 911 Carrera",
  ]) {
    assert.match(starterPromptSource, new RegExp(prompt.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});
