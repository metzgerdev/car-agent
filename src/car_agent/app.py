"""HTTP interface for the text-first demo."""

from __future__ import annotations

import json
import os
from pathlib import Path
from queue import Queue
from threading import Thread
from time import perf_counter
from typing import Any, Iterator, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .crewai_agent import CrewAISalesAgent
from .modality import normalize_command
from .models import ToolCall
from .repositories import ReviewRepository
from .review_models import MagazineReview


WEB_ROOT = Path(__file__).parent / "web"


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    modality: Literal["text", "voice"] = "text"
    evaluation: bool = False

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


class EvaluationPhase(BaseModel):
    name: str
    duration_ms: float
    share: float


class EvaluationTool(BaseModel):
    name: str
    count: int


class EvaluationSource(BaseModel):
    name: str
    kind: str
    count: int


class EvaluationConfidence(BaseModel):
    label: Literal["high", "medium", "limited"]
    score: float
    rationale: str


class RecommendationChange(BaseModel):
    changed: bool
    before: list[str]
    after: list[str]
    changed_preferences: list[str] = Field(default_factory=list)
    reason: str


class EvaluationMetadata(BaseModel):
    route: Literal["deterministic", "crewai_live"]
    route_reason: str
    total_ms: float
    phases: list[EvaluationPhase]
    tools: list[EvaluationTool]
    sources: list[EvaluationSource]
    confidence: EvaluationConfidence
    recommendation_change: RecommendationChange


class ChatResponse(BaseModel):
    message: str
    state: dict[str, Any]
    trace: list[dict[str, Any]]
    reviews: list[VehicleReviewsResponse] = Field(default_factory=list)
    evaluation: EvaluationMetadata | None = None


