# Acceptance Matrix

This document is the executable-minded checklist for the phases in [plan.md](../plan.md). Each test case has an ID so implementation, CI output, and the portfolio write-up can refer to the same contract.

The project is a demo of AI engineering rather than a production marketplace.
The inventory is therefore a checked-in mock fixture; listing freshness and
availability are intentionally outside the acceptance gate. Phase 2 measures
typed multi-source ingestion, provenance, normalization, retrieval grounding,
and deterministic verification.

## Phase status

| Phase | Status | Current evidence | Next gate |
| --- | --- | --- | --- |
| 0 — Contract and skeleton | complete | Python 3.12.13 compile and serialization checks pass | none |
| 1 — Thin vertical slice | complete | Guided CLI verifier passes all P1 checks | none |
| 2 — Data and knowledge | complete | Pydantic mock-inventory normalization, direct JSON fixture loading, recorded NHTSA/EPA adapters, deterministic 50-record fixture generation with model-specific production-year validation, and notebook verification pass; 83 Python tests pass | none |
| 3 — Sales behavior | complete | CrewAI/OpenRouter foundation, persistent qualification, deterministic ranking, exact availability lookup, explicit deterministic-router grounding and safety routes, context-aware vehicle follow-ups, bounded hybrid LLM context, shared consultative salesperson persona, synthetic service-history retrieval, ambiguity/uncertainty handling, grounded objections, and 20-scenario evaluation pass; 83 Python tests pass | Phase 4 API and conversion tests |
| 4 — Conversion and polish | complete | Typed API contract, invalid-schedule protection, idempotent booking, redacted public responses, assistant-ui styled dark browser UI, streamed tool-trace progress, complete multi-turn tool-trace history, phase-aware tool purpose/outcome/timing metadata, streamed deterministic and live CrewAI answer generation, processing-state Thinking placeholder, curated magazine-review context, suggested-vehicle review context pass, text-only composer, deterministic side-effect routing for test-drive scheduling, fixed composer with bottom-following chat scroll, gallery image loading states, and clickable initial starter prompts; 83 Python tests, 9 frontend tests, and frontend build pass | none |

### Update protocol

At every phase checkpoint, update this file in the same commit as the implementation or test change:

1. Change the phase status and each affected case from `planned`/`partial` to `implemented` only when its test passes.
2. Record the verification command and result in the phase status table.
3. Add a dated entry to the checkpoint log below, including the commit hash and the next gate.

## Checkpoint log

