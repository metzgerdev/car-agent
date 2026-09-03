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
| 2 — Data and knowledge | complete | Pydantic source models, Craigslist streaming normalization, recorded NHTSA/EPA adapters, SQLite ingestion, and notebook verification pass | Phase 3 scenario evaluation |
| 3 — Sales behavior | in progress | CrewAI/OpenRouter orchestration and local key loading are configured; P3-T1 and P3-T2 remain partial foundations | Scenario evaluation set |
| 4 — Conversion and polish | not started | P4-T2 has scheduler validation foundations | API, redaction, and voice boundary tests |

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
| 2026-09-03 | CrewAI orchestration foundation | CrewAI crew construction, typed tool adapters, offline facade behavior, and structured-output normalization pass | `cdb2046` | Scenario evaluation set |
| 2026-09-03 | OpenRouter runtime configuration | OpenRouter key loading, LiteLLM dependency, explicit OpenRouter base URL/model, and 23 tests pass without exposing the key | `fa3f3a3` | Scenario evaluation set |

## Test commands

```bash
python -m compileall -q src tests
pytest -q
```

The test suite must run without network access or a live model. Integration tests for a provider or external data source belong in a separate opt-in command.

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

## Phase 3 — Sales behavior

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P3-T0 | Construct the CrewAI sales crew and OpenRouter configuration | One CrewAI agent, one structured task, all five domain tools, and an OpenRouter LLM configuration are available without exposing the key | implemented |
| P3-T1 | Give preferences over multiple turns | State persists and each turn asks at most two useful questions | partial |
| P3-T2 | Combine hard and soft preferences | Hard constraints always win; soft preferences affect ranking | partial |
| P3-T3 | Say only “I like Porsche” | Agent asks which Porsche instead of selecting one | planned |
| P3-T4 | Ask for an unavailable specification | Agent states the limitation and offers inspection or source lookup | planned |
| P3-T5 | Object to maintenance or price | Agent gives a sourced trade-off and next action | planned |
| P3-T6 | Run 20 scripted conversations | At least 18 expected outcomes pass; budget compliance is 100% | planned |

## Phase 4 — Conversion and polish

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| P4-T1 | Call `/health`, `/chat`, and malformed `/chat` | 200, valid response, and 422 respectively | planned |
| P4-T2 | Submit invalid scheduling data | Error is returned and request count does not change | partial |
| P4-T3 | Retry an identical booking | No duplicate booking is created | planned |
| P4-T4 | Inspect a trace/log | Tool trace remains inspectable and contact values are redacted | planned |
| P4-T5 | Send equivalent text and voice intents | Both use the same normalized domain command | planned |
| P4-T6 | Follow clean-checkout instructions | Setup, tests, and demo transcript complete successfully | planned |

## Completion rule

A phase can be marked complete only when all of its test cases are implemented and passing, or when an explicit exception is documented with a replacement test and rationale.