class VoiceTokenResponse(BaseModel):
    token: str


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5_000)

    @field_validator("text")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be blank")
        return cleaned


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


    @api.get("/voice/scribe-token", response_model=VoiceTokenResponse)
    def voice_scribe_token() -> VoiceTokenResponse:
        """Mint a short-lived ElevenLabs token without exposing the API key."""

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="ElevenLabs voice is not configured. Set ELEVENLABS_API_KEY.",
            )
        try:
            response = httpx.post(
                "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
                headers={"xi-api-key": api_key},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("token") if isinstance(payload, dict) else None
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail="ElevenLabs could not issue a realtime transcription token.",
            ) from exc
        if not isinstance(token, str) or not token:
            raise HTTPException(
                status_code=502,
                detail="ElevenLabs returned an invalid realtime transcription token.",
            )
        return VoiceTokenResponse(token=token)


    @api.post("/voice/speak")
    def voice_speak(request: SpeechRequest) -> StreamingResponse:
        """Stream an assistant answer from ElevenLabs as playable MPEG audio."""

        if not os.getenv("ELEVENLABS_API_KEY") or not os.getenv("ELEVENLABS_VOICE_ID"):
            raise HTTPException(
                status_code=503,
                detail=(
                    "ElevenLabs speech is not configured. Set ELEVENLABS_API_KEY "
                    "and ELEVENLABS_VOICE_ID."
                ),
            )
        return StreamingResponse(
            _stream_elevenlabs_tts(request.text),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )


    @api.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest, http_request: Request) -> Any:
        command = normalize_command(request.conversation_id, request.message, request.modality)
        if "text/event-stream" in http_request.headers.get("accept", ""):
            return StreamingResponse(
                _stream_chat(
                    service,
                    reviews,
                    command.conversation_id,
                    command.message,
                    evaluation=request.evaluation,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        timing = _TurnEvaluation() if request.evaluation else None
        before = _evaluation_snapshot(service, command.conversation_id)
        route, route_reason = _evaluation_route(service, command.conversation_id, command.message)
        if timing:
            response = service.respond(
                command.conversation_id,
                command.message,
                trace_observer=timing.observe,
            )
        else:
            response = service.respond(command.conversation_id, command.message)
        payload = response.to_dict()
        payload["reviews"] = _reviews_for_response(service, response, reviews)
        if timing:
            payload["evaluation"] = _build_evaluation(
                service,
                response,
                before,
                route,
                route_reason,
                timing,
            )
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
    *,
    evaluation: bool = False,
) -> Iterator[str]:
    """Run one synchronous agent turn while yielding trace events as tools run."""

    events: Queue[tuple[str, dict[str, Any]] | None] = Queue()
    pending_trace_ids: dict[str, list[str]] = {}
    trace_counter = 0
    timing = _TurnEvaluation() if evaluation else None
    before = _evaluation_snapshot(service, conversation_id)
    route, route_reason = _evaluation_route(service, conversation_id, message)

    def observe(
        status: Literal["start", "complete"],
        name: str,
        arguments: dict[str, Any],
        call: ToolCall | None,
    ) -> None:
        nonlocal trace_counter
        if timing:
            timing.observe(status, name)
        if status == "start":
            trace_counter += 1
            trace_id = f"trace-{trace_counter}"
            pending_trace_ids.setdefault(name, []).append(trace_id)
        else:
            trace_ids = pending_trace_ids.get(name, [])
            trace_id = trace_ids.pop(0) if trace_ids else f"trace-{trace_counter}"
        payload: dict[str, Any] = {
            "trace_id": trace_id,
            "status": "running" if status == "start" else "complete",
            "name": name,
            "arguments": _redacted_arguments(name, arguments),
        }
        if call is not None:
            payload["call"] = call.to_dict(redact_sensitive=True)
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
            if timing:
                payload["evaluation"] = _build_evaluation(
                    service,
                    response,
                    before,
                    route,
                    route_reason,
                    timing,
                )
            events.put(("response", ChatResponse.model_validate(payload).model_dump(mode="json")))
        except Exception as exc:  # pragma: no cover - surfaced through the client event
            events.put(("error", {"message": str(exc)}))
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


def _stream_elevenlabs_tts(text: str) -> Iterator[bytes]:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ["ELEVENLABS_VOICE_ID"]
    model_id = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "POST",
            url,
            headers={
                "xi-api-key": api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={"text": text, "model_id": model_id},
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                if chunk:
                    yield chunk


def _redacted_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Apply the same contact redaction policy to an in-flight trace event."""

    return ToolCall(name=name, arguments=arguments, result={}).to_dict(redact_sensitive=True)["arguments"]


app = create_app()
agent: CrewAISalesAgent = app.state.agent


class _TurnEvaluation:
    def __init__(self) -> None:
        self.started_at = perf_counter()
        self._pending: dict[str, list[float]] = {}
        self.tool_durations: dict[str, list[float]] = {}

    def observe(
        self,
        status: Literal["start", "complete"],
        name: str,
        _arguments: dict[str, Any] | None = None,
        _call: ToolCall | None = None,
    ) -> None:
        if status == "start":
            self._pending.setdefault(name, []).append(perf_counter())
            return
        starts = self._pending.get(name, [])
        started = starts.pop(0) if starts else None
        if started is not None:
            self.tool_durations.setdefault(name, []).append((perf_counter() - started) * 1000)

    @property
    def total_ms(self) -> float:
        return (perf_counter() - self.started_at) * 1000


def _evaluation_route(
    service: CrewAISalesAgent,
    conversation_id: str,
    message: str,
) -> tuple[Literal["deterministic", "crewai_live"], str]:
    route_method = getattr(service, "evaluation_route", None)
    if callable(route_method):
        route, reason = route_method(conversation_id, message)
        return route, reason
    route = "crewai_live" if getattr(service, "use_live_model", False) else "deterministic"
    return route, "The configured agent facade selected this execution path."


def _evaluation_snapshot(service: CrewAISalesAgent, conversation_id: str) -> dict[str, Any]:
    state = getattr(service, "sessions", {}).get(conversation_id)
    if state is None:
        return {"vehicle_ids": [], "preferences": {}}
    preferences = state.preferences.to_dict()
    preferences.pop("name", None)
    preferences.pop("email", None)
    return {"vehicle_ids": list(state.last_vehicle_ids), "preferences": preferences}


def _build_evaluation(
    service: CrewAISalesAgent,
    response: Any,
    before: dict[str, Any],
    route: Literal["deterministic", "crewai_live"],
    route_reason: str,
    timing: _TurnEvaluation,
) -> dict[str, Any]:
    total_ms = max(timing.total_ms, 0.0)
    tool_total_ms = sum(sum(values) for values in timing.tool_durations.values())
    decision_ms = max(0.0, total_ms - tool_total_ms)
    phase_name = "CrewAI / OpenRouter" if route == "crewai_live" else "Deterministic policy"
    raw_phases: list[tuple[str, float]] = [(phase_name, decision_ms)]
    raw_phases.extend(
        (f"Tool: {name}", sum(durations))
        for name, durations in timing.tool_durations.items()
    )
    phases = [
        {
            "name": name,
            "duration_ms": round(duration, 2),
            "share": round((duration / total_ms * 100) if total_ms else 0.0, 1),
        }
        for name, duration in raw_phases
        if duration > 0.0
    ]
    tool_counts: dict[str, int] = {}
    for call in response.trace:
        tool_counts[call.name] = tool_counts.get(call.name, 0) + 1
    sources = _source_coverage(response.trace)
    confidence = _confidence(response.trace, len(sources))
    after_ids = list(response.state.last_vehicle_ids)
    before_ids = list(before.get("vehicle_ids", []))
    changed_preferences = [
        key
        for key, value in response.state.preferences.to_dict().items()
        if key not in {"name", "email"} and value != before.get("preferences", {}).get(key)
    ]
    recommendation_changed = before_ids != after_ids
    if recommendation_changed:
        if changed_preferences:
            reason = f"The turn changed {', '.join(changed_preferences)} and refreshed grounded vehicle options."
        else:
            reason = "The turn requested a new grounded vehicle set or selected a different vehicle."
    elif changed_preferences:
        reason = f"The turn updated {', '.join(changed_preferences)}, but the current vehicle set stayed the same."
    else:
        reason = "No recommendation change was detected for this turn."
    tools = getattr(service, "tools", None)
    inventory = getattr(tools, "inventory", None)
    return EvaluationMetadata(
        route=route,
        route_reason=route_reason,
        total_ms=round(total_ms, 2),
        phases=[EvaluationPhase.model_validate(phase) for phase in phases],
        tools=[EvaluationTool(name=name, count=count) for name, count in tool_counts.items()],
        sources=[EvaluationSource.model_validate(source) for source in sources],
        confidence=confidence,
        recommendation_change=RecommendationChange(
            changed=recommendation_changed,
            before=_vehicle_names(inventory, before_ids),
            after=_vehicle_names(inventory, after_ids),
            changed_preferences=changed_preferences,
            reason=reason,
        ),
    ).model_dump(mode="json")


def _vehicle_names(inventory: Any, vehicle_ids: list[str]) -> list[str]:
    if inventory is None:
        return vehicle_ids
    names: list[str] = []
    for vehicle_id in vehicle_ids:
        vehicle = inventory.get(vehicle_id)
        names.append(vehicle.name if vehicle else vehicle_id)
    return names


def _source_coverage(trace: list[ToolCall]) -> list[dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}

    def add(name: Any, kind: str) -> None:
        if not isinstance(name, str) or not name:
            return
        entry = coverage.setdefault(name, {"name": name, "kind": kind, "count": 0})
        entry["count"] += 1

    def inspect(value: Any) -> None:
        if not isinstance(value, dict):
            return
        provenance = value.get("provenance")
        if isinstance(provenance, dict):
            add(provenance.get("source_type"), "inventory")
        facts = value.get("facts")
        if isinstance(facts, list):
            for fact in facts:
                if isinstance(fact, dict):
                    add(fact.get("source"), "facts")
        reviews = value.get("reviews")
        if isinstance(reviews, list):
            for review in reviews:
                if isinstance(review, dict):
                    add(review.get("outlet"), "editorial")
        service_history = value.get("service_history")
        if isinstance(service_history, list):
            for record in service_history:
                if isinstance(record, dict):
                    add(record.get("source"), "service history")
        for key in ("vehicle", "vehicles", "matches"):
            nested = value.get(key)
            if isinstance(nested, list):
                for item in nested:
                    inspect(item)
            else:
                inspect(nested)

    for call in trace:
        inspect(call.result)
    return list(coverage.values())


def _confidence(trace: list[ToolCall], source_count: int) -> EvaluationConfidence:
    exact_match = any(
        call.name == "lookup_vehicle_exact" and call.result.get("exact_match") is True
        for call in trace
    )
    if exact_match:
        return EvaluationConfidence(
            label="high",
            score=0.98,
            rationale="Exact inventory availability was verified by the deterministic lookup tool.",
        )
    if trace and source_count >= 2:
        return EvaluationConfidence(
            label="high",
            score=0.9,
            rationale=f"The answer is grounded by {len(trace)} tool calls across {source_count} sources.",
        )
    if trace:
        return EvaluationConfidence(
            label="medium",
            score=0.72,
            rationale=f"The answer used {len(trace)} grounded tool call(s), but source diversity is limited.",
        )
    return EvaluationConfidence(
        label="limited",
        score=0.45,
        rationale="No retrieval tool was used for this turn, so the evaluation has limited grounding evidence.",
    )


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
