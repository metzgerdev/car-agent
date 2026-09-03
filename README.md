# Classic Sports Car Sales Agent

This is a portfolio demo of a used classic-sports-car sales agent. It is deliberately built around explicit state, typed tools, retrieval, and an inspectable tool trace so its behavior can be evaluated independently of a language model.

The current slice is deterministic and runs without an API key. It supports preference discovery, inventory search, vehicle facts, comparisons, and a validated mock test-drive request. A live model adapter and sourced inventory are later phases described in [plan.md](plan.md).

## Run locally

```bash
/opt/homebrew/bin/python3.14 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn car_agent.app:app --reload
```

The project targets Python 3.14.7. `.python-version` records the exact development version; use the equivalent Python 3.14.7 executable if your Python manager installs it elsewhere.

Then send a message:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{"conversation_id":"demo","message":"I want a weekend sports car under $45k with spirited driving."}'
```

The response includes the assistant message, current qualification state, and the tools used for that turn.

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

The inventory and knowledge records in `data/` are illustrative demo records. They are intentionally kept separate from the domain and retrieval code so Phase 2 can replace them with sourced data and provenance.

To normalize an inventory fixture and write it to an idempotent SQLite store:

```bash
car-agent-ingest --input data/inventory.json --output data/inventory.sqlite
```
