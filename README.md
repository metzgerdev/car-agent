# Classic Sports Car Sales Agent

This is a portfolio demo of a used classic-sports-car sales agent. It is deliberately built around explicit state, typed tools, retrieval, and an inspectable tool trace so its behavior can be evaluated independently of a language model. CrewAI provides the live `Agent`/`Task`/`Crew` orchestration boundary, while the default mode remains deterministic and offline.

The current slice supports preference discovery, exact availability lookup, inventory search, vehicle facts, synthetic service-history retrieval, comparisons, and a validated mock test-drive request. CrewAI 1.15.x is supported on the Python 3.12.13 baseline. The HTTP app loads the local `.env` and uses its `OPENROUTER_API_KEY` for live CrewAI turns; the acceptance verifier remains explicitly offline.

## Run locally

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn car_agent.app:app --reload
```

The project targets Python 3.12.13. `.python-version` records the exact development version; use the equivalent Python 3.12 executable if your Python manager installs it elsewhere.

Then send a message:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{"conversation_id":"demo","message":"I want a weekend sports car under $45k with spirited driving."}'
```

The response includes the assistant message, current qualification state, and the tools used for that turn.

For an explicit availability question, the `lookup_vehicle_exact` tool checks the
year, make, and complete model against the current inventory. Its typed result
includes `exact_match` plus a `matched`, `not_found`, or `ambiguous` status. A
negative result is not treated as proof that the vehicle never existed; it means
only that the current inventory snapshot has no exact match. The agent may then
call `search_inventory` to offer grounded alternatives.

A compact identity response such as `2001 BMW M3` follows the same exact lookup
path, so the live model cannot end the turn with a progress message before
returning the availability result.

