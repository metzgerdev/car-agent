# Classic Sports Car Sales Agent

Classic Sports Car Sales Agent is a used classic-sports-car sales application built around explicit state, typed tools, retrieval, and an inspectable tool trace. CrewAI provides the live `Agent`/`Task`/`Crew` orchestration boundary, while the default mode remains deterministic and offline.

The application supports preference discovery, exact availability lookup, inventory search, vehicle facts, service-history retrieval, comparisons, and a validated test-drive request. CrewAI 1.15.x is supported on the Python 3.12.13 baseline. The HTTP app loads the local `.env` and uses its `OPENROUTER_API_KEY` for live CrewAI turns; the acceptance verifier runs offline.

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
  -d '{"conversation_id":"sales-chat","message":"I want a weekend sports car under $45k with spirited driving."}'
```

The response includes the assistant message, current qualification state, and the tools used for that turn.

For an explicit availability question, the `lookup_vehicle_exact` tool checks the
year, make, and complete model against the current inventory. Its typed result
includes `exact_match` plus a `matched`, `family_match`, `not_found`, or
`ambiguous` status. A `family_match` handles a compact model-family request such
as `2008 BMW Z4` when the unique listing is `2008 BMW Z4 M Coupe`; it keeps
`exact_match: false` and names the full trim rather than misrepresenting it as
an exact match. A `not_found` result means only that the current inventory
snapshot has no exact or same-year family match. The agent may then call
`search_inventory` to offer grounded alternatives.

A compact identity response such as `2001 BMW M3` follows the same exact lookup
path, so the live model cannot end the turn with a progress message before
returning the availability result.

For the browser UI, open [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
after starting the server. The page has the conversation and a right-side Tool
Trace panel that exposes redacted agent activity. The composer accepts text
messages only.

The browser also includes an auction-style featured inventory gallery.
It loads the typed 50-car fixture from `/inventory`, supports local filtering
and pagination, and opens a listing preview with a real model-reference photo
and key vehicle specs for every record. The source page, photographer, and
license are shown in the preview.

The browser frontend is built with [assistant-ui](https://github.com/assistant-ui/assistant-ui)
and uses its `LocalRuntime` adapter to call the existing FastAPI `/chat`
endpoint. Its conversation surface is a styled assistant-ui Thread/Composer
composition with a ChatGPT-inspired dark theme; the surrounding panels expose
grounding evidence. The checked-in browser bundle is ready to serve.
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
artificial delay, so offline and live modes exercise the same browser streaming
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
appears in the Tool Trace. These records are synthetic data, clearly marked as
`synthetic_demo`; they demonstrate a separate inventory enrichment source and
must not be treated as seller documents or a real condition report.

The advisor can also answer a contextual request such as `summarize magazine
reviews of the car`. It retrieves the curated review records, passes those
bounded sources to the live CrewAI turn for synthesis, and includes each
publication's short summary and source link in the response. Offline mode
serves the same grounded records directly. It asks for a specific vehicle if
no car has been selected yet.

## Run deterministic evaluation

Run the deterministic 20-conversation sales evaluation without a live model:

```bash
car-agent-evaluate --strict
```

The strict evaluator checks state progression, tool use, ambiguity handling,
uncertainty responses, objection handling, question count, and hard-budget
compliance.

## Configure live CrewAI and OpenRouter

The HTTP app uses `CrewAISalesAgent` with OpenRouter. Create a local `.env` with
`OPENROUTER_API_KEY`; the model defaults to
`openrouter/deepseek/deepseek-chat` and can be changed with
`CAR_AGENT_CREWAI_MODEL`.

For deterministic local checks, use `car-agent-verify --strict`; it never makes model calls. Both paths return the same domain response shape: message, conversation state, and tool trace.

### Salesperson character

The advisor uses the shared `CLASSIC_CAR_PERSONA` contract in
[`src/car_agent/persona.py`](src/car_agent/persona.py). It gives the live
CrewAI agent a named, consultative character—Alex—through its role, goal, and
backstory, while deterministic mode uses the same user-facing voice. The
character is enthusiastic but not pushy: it explains trade-offs, distinguishes
facts from opinions, never invents inventory or specifications, and ends with
a natural next step.

## Verify interactively

After installing the project, run:

```bash
car-agent-verify --guided
```

Enter the suggested shopper messages and use `/check` at any point. Other useful commands are `/state`, `/trace`, `/reset`, and `/quit`. To make an incomplete run fail in automation, add `--strict`.

Run the tests with:

```bash
pytest
```

The inventory and knowledge records in `data/` are illustrative records. The multi-source plan in [`data/sources.md`](data/sources.md) treats the checked-in inventory fixture as the canonical inventory and NHTSA/EPA payloads as provenance-backed enrichment. Pydantic boundary models and recorded fixtures keep the integration inspectable without requiring live provider calls. The app validates and loads `data/inventory.json` directly at startup.

The checked-in inventory contains 50 deterministic records: six curated
vehicles plus 44 auction-style records generated by
[`scripts/generate_mock_inventory.py`](scripts/generate_mock_inventory.py).
Regenerate it with:

```bash
.venv/bin/python scripts/generate_mock_inventory.py
```

The generated records are inspired by common enthusiast-listing fields such as
mileage, condition notes, modifications, documentation, and service history;
they are not copied marketplace listings and their service records are marked
`synthetic_demo`. Every inventory record includes a real model-reference photo
from Wikimedia Commons with photographer, source-page, and license credits;
generated model families reuse their corresponding source-backed reference
photo across generated years and listing records.

To verify the inventory data interactively, install the notebook extra and open [notebooks/verify_phase2.ipynb](notebooks/verify_phase2.ipynb):

```bash
python -m pip install -e '.[dev,notebook]'
python -m ipykernel install --user \
  --name car-agent-py312 \
  --display-name "Python 3.12.13 (car-agent)"
jupyter lab notebooks/verify_phase2.ipynb
```

In Jupyter, select the `Python 3.12.13 (car-agent)` kernel. The notebook runs
offline and ends with a PASS summary for the inventory checks.
