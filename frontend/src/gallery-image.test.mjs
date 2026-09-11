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

test("the conversation offers a reset path back to starter prompts", () => {
  assert.match(mainSource, /Back to starter prompts/);
  assert.match(mainSource, /setConversationId\(newConversationId\(\)\)/);
  assert.match(stylesSource, /\.conversation-back-bar\s*\{/);
});

test("live trace labels use the backend's canonical tool names", () => {
  assert.match(mainSource, /case "list_inventory"/);
  assert.match(mainSource, /case "get_vehicle_facts"/);
  assert.match(mainSource, /case "get_service_history"/);
  assert.doesNotMatch(mainSource, /case "search_inventory"/);
});
