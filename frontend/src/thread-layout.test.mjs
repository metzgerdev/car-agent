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

test("the chat uses ElevenLabs UI message and empty-state primitives", () => {
  assert.match(threadSource, /ConversationEmptyState/);
  assert.match(threadSource, /ConversationContent/);
  assert.match(threadSource, /<Conversation className="elevenlabs-conversation/);
  assert.match(threadSource, /MessageContent/);
  assert.match(threadSource, /ShimmeringText/);
  assert.match(threadSource, /<Message from="user"/);
  assert.match(threadSource, /<Message from="assistant"/);
  assert.match(stylesSource, /color-scheme: light/);
  assert.match(stylesSource, /--chat-bg: #ffffff/);
});

test("message avatars retain a square, non-shrinking footprint", () => {
  assert.match(stylesSource, /\.elevenlabs-message-avatar\s*\{[\s\S]*flex: 0 0 30px;[\s\S]*aspect-ratio: 1;/);
  assert.match(stylesSource, /\.elevenlabs-message-avatar\s*\{ flex-basis: 26px; width: 26px;/);
});

test("the GP advisor avatar uses the ElevenLabs Matrix component", () => {
  assert.match(threadSource, /import \{ Matrix, type Frame \} from "\.\.\/\.\.\/elevenlabs-ui\/matrix"/);
  assert.match(threadSource, /function AdvisorAvatar\(\)[\s\S]*<Matrix[\s\S]*frames=\{gpMarkFrames\}/);
  assert.doesNotMatch(threadSource, /elevenlabs-assistant-avatar" aria-hidden="true">GP</);
});

test("both message roles use visible, bordered text cards", () => {
  const userMessageSource = threadSource.match(/function UserMessage\(\)[\s\S]*?\n\}/)?.[0] ?? "";
  assert.match(userMessageSource, /<MarkdownTextPrimitive remarkPlugins=\{\[remarkGfm\]\} components=\{markdownComponents\} \/>/);
  assert.doesNotMatch(userMessageSource, /elevenlabs-message-label">You/);
  assert.match(stylesSource, /\.elevenlabs-message-content\s*\{[\s\S]*background: #fff;[\s\S]*border: 1px solid var\(--chat-border-strong\);/);
  assert.match(stylesSource, /\.is-user \.elevenlabs-message-content\s*\{[\s\S]*color: var\(--chat-text\);[\s\S]*background: #fff;[\s\S]*border-color: #a1a1aa;/);
});

test("Markdown source links keep the full supplied URL visible", () => {
  assert.match(threadSource, /function SourceLink\(\{ href, children, \.\.\.props \}/);
  assert.match(threadSource, /target="_blank" rel="noreferrer">\{href\}<\/a>/);
  assert.match(threadSource, /components=\{markdownComponents\}/);
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