| Date | Phase/checkpoint | Evidence | Commit | Next gate |
| --- | --- | --- | --- | --- |
| 2026-09-03 | Phase 0/1 baseline | Python 3.14.7 smoke flow and guided verifier pass | `e5e5c79` | superseded by Python 3.12.13 baseline |
| 2026-09-03 | Phase 2 local ingestion | Normalization, provenance rejection, idempotent SQLite ingest, and compile checks pass | `282ff33` | Pydantic source adapters |
| 2026-09-03 | Python 3.12 and notebook verification | Python 3.12.13 environment, 19 tests, and headless Phase 2 notebook pass | `abc390b` | Official NHTSA/EPA adapters |
| 2026-09-03 | Phase 2 multi-source adapters | 29 tests pass for typed source contracts, NHTSA vPIC/recall fixtures, EPA facts, and provenance-preserving enrichment | `2a3d692` | Phase 3 scenario evaluation |
| 2026-09-03 | Phase 2 fixture ingestion | Mock inventory records pass typed normalization, canonical SQLite storage, repository loading, and idempotency checks; 45 tests pass | `a48846a` | none |
| 2026-09-03 | Phase 3 sales behavior | 35 tests pass; `car-agent-evaluate --strict` reports 20/20 scenarios and zero budget violations | `3770b2c` | Phase 4 API and conversion tests |
| 2026-09-03 | Phase 4 conversion and polish | 41 tests pass; API, scheduling, redaction, modality, and clean-checkout smoke tests pass | `11bfd1b` | none |
| 2026-09-03 | Phase 4 browser demo UI | Browser shell, guided prompts, live API health state, shopper profile, and redacted tool-trace panels are served by FastAPI; 42 tests pass | `15146ef` | none |
| 2026-09-03 | Phase 4 editorial review context | Typed Car and Driver/MotorTrend review links and paraphrased summaries are matched to inventory and surfaced through the UI modal; 46 tests pass | `8efbc20` | none |
| 2026-09-03 | Phase 4 suggested-vehicle review context | Review groups are attached from both conversation state and structured search/get-vehicle tool results, so alternatives suggested by the agent also surface review cards; 46 tests pass | `4170afb` | none |
| 2026-09-03 | Phase 4 agent review summaries | `retrieve_magazine_reviews` is available to CrewAI and deterministic paths; live mode passes its bounded review records to a review-synthesis turn that returns publication-level summaries with citations, while offline mode serves the same grounded records; 54 tests pass | `9031268` | none |
| 2026-09-03 | Phase 4 explicit vehicle follow-up regression | An explicitly named vehicle pins live conversation state before and after model output, so a review follow-up for the RX-7 cannot retrieve stale BMW context; 55 tests pass | `1536525` | none |
| 2026-09-03 | Phase 4 assistant-ui frontend | React frontend uses assistant-ui `LocalRuntime` with a custom adapter for `/chat`, preserves state/trace/review panels, and produces a FastAPI-served production bundle; frontend typecheck/build and 55 Python tests pass | `f02ecd2` | none |
| 2026-09-03 | Phase 4 assistant-ui styled dark UI | The conversation uses a dedicated assistant-ui styled Thread/Composer composition with ChatGPT-inspired dark tokens, while review, profile, prompt, and trace panels remain available; frontend typecheck/build and 55 Python tests pass | `c22f114` | none |
| 2026-09-04 | Phase 4 streamed trace progress | `/chat` negotiates an SSE response that emits redacted tool-start and tool-complete events before the final response; the assistant-ui Tool Trace panel renders live progress; 56 Python tests and frontend typecheck/build pass | `a130db8` | none |
| 2026-09-04 | Phase 4 focused evidence rail | The browser right rail contains only the live Tool Trace panel; prompts, shopper profile, and review cards are removed from that rail while review citations remain available in chat/API responses; the browser contract asserts the removed surfaces are absent | `177784b` | none |
| 2026-09-04 | Phase 4 streamed trace spinner cleanup | The assistant-ui adapter clears active trace state in a `finally` block after successful, failed, or aborted SSE turns, preventing an in-flight spinner from persisting after the stream ends; 56 Python tests and frontend typecheck/build pass | `9fc2f6f` | none |
| 2026-09-04 | Phase 4 explicit SSE completion cleanup | The browser clears active trace state on the server's `done` event and tolerates rewritten trace IDs by falling back to the tool name; frontend typecheck/build and phase-4 contract tests pass | `704e8b5` | none |
| 2026-09-04 | Phase 4 disabled-send hover feedback | The empty composer’s disabled send button uses a non-spinning `not-allowed` cursor rather than the macOS wait cursor; the served CSS contract verifies the regression fix | `c53e1db` | none |
| 2026-09-04 | Phase 4 streamed LLM answer generation | Live CrewAI turns use native `Crew(stream=True)` output; shopper-facing message deltas are emitted as `response_delta` SSE events before the final typed response, while tool-call chunks and structured state remain server-side; 58 Python tests and frontend typecheck/build pass | `8ac91ee` | none |
| 2026-09-04 | Phase 4 complete tool-trace history | The browser preserves completed tool calls across turns, keeps repeated same-name calls as separate entries, and reconciles missing live completions from the final per-turn response; 59 Python tests, 4 frontend trace-history tests, and frontend typecheck/build pass | `35e8c1c` | none |
| 2026-09-04 | Phase 4 processing placeholder | The browser shows an assistant-style `Thinking...` placeholder immediately after submission, removes it at the first streamed answer delta, and clears it on completion, error, or cancellation; 60 Python tests, frontend contract tests, and frontend typecheck/build pass | `770274a` | none |
| 2026-09-04 | Phase 3 contextual alternatives follow-up | After an unavailable exact lookup, a clear follow-up such as `tell me about similar sports cars` reuses the grounded alternatives, retrieves their details, and responds with options in both deterministic and live facades; 62 Python tests pass | `a8e9856` | none |
| 2026-09-04 | Phase 3 context-aware vehicle follow-ups | References such as `it`/`that car` resolve to the selected or latest vehicle; clear detail, facts, comparison, alternatives, and scheduling follow-ups use grounded state-aware routes in deterministic and live facades; 64 Python tests pass | `bd19c3b` | none |
| 2026-09-04 | Phase 3 hybrid conversation context | The backend retains typed full turn records while live CrewAI receives only four recent turns, a bounded older-turn summary, the active vehicle record, and the latest non-sensitive grounding result; 68 Python tests pass | `0513a18` | none |
| 2026-09-05 | Phase 3 salesperson persona | A shared `CLASSIC_CAR_PERSONA` contract gives CrewAI and the deterministic advisor the same named, consultative voice, with tests covering role/backstory/task guidance, grounded recommendations, and natural next steps; 71 Python tests pass | `2d76669` | none |
| 2026-09-05 | Phase 3 service-history retrieval | Mock inventory records carry typed synthetic `ServiceRecord` entries, SQLite normalization preserves them, and both deterministic and CrewAI paths expose `retrieve_service_history`; 73 Python tests plus frontend build pass | `e5767c3` | none |
| 2026-09-05 | Phase 4 deterministic answer streaming | Offline policy turns emit multiple `response_delta` events through the same SSE/UI contract as live CrewAI turns, without an artificial delay; 74 Python tests and frontend build pass | `d2cfa9f` | none |
| 2026-09-06 | Phase 4 test-drive trace safety | Live-mode scheduling now routes through deterministic validation, so a successful confirmation is always paired with a `schedule_test_drive` tool event in the SSE stream; invalid or incomplete requests remain unbooked; 82 Python tests pass | `aae0a97` | none |
| 2026-09-06 | Phase 4 app simplification | Removed the user-facing agent evaluation mode, its API metadata, browser cockpit, and latency bookkeeping; normal JSON/SSE chat, Tool Trace, and the Phase 3 scenario evaluator remain; 80 Python tests, 4 frontend tests, and frontend build pass | `bc1799b` | none |
| 2026-09-06 | Phase 4 text-only simplification | Removed ElevenLabs endpoints, voice transport fields, microphone/TTS controls, modality adapters, and the voice dependency; the app now exposes only the text chat/SSE boundary; 76 Python tests, 4 frontend tests, and frontend build pass | `acd8a0f` | none |
| 2026-09-06 | Phase 4 trace explanation metadata | Tool traces now expose deterministic `phase`, `purpose`, `outcome`, and measured `duration_ms` fields across offline and CrewAI tool paths; SSE progress events and the browser Tool Trace render the human-readable explanation before expandable raw details; 77 Python tests, 4 frontend tests, and frontend build pass | `b540b9a` | none |
| 2026-09-06 | Phase 4 dead-code cleanup | Removed stale voice proxy configuration, unused frontend review/profile/prompt/modal state and styles, and the unconsumed CrewAI crew cache while retaining the tested review API and synthesis path; 77 Python tests, 4 frontend tests, and frontend build pass | `4269d55` | none |
| 2026-09-07 | Phase 2 mock-inventory simplification | Removed the Craigslist CSV ingestion path, boundary models, adapter helpers, CLI, sample files, and tests; the checked-in mock JSON inventory remains the canonical source, with NHTSA/EPA enrichment adapters retained; 71 Python tests, 4 frontend tests, and frontend build pass | `b6fea73` | none |
| 2026-09-07 | Phase 2 JSON-only simplification | Removed `SQLiteInventoryStore`, `ingest_cli.py`, the `car-agent-ingest` entry point, `CAR_AGENT_INVENTORY_PATH`, SQLite tests, and SQLite documentation; the app and notebook now validate and load mock JSON directly; 71 Python tests, 4 frontend tests, and frontend build pass | `680804c` | none |
| 2026-09-07 | Phase 2 1,000-record mock inventory | Added a deterministic generator that preserves the six curated demo vehicles and creates 994 synthetic auction-style records; complete fixture validation, generator reproducibility, 72 Python tests, Phase 3 evaluation, and frontend build pass | `2773c51` | none |
| 2026-09-07 | Phase 3 partial vehicle identity regression | `2008 BMW Z4` now resolves to the unique same-year `2008 BMW Z4 M Coupe` family match with `exact_match: false`, while true misses still route to grounded alternatives; 73 Python tests and the 20-scenario evaluator pass | `ec7da91` | none |
| 2026-09-07 | Phase 4 press-review intent regression | Added `press review(s)`, automotive press, car reviews, and auto reviews to the deterministic review-intent route; the reproduced Z4 follow-up calls `retrieve_magazine_reviews` and returns its citation; 74 Python tests and the 20-scenario evaluator pass | `f30e7b9` | none |
| 2026-09-07 | Phase 4 auction-style inventory gallery | Added typed `/inventory` featured listings, CSS-generated synthetic gallery visuals, client-side filtering, and a three-shot listing preview modal above the chat while keeping the right rail dedicated to Tool Trace; 75 Python tests, 4 frontend tests, and frontend build pass | `346d0e1` | none |
| 2026-09-07 | Phase 4 inventory trim and model photos | Reduced the deterministic fixture to 100 records, added typed Wikimedia Commons photo/source/license metadata for the six curated gallery vehicles, and added credited real-photo rendering with a fallback visual; 75 Python tests, 4 frontend tests, and frontend build pass | `2f8676f` | none |
| 2026-09-07 | Phase 4 focused demo shell | Removed the title/status header and instructional banner so the browser presents only the inventory gallery, chat surface, and Tool Trace panel; 75 Python tests, 4 frontend tests, and frontend build pass | `a1b1af8` | none |
| 2026-09-07 | Phase 4 bare-model trace regression | Bare known-model turns such as `honda s2000` now use deterministic `search_inventory → get_vehicle` grounding in live and offline paths, emit SSE trace progress, and cannot finish as an ungrounded model-only answer; 77 Python tests and 4 frontend tests pass | `dc329ec` | none |
| 2026-09-07 | Phase 4 extended Tool Trace rail | Extended the desktop Tool Trace panel to the conversation height with internal scrolling for long histories while preserving the stacked mobile layout; 77 Python tests, 4 frontend tests, and frontend build pass | `f1913b4` | none |
| 2026-09-07 | Phase 4 clean source-photo presentation | Removed all in-image text, badges, gradients, and synthetic layers from mapped vehicle photos while retaining attribution outside the image and preserving the fallback visual; 77 Python tests, 4 frontend tests, and frontend build pass | `d23eaad` | none |
| 2026-09-07 | Phase 4 minimal gallery chrome | Removed the featured-inventory heading, enthusiast tagline, mock-listing count, auction-style label, and gallery explanatory footnote so the surface opens directly to cards and filtering; 77 Python tests, 4 frontend tests, and frontend build pass | `8083322` | none |
| 2026-09-07 | Phase 4 inventory owner label | Added `Grand Prix Motors Inventory` in the compact gallery-label position while preserving the minimal card-and-filter surface; 77 Python tests, 4 frontend tests, and frontend build pass | `a8b6a8d` | none |
| 2026-09-07 | Phase 4 Grand Prix brand mark | Replaced the chat welcome and assistant `CC` marks with `GP`; 77 Python tests, 4 frontend tests, and frontend build pass | `24113b4` | none |
| 2026-09-07 | Phase 4 minimal composer | Removed the `Text chat` and `Grounded by inventory and source records` helper text below the composer; 77 Python tests, 4 frontend tests, and frontend build pass | `70a78e3` | none |
| 2026-09-07 | Phase 4 inventory tagline | Added the corrected tagline `Specializing in classic/modern-classic enthusiast sports cars` beneath the Grand Prix Motors Inventory label; 77 Python tests, 4 frontend tests, and frontend build pass | `66b7017` | none |
| 2026-09-07 | Phase 4 minimal empty chat | Removed the `Classic Car Advisor` heading and introductory question from the empty chat state, retaining only the `GP` mark and changing the composer placeholder to Grand Prix Motors; 77 Python tests, 4 frontend tests, and frontend build pass | `f62c523` | none |
| 2026-09-07 | Phase 4 minimal Tool Trace chrome | Removed the `Live agent activity` eyebrow and empty Tool Trace instructional copy, leaving the trace title, progress, call count, and history; 77 Python tests, 4 frontend tests, and frontend build pass | `5160510` | none |
| 2026-09-07 | Phase 4 brand tagline placement | Moved `Specializing in classic/modern-classic enthusiast sports cars` from the gallery header to directly beneath the `GP` chat welcome mark; 77 Python tests, 4 frontend tests, and frontend build pass | `3218102` | none |
| 2026-09-07 | Phase 4 starter prompt suggestions | Added three clickable starter prompts beneath the GP tagline; each sends through the existing assistant-ui composer path; 77 Python tests, 4 frontend tests, and frontend build pass | `c4f7cbc` | none |
| 2026-09-07 | Phase 4 paginated inventory gallery | The gallery loads all 100 typed mock listings, displays six cards per page, resets pagination for filters, and provides accessible Previous/Next controls; 78 Python tests, 4 frontend tests, and frontend build pass | `b5d28bc` | none |
| 2026-09-07 | Phase 4 complete inventory photo coverage | Reduced the canonical fixture to 50 records and mapped every listing model family to a real Wikimedia Commons reference photo with source-page, attribution, and license metadata; 78 Python tests, 4 frontend tests, and frontend build pass | `bfc5733` | none |
| 2026-09-07 | Phase 4 fixed chat composer and auto-scroll | Constrained the conversation to a fixed-height flex surface, placed the composer outside the scrolling message viewport, and explicitly enabled assistant-ui bottom-following for new messages; 81 Python tests, 6 frontend tests, and frontend build pass | `a2fcea0` | none |
| 2026-09-08 | Phase 2 model-year validity | Replaced the generic 1990–2020 year formula with model-specific production-year ranges; the BMW 2002 and E36 328is examples now generate only historically valid years, and the checked-in 50-record fixture passes the new validity tests; 83 Python tests, 6 frontend tests, and frontend build pass | `0655179` | none |
| 2026-09-08 | Phase 2 inventory description cleanup | Removed the internal `Synthetic auction-style listing for an` label from generated descriptions and added a regression assertion; 83 Python tests pass | `754077d` | none |
| 2026-09-08 | Phase 4 gallery image loading state | Gallery photos show a centered spinner while loading, clear it on success or failure, and preserve the existing fallback visual and clean source-photo presentation; 83 Python tests, 8 frontend tests, and frontend build pass | `c735fac` | none |
| 2026-09-08 | Phase 3 live routing boundary | Renamed the deterministic policy to `DeterministicRouter`; `CrewAISalesAgent` remains the live CrewAI/LLM facade and delegates only grounding, context, offline verification, and safety-sensitive routes to the router; 84 Python tests, 8 frontend tests, and frontend build pass | `a6d429c` | none |
| 2026-09-08 | Phase 4 starter prompt initial state | Starter prompts no longer inherit the empty-composer `canSend` state; they remain enabled on initial load, submit their text through assistant-ui, and pass 9 frontend tests with a production build | `fa6185c` | none |
| 2026-09-08 | Phase 4 CLI simplification | Removed `demo_cli.py`, its `car-agent-demo` entry point, smoke test, and active documentation references; API/frontend verification remains the supported path; 83 Python tests pass | `6a71754` | none |
| 2026-09-03 | Phase 3 exact availability lookup | Typed `lookup_vehicle_exact` returns `exact_match` with matched/not-found/ambiguous status; explicit unavailable requests call it before grounded alternative search; 48 tests pass | `cdd7813` | none |
| 2026-09-03 | Phase 3 bare vehicle availability regression | A compact identity such as `2001 bmw m3` is routed through exact lookup even in live mode, returning a complete unavailable/alternative response instead of a progress-only final message; 52 tests pass | `74f1ea7` | none |
| 2026-09-03 | CrewAI orchestration foundation | CrewAI crew construction, typed tool adapters, offline facade behavior, and structured-output normalization pass | `cdb2046` | Scenario evaluation set |
| 2026-09-03 | OpenRouter runtime configuration | OpenRouter key loading, LiteLLM dependency, explicit OpenRouter base URL/model, and 23 tests pass without exposing the key | `fa3f3a3` | Scenario evaluation set |

