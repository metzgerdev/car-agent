# Acceptance Matrix

This document is the executable-minded checklist for the phases in [plan.md](../plan.md). Each test case has an ID so implementation, CI output, and the portfolio write-up can refer to the same contract.

The project is a demo of AI engineering rather than a production marketplace.
The Craigslist inventory source is therefore treated as a static snapshot;
listing freshness and availability are intentionally outside the acceptance
gate. Phase 2 measures typed multi-source ingestion, provenance, normalization,
retrieval grounding, and deterministic verification.

## Phase status

| Phase | Status | Current evidence | Next gate |
| --- | --- | --- | --- |
| 0 — Contract and skeleton | complete | Python 3.12.13 compile and serialization checks pass | none |
| 1 — Thin vertical slice | complete | Guided CLI verifier passes all P1 checks | none |
| 2 — Data and knowledge | complete | Pydantic source models, Craigslist streaming normalization, three-row CSV-to-SQLite ingestion, recorded NHTSA/EPA adapters, and notebook verification pass | none |
| 3 — Sales behavior | complete | CrewAI/OpenRouter foundation, persistent qualification, deterministic ranking, exact availability lookup, context-aware vehicle follow-ups, bounded hybrid LLM context, shared consultative salesperson persona, synthetic service-history retrieval, ambiguity/uncertainty handling, grounded objections, and 20-scenario evaluation pass; 73 Python tests pass | Phase 4 API and conversion tests |
| 4 — Conversion and polish | complete | Typed API contract, invalid-schedule protection, idempotent booking, redacted public responses, clean offline demo, assistant-ui styled dark browser UI, streamed tool-trace progress, complete multi-turn tool-trace history, phase-aware tool purpose/outcome/timing metadata, streamed deterministic and live CrewAI answer generation, processing-state Thinking placeholder, curated magazine-review modal, suggested-vehicle review context pass, text-only composer, and deterministic side-effect routing for test-drive scheduling; 77 Python tests, 4 frontend trace-history tests, and frontend build pass | none |

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
| 2026-09-03 | Phase 2 multi-source adapters | 29 tests pass for Pydantic Craigslist rows, streaming CSV validation, NHTSA vPIC/recall fixtures, EPA facts, and provenance-preserving enrichment | `2a3d692` | Phase 3 scenario evaluation |
| 2026-09-03 | Phase 2 Craigslist sample ingestion | Four source-shaped rows stream through Pydantic normalization, explicit horsepower enrichment, canonical SQLite storage, repository loading, and idempotency checks; 45 tests pass | `a48846a` | none |
| 2026-09-03 | Phase 3 sales behavior | 35 tests pass; `car-agent-evaluate --strict` reports 20/20 scenarios and zero budget violations | `3770b2c` | Phase 4 API and conversion tests |
| 2026-09-03 | Phase 4 conversion and polish | 41 tests pass; API, scheduling, redaction, modality, and `car-agent-demo` clean-checkout smoke tests pass | `11bfd1b` | none |
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
| 2026-09-05 | Phase 3 service-history retrieval | Inventory records carry typed synthetic `ServiceRecord` entries, SQLite/Craigslist normalization preserves or generates them, and both deterministic and CrewAI paths expose `retrieve_service_history`; 73 Python tests plus frontend build pass | `e5767c3` | none |
| 2026-09-05 | Phase 4 deterministic answer streaming | Offline policy turns emit multiple `response_delta` events through the same SSE/UI contract as live CrewAI turns, without an artificial delay; 74 Python tests and frontend build pass | `d2cfa9f` | none |
| 2026-09-06 | Phase 4 test-drive trace safety | Live-mode scheduling now routes through deterministic validation, so a successful confirmation is always paired with a `schedule_test_drive` tool event in the SSE stream; invalid or incomplete requests remain unbooked; 82 Python tests pass | `aae0a97` | none |
| 2026-09-06 | Phase 4 app simplification | Removed the user-facing agent evaluation mode, its API metadata, browser cockpit, and latency bookkeeping; normal JSON/SSE chat, Tool Trace, and the Phase 3 scenario evaluator remain; 80 Python tests, 4 frontend tests, and frontend build pass | `bc1799b` | none |
| 2026-09-06 | Phase 4 text-only simplification | Removed ElevenLabs endpoints, voice transport fields, microphone/TTS controls, modality adapters, and the voice dependency; the app now exposes only the text chat/SSE boundary; 76 Python tests, 4 frontend tests, and frontend build pass | `acd8a0f` | none |
| 2026-09-06 | Phase 4 trace explanation metadata | Tool traces now expose deterministic `phase`, `purpose`, `outcome`, and measured `duration_ms` fields across offline and CrewAI tool paths; SSE progress events and the browser Tool Trace render the human-readable explanation before expandable raw details; 77 Python tests, 4 frontend tests, and frontend build pass | pending | none |
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

Phase 4 can be verified with the clean offline happy-path demo:

