import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const mainSource = readFileSync(new URL("./main.tsx", import.meta.url), "utf8");
const stylesSource = readFileSync(new URL("./styles.css", import.meta.url), "utf8");

test("gallery photos expose a loading state and clear it on load or error", () => {
  assert.match(mainSource, /className="listing-image-loading"/);
  assert.match(mainSource, /onLoad=\{\(\) => setImageLoading\(false\)\}/);
  assert.match(mainSource, /onError=\{\(event\) => \{[\s\S]*setImageLoading\(false\)/);
  assert.match(mainSource, /parentElement\?\.classList\.add\("image-fallback"\)/);
});

test("gallery loading state uses a visible animated spinner", () => {
  assert.match(stylesSource, /\.listing-image-loading\s*\{[\s\S]*place-items: center;/);
  assert.match(stylesSource, /\.listing-image-spinner\s*\{[\s\S]*animation: spin 800ms linear infinite;/);
});

test("gallery exposes the inventory-backed conversation focus", () => {
  assert.match(mainSource, /focusedVehicleId/);
  assert.match(mainSource, /inventory-card-focused/);
  assert.match(stylesSource, /\.inventory-card-focused\s*\{/);
  assert.doesNotMatch(mainSource, /Conversation focus/);
});

test("gallery shows the inventory without a client-side make or model filter", () => {
  assert.doesNotMatch(mainSource, /Filter make, model, or tag/);
  assert.doesNotMatch(mainSource, /visibleVehicles/);
  assert.doesNotMatch(stylesSource, /gallery-search/);
});

test("desktop layout uses inventory as a vertical rail beside the conversation", () => {
  assert.match(mainSource, /<div className="workspace">\s*<InventoryGallery/);
  assert.match(stylesSource, /grid-template-columns: minmax\(220px, 250px\) minmax\(0, 1fr\) minmax\(280px, 320px\)/);
  assert.match(stylesSource, /workspace > \.inventory-gallery \.gallery-grid\s*\{[\s\S]*overflow-y: auto/);
  assert.match(stylesSource, /workspace > \.inventory-gallery \.inventory-card-kicker\s*\{ display: none/);
  assert.match(stylesSource, /workspace > \.inventory-gallery \.inventory-card\s*\{ display: flex;/);
  assert.match(stylesSource, /workspace > \.inventory-gallery \.inventory-card-hit\s*\{ display: grid; flex: 1;/);
  assert.match(stylesSource, /workspace > \.inventory-gallery \.listing-visual\s*\{ align-self: stretch; height: auto; min-height: 0;/);
  assert.match(stylesSource, /workspace > \.inventory-gallery \.listing-photo\s*\{ max-width: none;/);
});

test("desktop evidence rail stays visible while long card content scrolls internally", () => {
  assert.match(stylesSource, /@media \(min-width: 901px\) \{\s*html, body, #root \{ height: 100%; overflow: hidden; \}/);
  assert.match(stylesSource, /\.shell \{ width: 100%; height: 100vh; height: 100dvh; min-height: 0; padding: 24px 20px 40px; margin: 0; overflow: hidden; \}/);
  assert.match(stylesSource, /\.workspace \{ height: 100%; min-height: 0; grid-template-columns:/);
  assert.match(stylesSource, /\.sidebar \{ display: flex; height: 100%; min-height: 0; flex-direction: column; overflow: hidden;/);
  assert.match(stylesSource, /\.sidebar \.tool-trace-panel \.trace-list \{ min-height: 0; max-height: none; flex: 1 1 auto; overflow-y: auto;/);
  assert.doesNotMatch(stylesSource, /\.sidebar \{[^}]*overflow-y: auto/);
});

test("trace summaries show a readable outcome before raw tool data", () => {
  assert.match(mainSource, /function traceStatusLabel\(result: unknown\)/);
  assert.match(mainSource, /function traceResultCount\(result: unknown\)/);
  assert.match(mainSource, /className="trace-summary-purpose"/);
  assert.match(mainSource, /className="trace-result-count"/);
  assert.match(mainSource, /className="trace-raw-data"/);
  assert.match(stylesSource, /\.trace-raw-data > summary\s*\{[\s\S]*font-size: 0\.64rem/);
});

test("the conversation offers a reset path back to starter prompts", () => {
  assert.match(mainSource, /Back to starter prompts/);
  assert.match(mainSource, /setConversationId\(newConversationId\(\)\)/);
  assert.match(stylesSource, /\.conversation-back-bar\s*\{/);
});

test("trace metrics surface conversation-level LLM calls and token usage", () => {
  assert.match(mainSource, /Token budget used/);
  assert.match(mainSource, /LLM calls/);
  assert.match(mainSource, /llmUsage: payload\.metrics/);
});

test("the evidence rail contains only metrics and the tool trace", () => {
  assert.doesNotMatch(mainSource, /BuyerDossier|buyer-dossier|dossier/i);
  assert.doesNotMatch(stylesSource, /buyer-dossier|dossier/i);
});

test("live trace labels use the backend's canonical tool names", () => {
  assert.match(mainSource, /case "list_inventory"/);
  assert.match(mainSource, /case "get_vehicle_facts"/);
  assert.match(mainSource, /case "get_service_history"/);
  assert.doesNotMatch(mainSource, /case "search_inventory"/);
});