## Test commands

```bash
python -m compileall -q src tests
pytest -q
```

The test suite must run without network access or a live model. Integration tests for a provider or external data source belong in a separate opt-in command.

Phase 3 can be verified with the deterministic scenario evaluator:

```bash
car-agent-evaluate --strict
```

Phase 4 can be verified with the API and frontend checks:

```bash
pytest -q tests/test_phase4_contract.py
npm --prefix frontend test
npm --prefix frontend run build
```

Phase 2 can also be verified interactively with [notebooks/verify_phase2.ipynb](../notebooks/verify_phase2.ipynb). Run it with `jupyter lab` after installing `.[notebook]`; its final cell asserts P2-T1 through P2-T5 and prints a single summary. For headless verification:

```bash
jupyter nbconvert --to notebook --execute --output /tmp/verify_phase2.executed.ipynb notebooks/verify_phase2.ipynb
```

## Phase 0 — Contract and skeleton

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P0-T1 | Read the version files | `.python-version` is `3.12.13`; packaging accepts Python 3.12 only | implemented |
| P0-T2 | Compile source and tests | `compileall` exits 0 | implemented |
| P0-T3 | Serialize a response | `AgentResponse.to_dict()` is JSON serializable and contains message, state, and trace | implemented |

## Phase 1 — Thin vertical slice

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P1-T1 | Send only a budget | Agent asks for missing preferences and calls no tools | implemented |
| P1-T2 | Add use and driving style | Agent emits the ordered trace `search_inventory → get_vehicle × 2 → retrieve_vehicle_facts` | implemented |
| P1-T3 | Inspect a recommended model | Facts match the selected vehicle and include a source | implemented |
| P1-T4 | Provide valid scheduling details | Exactly one test-drive request is created | implemented |
| P1-T5 | Search with a budget cap | Every result price is at or below the cap | implemented |
| P1-T6 | Complete the guided CLI flow with `--strict` | All Phase 1 checks report PASS and the process exits 0 | implemented |

