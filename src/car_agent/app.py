"""FastAPI interface for chat and inventory."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Iterator, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .crewai_agent import CrewAISalesAgent
from .models import ToolCall, trace_descriptor
from .repositories import ReviewRepository
from .review_models import MagazineReview


WEB_ROOT = Path(__file__).parent / "web"
LOGGER = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)

    @field_validator("conversation_id", "message")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class HealthResponse(BaseModel):
    status: Literal["ok"]


class VehicleReviewsResponse(BaseModel):
    vehicle_id: str
    vehicle_name: str
    reviews: list[MagazineReview]


class InventoryVehicleResponse(BaseModel):
    id: str
    name: str
    make: str
    model: str
    year: int
    price: int
    mileage: int
    body_style: str
    transmission: str
    drivetrain: str
    horsepower: int
    description: str
    tags: list[str] = Field(default_factory=list)
    image_url: str | None = None
    image_source_url: str | None = None
    image_attribution: str | None = None
    image_license: str | None = None


class InventoryResponse(BaseModel):
    total: int
    vehicles: list[InventoryVehicleResponse]


class ChatResponse(BaseModel):
    message: str
    state: dict[str, Any]
    trace: list[dict[str, Any]]
    reviews: list[VehicleReviewsResponse] = Field(default_factory=list)


def create_app(
    sales_agent: CrewAISalesAgent | None = None,
    review_repository: ReviewRepository | None = None,
) -> FastAPI:
    """Create an API app with an injectable agent for offline verification."""

    api = FastAPI(title="Classic Sports Car Sales Agent", version="0.1.0")
    service = sales_agent or CrewAISalesAgent(use_live_model=True)
    reviews = review_repository or ReviewRepository()
    api.state.agent = service
    api.state.review_repository = reviews
    api.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


    @api.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")


    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")


    @api.get("/inventory", response_model=InventoryResponse)
    def inventory(limit: int = Query(default=12, ge=1, le=100)) -> InventoryResponse:
        all_vehicles = service.tools.inventory.all()
        featured = [
            InventoryVehicleResponse.model_validate(vehicle.to_dict(include_service_history=False))
            for vehicle in all_vehicles[:limit]
        ]
        return InventoryResponse(total=len(all_vehicles), vehicles=featured)


    @api.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest, http_request: Request) -> Any:
        if "text/event-stream" in http_request.headers.get("accept", ""):
            return StreamingResponse(
                _stream_chat(
                    service,
                    reviews,
                    request.conversation_id,
                    request.message,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        response = service.respond(request.conversation_id, request.message)
        payload = response.to_dict()
        payload["reviews"] = _reviews_for_response(service, response, reviews)
        return ChatResponse.model_validate(payload)


    @api.get("/vehicles/{vehicle_id}/reviews", response_model=VehicleReviewsResponse)
    def vehicle_reviews(vehicle_id: str) -> VehicleReviewsResponse:
        vehicle = service.tools.inventory.get(vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found.")
        return VehicleReviewsResponse(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle.name,
            reviews=reviews.retrieve(vehicle),
        )

    return api


def _stream_chat(
    service: CrewAISalesAgent,
    repository: ReviewRepository,
    conversation_id: str,
    message: str,
) -> Iterator[str]:
    """Run one synchronous agent turn while yielding trace events as tools run."""

    events: Queue[tuple[str, dict[str, Any]] | None] = Queue()
    pending_trace_ids: dict[str, list[str]] = {}
    trace_counter = 0

    def observe(
        status: Literal["start", "complete"],
        name: str,
        arguments: dict[str, Any],
        call: ToolCall | None,
    ) -> None:
        nonlocal trace_counter
        if status == "start":
            trace_counter += 1
            trace_id = f"trace-{trace_counter}"
            pending_trace_ids.setdefault(name, []).append(trace_id)
        else:
            trace_ids = pending_trace_ids.get(name, [])
            trace_id = trace_ids.pop(0) if trace_ids else f"trace-{trace_counter}"
        phase, purpose = trace_descriptor(name)
        payload: dict[str, Any] = {
            "trace_id": trace_id,
            "status": "running" if status == "start" else "complete",
            "name": name,
            "phase": phase,
            "purpose": purpose,
            "outcome": "Running…" if status == "start" else "Operation completed.",
            "duration_ms": None if status == "start" else 0.0,
            "arguments": _redacted_arguments(name, arguments),
        }
        if call is not None:
            call_payload = call.to_dict(redact_sensitive=True)
            payload["call"] = call_payload
            payload.update(
                {
                    "phase": call_payload["phase"],
                    "purpose": call_payload["purpose"],
                    "outcome": call_payload["outcome"],
                    "duration_ms": call_payload["duration_ms"],
                }
            )
        events.put(("trace", payload))

    def work() -> None:
        try:
            response = service.respond(
                conversation_id,
                message,
                trace_observer=observe,
                response_observer=lambda delta: events.put(
                    ("response_delta", {"delta": delta})
                ),
            )
            payload = response.to_dict()
            payload["reviews"] = _reviews_for_response(service, response, repository)
            events.put(("response", ChatResponse.model_validate(payload).model_dump(mode="json")))
        except Exception:  # pragma: no cover - surfaced through the client event
            LOGGER.exception("Chat stream failed for conversation %s", conversation_id)
            events.put(("error", {"message": "The advisor encountered an internal error."}))
        finally:
            events.put(None)

    Thread(target=work, name="car-agent-chat", daemon=True).start()
    while True:
        item = events.get()
        if item is None:
            break
        event_name, payload = item
        yield _sse(event_name, payload)
    yield _sse("done", {})


def _sse(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _redacted_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Apply the same contact redaction policy to an in-flight trace event."""

    return ToolCall(name=name, arguments=arguments, result={}).to_dict(redact_sensitive=True)["arguments"]


app = create_app()
agent: CrewAISalesAgent = app.state.agent


def _reviews_for_response(
    service: CrewAISalesAgent,
    response: Any,
    repository: ReviewRepository,
) -> list[VehicleReviewsResponse]:
    vehicle_ids: list[str] = []
    seen_ids: set[str] = set()

    def add_vehicle_id(value: Any) -> None:
        if isinstance(value, str) and value and value not in seen_ids:
            seen_ids.add(value)
            vehicle_ids.append(value)

    add_vehicle_id(response.state.preferences.selected_vehicle_id)
    for vehicle_id in response.state.last_vehicle_ids:
        add_vehicle_id(vehicle_id)
    for call in response.trace:
        _add_tool_result_vehicle_ids(call.result, add_vehicle_id)

    groups: list[VehicleReviewsResponse] = []
    for vehicle_id in vehicle_ids:
        vehicle = service.tools.inventory.get(vehicle_id)
        if not vehicle:
            continue
        vehicle_reviews = repository.retrieve(vehicle)
        if vehicle_reviews:
            groups.append(
                VehicleReviewsResponse(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    reviews=vehicle_reviews,
                )
            )
    return groups


def _add_tool_result_vehicle_ids(result: Any, add_vehicle_id: Any) -> None:
    if not isinstance(result, dict):
        return
    vehicle = result.get("vehicle")
    if isinstance(vehicle, dict):
        add_vehicle_id(vehicle.get("id"))
    vehicles = result.get("vehicles")
    if isinstance(vehicles, list):
        for candidate in vehicles:
            if isinstance(candidate, dict):
                add_vehicle_id(candidate.get("id"))
    matches = result.get("matches")
    if isinstance(matches, list):
        for candidate in matches:
            if isinstance(candidate, dict):
                add_vehicle_id(candidate.get("id"))
