# Classic Sports Car Sales Agent

## What it is

A text-first sales assistant for classic and modern-classic enthusiast sports
cars. It combines deterministic business logic, typed domain tools, inventory
retrieval, curated vehicle reviews, and CrewAI orchestration.

The application includes a checked-in 50-car illustrative inventory. Service
history records are synthetic and clearly labeled; magazine reviews include
source links and summaries.

## Install

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

For live CrewAI/OpenRouter responses, create `.env`:

```env
OPENROUTER_API_KEY=your-key
CAR_AGENT_CREWAI_MODEL=openrouter/deepseek/deepseek-chat
```

## Run the UI

```bash
uvicorn car_agent.app:app --reload
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

The UI provides a dark assistant-ui chat interface, inventory gallery, and
live Tool Trace panel. HTTP chat requests use the CrewAI/OpenRouter path when
the API key is configured; deterministic routing and tool contracts remain
available for offline verification.

To rebuild the frontend after changing `frontend/src`:

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Serves the web UI. |
| `GET` | `/health` | Returns application health. |
| `GET` | `/inventory?limit=12` | Returns typed inventory listings. |
| `POST` | `/chat` | Processes a shopper message and returns the response, state, and tool trace. |
| `GET` | `/vehicles/{vehicle_id}/reviews` | Returns curated reviews for a listing. |

`POST /chat` body:

```json
{
  "conversation_id": "shopper-1",
  "message": "Do you have a BMW Z4?"
}
```

Clients requesting `Accept: text/event-stream` receive trace events and
response deltas as the turn runs. Standard clients receive one JSON response.

## Available tools

| Tool | Purpose |
|---|---|
| `search_inventory` | Rank listings using shopper preferences and query terms. |
| `lookup_vehicle_exact` | Verify exact year, make, and model availability, including family matches. |
| `get_vehicle` | Load one complete inventory listing. |
| `retrieve_vehicle_facts` | Retrieve sourced ownership and vehicle facts. |
| `retrieve_service_history` | Retrieve listing-level service records and provenance. |
| `retrieve_magazine_reviews` | Retrieve curated magazine reviews and source links. |
| `compare_vehicles` | Compare two inventory vehicles. |
| `schedule_test_drive` | Validate and create a test-drive request. |

## Architecture and design

- React and assistant-ui provide the chat and inventory gallery.
- FastAPI exposes the UI and JSON/SSE API.
- `CrewAISalesAgent` coordinates deterministic routing and live CrewAI turns.
- Pydantic models define inventory, conversation state, tool results, reviews,
  and API responses.
- Typed tools ground responses in inventory, exact vehicle lookup, vehicle
  facts, service history, magazine reviews, comparisons, and test-drive
  scheduling.
- Conversation state and the test-drive scheduler are in memory. Inventory and
  source records are loaded from JSON fixtures.
- Tool calls include phase, purpose, outcome, duration, and redacted arguments;
  the UI receives them through the existing SSE stream.