## Phase 2 — Data and knowledge

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P2-T1 | Ingest a valid source fixture | A normalized 1960–2025 record is produced | implemented |
| P2-T2 | Ingest without provenance | Record is rejected with a field-level error | implemented |
| P2-T3 | Load the same fixture twice | The validated mock inventory is deterministic and contains no duplicate IDs | implemented |
| P2-T4 | Ask for one model’s ownership notes | Only that model’s sourced facts are returned | implemented |
| P2-T5 | Ingest invalid price/year/mileage/ID | Row is rejected and the error is visible | implemented |
| P2-T6 | Run official-source adapters against recorded fixtures | NHTSA vPIC, NHTSA recall, and EPA payloads validate with Pydantic and normalize into provenance-backed `VehicleFact` records with source URL and retrieval timestamp | implemented |
| P2-T7 | Load the checked-in mock inventory | `data/inventory.json` validates into canonical `Vehicle` records with `illustrative_fixture` provenance, repository loading and agent search work | implemented |
| P2-T8 | Validate the generated inventory scale | The deterministic generator preserves the six curated records and produces 44 additional typed records, for 50 unique IDs with synthetic service history; every generated model/year pair stays within its curated production range, descriptions omit internal synthetic-listing labels, and every record carries typed model-reference photo attribution metadata | implemented |

