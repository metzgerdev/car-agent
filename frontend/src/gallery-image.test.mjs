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