For the browser demo, open [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
after starting the server. The page has the conversation and a right-side Tool
Trace panel that exposes redacted agent activity. The “Voice transcript” option
uses the ElevenLabs Scribe realtime microphone when voice credentials are
configured. Click the microphone button, speak until the transcript commits,
then click the send arrow. The transcript is submitted to the same `/chat`
boundary with `modality: "voice"`.

To enable the voice layer, add these values to the local `.env` (the file is
ignored by Git):

```bash
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=your-voice-id
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
```

FastAPI mints the short-lived Scribe token and proxies assistant speech from
ElevenLabs, so the API key never reaches the browser. If the credentials are
absent, text chat continues to work and the voice controls report that voice
is not configured. The browser uses the official
[`@elevenlabs/react`](https://www.npmjs.com/package/@elevenlabs/react) hook;
see ElevenLabs' [realtime Scribe client-side streaming guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/client-side-streaming)
for the provider-side protocol.

The browser frontend is built with [assistant-ui](https://github.com/assistant-ui/assistant-ui)
and uses its `LocalRuntime` adapter to call the existing FastAPI `/chat`
endpoint. Its conversation surface is a styled assistant-ui Thread/Composer
composition with a ChatGPT-inspired dark theme; the surrounding panels expose
the demo's grounding evidence. The checked-in browser bundle is ready to serve.
To rebuild it after changing the React source, use Node 22 or newer:

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

The React source lives in `frontend/src`; FastAPI serves the production bundle
from `src/car_agent/web`.

The browser requests `/chat` with `Accept: text/event-stream`. The server keeps
the existing JSON response for normal clients, but streams redacted tool-start
and tool-complete events for the UI so the grounding panel can show messages
such as “Searching inventory…” while CrewAI is working.

The browser also has an optional `Evaluation` mode. When enabled, the next
turn requests structured evaluation metadata and renders an evaluation
cockpit above the conversation with the selected route (deterministic or
CrewAI/OpenRouter), latency buckets, tool counts, source coverage, qualitative
confidence, and recommendation changes. It exposes observable architecture
signals rather than private model chain-of-thought; normal turns omit the
evaluation payload.

The Tool Trace panel retains completed calls across the entire conversation,
including repeated calls with the same tool name. The final response acts as a
per-turn reconciliation point, backfilling any completion that was not observed
live without replacing earlier-turn history.

For live CrewAI turns, the same SSE stream also carries `response_delta` events
from CrewAI's native `Crew(stream=True)` output. The assistant-ui adapter applies
those deltas incrementally to the answer bubble, then replaces them with the
final typed response when the turn completes. Clients that do not request SSE
continue to receive the existing single JSON response.

Deterministic turns use the same `response_delta` contract. The local policy
splits its already-computed answer into small chunks without adding an
artificial delay, so offline and live demos exercise the same browser streaming
path.

Follow-up turns use the structured conversation state: `selected_vehicle_id`
resolves references such as “it” or “that car,” while `last_vehicle_ids`
resolves “those two” and “similar cars.” Clear contextual requests for details,
facts, comparisons, alternatives, or scheduling are routed to the grounded
domain tools before the live model is used for open-ended language.

The live model uses a hybrid context window. The backend retains the complete
typed turn log for the conversation, but each CrewAI prompt receives only the
latest four turns, a bounded summary of older turns, the active vehicle record,
and the latest non-sensitive grounding result. This keeps prompts useful and
bounded without making the model responsible for reconstructing business state
from an unbounded transcript.

When recommendations are available, the advisor can include curated Car and
Driver and MotorTrend review links in its response. These are editorial
context, not condition reports for a specific listing.

The advisor can also answer questions about a car's service history. The
dedicated `retrieve_service_history` tool returns typed listing records and
appears in the Tool Trace. These records are synthetic demo data, clearly
marked as `synthetic_demo`; they demonstrate a separate inventory enrichment
source and must not be treated as seller documents or a real condition report.

The advisor can also answer a contextual request such as `summarize magazine
reviews of the car`. It retrieves the curated review records, passes those
bounded sources to the live CrewAI turn for synthesis, and includes each
publication's short summary and source link in the response. Offline mode
serves the same grounded records directly. It asks for a specific vehicle if
no car has been selected yet.

## Run the clean offline demo

Run the complete qualification, recommendation, fact lookup, and test-drive
flow without a live model or network connection:

```bash
car-agent-demo
```

The demo prints each shopper turn, the assistant response, the current stage,
and the tool trace, ending with `Demo result: PASS`.

## Evaluate Phase 3

Run the deterministic 20-conversation sales evaluation without a live model:

```bash
car-agent-evaluate --strict
```

The strict evaluator checks state progression, tool use, ambiguity handling,
uncertainty responses, objection handling, question count, and hard-budget
compliance.

## Profile offline latency

Run the repeatable six-turn profile to see time spent in parsing, agent flows,
and each domain tool:

```bash
car-agent-profile --iterations 25
```

The profile reports exclusive phase time, so nested phases are not double-counted.
It intentionally measures the deterministic offline path. Live CrewAI latency is
dominated by the external model request and should be measured separately when
you explicitly want to spend an OpenRouter call.

To measure that live path, use a deliberately small opt-in workload:

```bash
car-agent-profile --live --iterations 1
```

This makes four OpenRouter-backed CrewAI turns. The report separates CrewAI
turn setup, `crew.kickoff` (model request plus orchestration), tool execution,
and output normalization. Provider usage and latency can vary by model, load,
and network conditions.

## Run with CrewAI and OpenRouter

The HTTP app uses `CrewAISalesAgent` with OpenRouter. The copied `.env` already supplies `OPENROUTER_API_KEY`; the model defaults to `openrouter/deepseek/deepseek-chat` and can be changed with `CAR_AGENT_CREWAI_MODEL`.

```bash
uvicorn car_agent.app:app --reload
```

For deterministic local checks, use `car-agent-verify --strict`; it never makes model calls. Both paths return the same domain response shape: message, conversation state, and tool trace.

### Salesperson character

The advisor uses the shared `CLASSIC_CAR_PERSONA` contract in
[`src/car_agent/persona.py`](src/car_agent/persona.py). It gives the live
CrewAI agent a named, consultative character—Alex—through its role, goal, and
backstory, while the deterministic demo uses the same user-facing voice. The
character is enthusiastic but not pushy: it explains trade-offs, distinguishes
facts from opinions, never invents inventory or specifications, and ends with
a natural next step.

## Verify Phase 1 interactively

After installing the project, run:

```bash
car-agent-verify --guided
```

Enter the suggested shopper messages and use `/check` at any point. The verifier reports the Phase 1 cases as they pass. Other useful commands are `/state`, `/trace`, `/reset`, and `/quit`. To make an incomplete run fail in automation, add `--strict`.

Run the tests with:

```bash
pytest
```

The inventory and knowledge records in `data/` are illustrative demo records. The multi-source plan in [`data/sources.md`](data/sources.md) treats the Craigslist snapshot as demo inventory and NHTSA/EPA payloads as provenance-backed enrichment. Pydantic boundary models and recorded fixtures keep the integration inspectable without requiring live provider calls.

To normalize an inventory fixture and write it to an idempotent SQLite store:

```bash
car-agent-ingest --input data/inventory.json --output data/inventory.sqlite
```

To try the first small Craigslist ingestion sample, provide explicit
horsepower enrichment for each source row and write canonical records to
SQLite:

```bash
car-agent-ingest-craigslist \
  --input data/craigslist_sample.csv \
  --horsepower-map data/craigslist_sample_horsepower.json \
  --output data/craigslist_sample.sqlite \
  --retrieved-at 2026-09-03T00:00:00Z
```

The sample contains four source-shaped rows; it is intentionally separate
from the six-record illustrative JSON fixture. To point the agent at the
resulting sample database for a demo, set the repository path before starting
the app:

```bash
CAR_AGENT_INVENTORY_PATH=data/craigslist_sample.sqlite uvicorn car_agent.app:app --reload
```

The SQLite output is ignored by Git and can be regenerated. The full source
export is not checked into this repository.

To verify Phase 2 interactively, install the notebook extra and open [notebooks/verify_phase2.ipynb](notebooks/verify_phase2.ipynb):

```bash
python -m pip install -e '.[dev,notebook]'
python -m ipykernel install --user \
  --name car-agent-py312 \
  --display-name "Python 3.12.13 (car-agent)"
jupyter lab notebooks/verify_phase2.ipynb
```

In Jupyter, select the `Python 3.12.13 (car-agent)` kernel. The notebook is
offline and ends with a PASS summary for P2-T1 through P2-T5.