## Phase 3 — Sales behavior

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P3-T0 | Construct the CrewAI sales crew and OpenRouter configuration | One CrewAI agent, one structured task, all domain tools including `retrieve_service_history`, and an OpenRouter LLM configuration are available without exposing the key | implemented |
| P3-T1 | Give preferences over multiple turns | State persists and each turn asks at most two useful questions | implemented |
| P3-T2 | Combine hard and soft preferences | Hard constraints always win; soft preferences affect ranking | implemented |
| P3-T3 | Say only “I like Porsche” | Agent asks which Porsche instead of selecting one | implemented |
| P3-T4 | Ask for an unavailable specification | Agent states the limitation and offers inspection or source lookup | implemented |
| P3-T5 | Object to maintenance or price | Agent gives a sourced trade-off and next action | implemented |
| P3-T6 | Run 20 scripted conversations | 20/20 expected outcomes pass; budget compliance is 100% | implemented |
| P3-T7 | Ask for an explicit year/make/model | `lookup_vehicle_exact` returns `exact_match: true` only for an exact current record; a unique same-year model-family request returns `status: family_match` with `exact_match: false` and the full trim; `not_found` produces grounded alternatives, including for compact replies such as `2001 BMW M3` | implemented |
| P3-T8 | Ask about similar cars after an unavailable exact lookup | A clear contextual follow-up reuses the prior grounded alternatives, returns their details, and does not ask the shopper to restate what “similar” means; the same route is used by offline and live facades | implemented |
| P3-T9 | Use a vehicle reference in a follow-up | Phrases such as “tell me more about it” resolve to the selected or latest grounded vehicle, retrieve its listing, and preserve the vehicle as the active context; clear contextual routes remain deterministic in live mode | implemented |
| P3-T10 | Run an open-ended live turn after prior conversation | CrewAI receives validated state plus bounded recent history, an older-turn summary, the active vehicle record, and safe grounding context; the full typed turn log remains retained without forwarding scheduling contact data | implemented |
| P3-T11 | Inspect the salesperson character | CrewAI exposes the shared Alex persona through role, goal, backstory, and task guidance; deterministic responses use the same consultative voice, grounded trade-offs, and natural next steps | implemented |
| P3-T12 | Ask for listing service history | Typed synthetic service records are returned by the dedicated `retrieve_service_history` tool, appear in the trace, are disclosed as synthetic, and do not replace general ownership facts | implemented |
| P3-T13 | Inspect the live routing boundary | `CrewAISalesAgent` owns the live CrewAI/LLM facade, `DeterministicRouter` owns exact lookup, grounding, contextual safety, scheduling, and offline verification, and the retired `DemoSalesAgent` symbol is absent from the application code | implemented |

