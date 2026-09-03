# Classic Sports Car Sales Agent

This is a portfolio demo of a used classic-sports-car sales agent. It is deliberately built around explicit state, typed tools, retrieval, and an inspectable tool trace so its behavior can be evaluated independently of a language model. CrewAI provides the live `Agent`/`Task`/`Crew` orchestration boundary, while the default mode remains deterministic and offline.

The current slice supports preference discovery, inventory search, vehicle facts, comparisons, and a validated mock test-drive request. CrewAI 1.15.x is supported on the Python 3.12.13 baseline. The HTTP app loads the local `.env` and uses its `OPENROUTER_API_KEY` for live CrewAI turns; the acceptance verifier remains explicitly offline.

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

For the browser demo, open [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
after starting the server. The page includes guided prompts for the six-turn
sales flow and panels that expose the current shopper state and redacted tool
trace. The “Voice transcript” option demonstrates the shared text/voice input
boundary; it does not perform speech-to-text.

When recommendations are available, the browser also shows curated Car and
Driver and MotorTrend review links. Select one to open a short paraphrased
summary and a link to the publication; these are editorial context, not
condition reports for a specific listing.

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

## Run with CrewAI and OpenRouter

The HTTP app uses `CrewAISalesAgent` with OpenRouter. The copied `.env` already supplies `OPENROUTER_API_KEY`; the model defaults to `openrouter/deepseek/deepseek-chat` and can be changed with `CAR_AGENT_CREWAI_MODEL`.

```bash
uvicorn car_agent.app:app --reload
```

For deterministic local checks, use `car-agent-verify --strict`; it never makes model calls. Both paths return the same domain response shape: message, conversation state, and tool trace.

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