```bash
car-agent-demo
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
| P2-T1 | Ingest a valid source fixture | A normalized 1990–2020 record is produced | implemented |
| P2-T2 | Ingest without provenance | Record is rejected with a field-level error | implemented |
| P2-T3 | Ingest the same fixture twice | Inventory remains duplicate-free | implemented |
| P2-T4 | Ask for one model’s ownership notes | Only that model’s sourced facts are returned | implemented |
| P2-T5 | Ingest invalid price/year/mileage/ID | Row is rejected and the error is visible | implemented |
| P2-T6 | Run official-source adapters against recorded fixtures | NHTSA vPIC, NHTSA recall, and EPA payloads validate with Pydantic and normalize into provenance-backed `VehicleFact` records with source URL and retrieval timestamp | implemented |
| P2-T7 | Ingest the small Craigslist CSV sample | Four source-shaped rows become canonical SQLite inventory records with explicit enrichment, preserved `craigslist_snapshot` provenance, repository loading, agent search, and idempotent re-ingestion | implemented |

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
| P3-T7 | Ask for an explicit year/make/model | `lookup_vehicle_exact` returns `exact_match: true` only for an exact current record; `false` produces a clear unavailable response and triggers grounded alternative search, including for compact replies such as `2001 BMW M3` | implemented |
| P3-T8 | Ask about similar cars after an unavailable exact lookup | A clear contextual follow-up reuses the prior grounded alternatives, returns their details, and does not ask the shopper to restate what “similar” means; the same route is used by offline and live facades | implemented |
| P3-T9 | Use a vehicle reference in a follow-up | Phrases such as “tell me more about it” resolve to the selected or latest grounded vehicle, retrieve its listing, and preserve the vehicle as the active context; clear contextual routes remain deterministic in live mode | implemented |
| P3-T10 | Run an open-ended live turn after prior conversation | CrewAI receives validated state plus bounded recent history, an older-turn summary, the active vehicle record, and safe grounding context; the full typed turn log remains retained without forwarding scheduling contact data | implemented |
| P3-T11 | Inspect the salesperson character | CrewAI exposes the shared Alex persona through role, goal, backstory, and task guidance; deterministic responses use the same consultative voice, grounded trade-offs, and natural next steps | implemented |
| P3-T12 | Ask for listing service history | Typed synthetic service records are returned by the dedicated `retrieve_service_history` tool, appear in the trace, are disclosed as synthetic, and do not replace general ownership facts | implemented |

## Phase 4 — Conversion and polish

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P4-T1 | Call `/health`, `/chat`, and malformed `/chat` | 200, valid response, and 422 respectively | implemented |
| P4-T2 | Submit invalid scheduling data | Error is returned and request count does not change | implemented |
| P4-T3 | Retry an identical booking | No duplicate booking is created | implemented |
| P4-T4 | Inspect a trace/log | Tool trace remains inspectable and contact values are redacted | implemented |
| P4-T6 | Follow clean-checkout instructions | Setup, tests, and demo transcript complete successfully | implemented |
| P4-T7 | Open the browser demo | `GET /` serves the assistant-ui React UI, its generated static assets load, the styled Thread uses the dark theme, and the right rail exposes only the live Tool Trace panel | implemented |
| P4-T8 | Open magazine context for a matched or suggested vehicle | The review endpoint and `/chat` response return typed links and short summaries from Car and Driver/MotorTrend without treating editorial context as canonical inventory facts; the right rail remains dedicated to Tool Trace | implemented |
| P4-T9 | Ask to summarize magazine reviews of the car | The agent retrieves the explicitly named, selected, or last vehicle's curated reviews; live CrewAI receives those bounded records and synthesizes publication-level themes/differences with Markdown citations, while offline mode serves the same grounded summaries; without vehicle context it asks for a specific model | implemented |
| P4-T10 | Watch a streamed chat turn | `POST /chat` with `Accept: text/event-stream` emits ordered redacted tool progress events, a final typed response event, and `done`; the browser renders active tool status before the answer arrives, while default JSON clients remain compatible | implemented |
| P4-T11 | Watch live LLM answer generation | Live CrewAI uses native streaming, the server emits shopper-facing `response_delta` events before the final typed response, and assistant-ui renders cumulative answer updates; tool-call chunks and structured state are not exposed | implemented |
| P4-T12 | Continue a conversation and inspect Tool Trace | Completed calls from prior turns remain visible; repeated calls such as `get_vehicle → get_vehicle` remain separate and a final response can backfill a missed live completion without erasing history | implemented |
| P4-T13 | Submit a chat message while the advisor is processing | An assistant-style `Thinking...` placeholder appears immediately, disappears when answer content starts streaming, and cannot remain after the stream finishes or fails | implemented |
| P4-T14 | Stream an offline deterministic answer | A deterministic turn emits multiple `response_delta` events whose concatenation equals the final response, before the final typed response event and `done` marker | implemented |
| P4-T5 | Use the text-only browser composer | The assistant-ui composer sends a plain text message through `/chat`; no voice controls, voice endpoints, modality fields, or ElevenLabs dependency are present | implemented |
| P4-T16 | Arrange a test drive in live mode | Scheduling uses the deterministic side-effect safety route, validates required details, emits `schedule_test_drive` in the streamed Tool Trace, and never confirms a booking without a successful tool result | implemented |

## Completion rule

A phase can be marked complete only when all of its test cases are implemented and passing, or when an explicit exception is documented with a replacement test and rationale.