## Phase 4 — Conversion and polish

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P4-T1 | Call `/health`, `/chat`, and malformed `/chat` | 200, valid response, and 422 respectively | implemented |
| P4-T2 | Submit invalid scheduling data | Error is returned and request count does not change | implemented |
| P4-T3 | Retry an identical booking | No duplicate booking is created | implemented |
| P4-T4 | Inspect a trace/log | Tool trace remains inspectable and contact values are redacted | implemented |
| P4-T6 | Follow clean-checkout instructions | Backend setup, frontend build, full tests, and browser start instructions complete successfully | implemented |
| P4-T7 | Open the browser demo | `GET /` serves the assistant-ui React UI, its generated static assets load, the styled Thread uses the dark theme, and the right rail exposes only the live Tool Trace panel | implemented |
| P4-T8 | Open magazine context for a matched or suggested vehicle | The review endpoint and `/chat` response return typed links and short summaries from Car and Driver/MotorTrend without treating editorial context as canonical inventory facts; the right rail remains dedicated to Tool Trace | implemented |
| P4-T9 | Ask for magazine or press reviews of the car | The agent retrieves the explicitly named, selected, or last vehicle's curated reviews; phrases such as “press reviews” route to `retrieve_magazine_reviews`; live CrewAI receives those bounded records and synthesizes publication-level themes/differences with Markdown citations, while offline mode serves the same grounded summaries; without vehicle context it asks for a specific model | implemented |
| P4-T10 | Watch a streamed chat turn | `POST /chat` with `Accept: text/event-stream` emits ordered redacted tool progress events, a final typed response event, and `done`; the browser renders active tool status before the answer arrives, including for a bare known model such as `honda s2000`, while default JSON clients remain compatible | implemented |
| P4-T11 | Watch live LLM answer generation | Live CrewAI uses native streaming, the server emits shopper-facing `response_delta` events before the final typed response, and assistant-ui renders cumulative answer updates; tool-call chunks and structured state are not exposed | implemented |
| P4-T12 | Continue a conversation and inspect Tool Trace | Completed calls from prior turns remain visible; repeated calls such as `get_vehicle → get_vehicle` remain separate and a final response can backfill a missed live completion without erasing history | implemented |
| P4-T13 | Submit a chat message while the advisor is processing | An assistant-style `Thinking...` placeholder appears immediately, disappears when answer content starts streaming, and cannot remain after the stream finishes or fails | implemented |
| P4-T14 | Stream an offline deterministic answer | A deterministic turn emits multiple `response_delta` events whose concatenation equals the final response, before the final typed response event and `done` marker | implemented |
| P4-T5 | Use the text-only browser composer | The assistant-ui composer sends a plain text message through `/chat`; no voice controls, voice endpoints, modality fields, or ElevenLabs dependency are present | implemented |
| P4-T16 | Arrange a test drive in live mode | Scheduling uses the deterministic side-effect safety route, validates required details, emits `schedule_test_drive` in the streamed Tool Trace, and never confirms a booking without a successful tool result | implemented |
| P4-T18 | Browse featured inventory | The dark UI loads the typed 50-car fixture from `/inventory`, renders six cards per page with source photos and credit metadata, opens a detail gallery modal, and keeps the right rail dedicated to Tool Trace | implemented |
| P4-T19 | Use the focused demo shell | The browser contains only the featured gallery, chat surface, and Tool Trace panel; the title/status header and instructional banner are absent | implemented |
| P4-T20 | Inspect a long tool trace | On desktop, the Tool Trace panel extends to the conversation height and its history scrolls internally; mobile retains the stacked responsive layout | implemented |
| P4-T21 | View a source photo | Every inventory record has a real model-reference photo that renders cleanly without in-image text, gradients, lot labels, or synthetic badges; a loading spinner is shown until the image resolves, and attribution remains outside the photo in the listing details | implemented |
| P4-T22 | Use the minimal gallery surface | The gallery opens directly to the listing cards and filter control without explanatory title, count, presentation, or fallback-copy labels | implemented |
| P4-T23 | Identify the inventory owner | The gallery displays `Grand Prix Motors Inventory` in the compact inventory-label position | implemented |
| P4-T24 | Display the Grand Prix brand mark | The chat welcome mark and assistant avatars display `GP` rather than `CC` | implemented |
| P4-T25 | Keep the composer minimal | The composer shows only the input and send control without the `Text chat` or grounding helper text below it | implemented |
| P4-T26 | Display the inventory tagline | The gallery shows `Specializing in classic/modern-classic enthusiast sports cars` beneath the Grand Prix Motors Inventory label | implemented |
| P4-T27 | Keep the empty chat branded but minimal | The empty chat state shows only the `GP` mark and no `Classic Car Advisor` heading or introductory question | implemented |
| P4-T28 | Keep the Tool Trace panel focused | The Tool Trace panel shows its title and calls without the `Live agent activity` eyebrow or empty-state instructional copy | implemented |
| P4-T29 | Place the inventory tagline beneath the brand mark | The empty chat state shows `Specializing in classic/modern-classic enthusiast sports cars` directly beneath the `GP` logo, and the gallery no longer repeats it | implemented |
| P4-T30 | Use starter prompt suggestions | The empty chat state shows clickable starter prompts beneath the tagline; selecting one sends it through the existing assistant-ui composer path | implemented |
| P4-T31 | Page through featured inventory | The gallery loads the typed 50-car inventory dataset, displays six cards per page, keeps filtering scoped to the loaded inventory, and provides accessible Previous/Next controls with page state | implemented |
| P4-T32 | Verify complete photo coverage | All 50 inventory records expose a Wikimedia Commons image URL, source page, attribution, and license metadata; generated model families reuse the correct model-reference photo | implemented |
| P4-T33 | Continue a long chat conversation | The composer remains fixed at the bottom of the conversation surface outside the scrolling message viewport, which follows new messages when the shopper remains at the bottom | implemented |
| P4-T34 | Load a gallery photo | Each gallery image shows an animated loading spinner until it loads or fails; successful images reveal cleanly and failed images use the existing fallback visual | implemented |
| P4-T35 | Use a starter prompt on initial load | Starter prompts remain enabled when the composer is empty; clicking one fills and submits the prompt through assistant-ui | implemented |

## Completion rule

A phase can be marked complete only when all of its test cases are implemented and passing, or when an explicit exception is documented with a replacement test and rationale.
