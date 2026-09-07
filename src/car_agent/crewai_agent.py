"""CrewAI orchestration for the classic-car sales conversation.

CrewAI owns the live agent/task/crew boundary in this module. The deterministic
policy remains available as the offline execution mode so the product can keep
its current acceptance tests independent of API keys and network access.
"""

from __future__ import annotations

import json
import os
import re
from time import perf_counter
from typing import Any, Callable

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool
from crewai.types.streaming import CrewStreamingOutput, StreamChunkType
from dotenv import load_dotenv
from pydantic import BaseModel, Field, PrivateAttr

from .agent import DemoSalesAgent, TraceObserver
from .conversation_context import ConversationTurn, build_prompt_context
from .lookup_models import ExactVehicleQuery
from .models import AgentResponse, ConversationState, ShopperPreferences, ToolCall
from .persona import CLASSIC_CAR_PERSONA
from .profiling import TimingRecorder
from .repositories import PROJECT_ROOT
from .tools import SalesTools


load_dotenv(PROJECT_ROOT / ".env")


ResponseObserver = Callable[[str], None]


class SearchInventoryInput(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict, description="Hard and soft shopper filters")


class ExactVehicleLookupInput(ExactVehicleQuery):
    """Structured identity for an authoritative availability lookup."""


class GetVehicleInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")


class RetrieveVehicleFactsInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")
    topic: str | None = Field(default=None, description="Optional fact topic such as maintenance")


class RetrieveServiceHistoryInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")


class RetrieveMagazineReviewsInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")


class CompareVehiclesInput(BaseModel):
    vehicle_ids: list[str] = Field(description="Exactly two inventory vehicle IDs", min_length=2, max_length=2)


class ScheduleTestDriveInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")
    name: str = Field(description="Shopper's full name")
    email: str = Field(description="Shopper's email address")
    preferred_time: str = Field(description="Shopper's preferred day and time")


class CrewTurnOutput(BaseModel):
    """Structured output required from a live CrewAI turn."""

    message: str = Field(description="The concise shopper-facing response")
    state: dict[str, Any] = Field(description="Updated conversation state matching the domain schema")


class _CrewSalesTool(BaseTool):
    _backend: SalesTools = PrivateAttr()
    _profiler: TimingRecorder = PrivateAttr()
    _trace: list[ToolCall] = PrivateAttr()
    _trace_observer: TraceObserver | None = PrivateAttr(default=None)

    def __init__(
        self,
        backend: SalesTools,
        trace: list[ToolCall],
        profiler: TimingRecorder | None = None,
        trace_observer: TraceObserver | None = None,
    ) -> None:
        super().__init__()
        self._backend = backend
        self._profiler = profiler or TimingRecorder(enabled=False)
        self._trace = trace
        self._trace_observer = trace_observer

    def _run_backend(
        self,
        name: str,
        arguments: dict[str, Any],
        function: Any,
    ) -> str:
        if self._trace_observer:
            self._trace_observer("start", name, arguments, None)
        started = perf_counter()
        with self._profiler.span(f"tool.{name}"):
            result = function()
        return self._record(name, arguments, result, (perf_counter() - started) * 1000)

    def _record(
        self,
        name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        duration_ms: float,
    ) -> str:
        call = ToolCall(
            name=name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )
        self._trace.append(call)
        if self._trace_observer:
            self._trace_observer("complete", name, arguments, call)
        return json.dumps(result)


class SearchInventoryTool(_CrewSalesTool):
    name: str = "search_inventory"
    description: str = "Search the current used classic sports-car inventory using shopper filters."
    args_schema: type[BaseModel] = SearchInventoryInput

    def _run(self, filters: dict[str, Any]) -> str:
        return self._run_backend(
            "search_inventory",
            {"filters": filters},
            lambda: self._backend.search_inventory(filters),
        )


class LookupVehicleExactTool(_CrewSalesTool):
    name: str = "lookup_vehicle_exact"
    description: str = "Check whether the current inventory contains an exact year, make, and model."
    args_schema: type[BaseModel] = ExactVehicleLookupInput

    def _run(self, year: int, make: str, model: str) -> str:
        arguments = {"year": year, "make": make, "model": model}
        return self._run_backend(
            "lookup_vehicle_exact",
            arguments,
            lambda: self._backend.lookup_vehicle_exact(arguments),
        )


class GetVehicleTool(_CrewSalesTool):
    name: str = "get_vehicle"
    description: str = "Fetch one complete inventory record by its exact vehicle ID."
    args_schema: type[BaseModel] = GetVehicleInput

    def _run(self, vehicle_id: str) -> str:
        return self._run_backend(
            "get_vehicle",
            {"vehicle_id": vehicle_id},
            lambda: self._backend.get_vehicle(vehicle_id),
        )


class RetrieveVehicleFactsTool(_CrewSalesTool):
    name: str = "retrieve_vehicle_facts"
    description: str = "Retrieve sourced ownership and vehicle facts for one exact vehicle ID."
    args_schema: type[BaseModel] = RetrieveVehicleFactsInput

    def _run(self, vehicle_id: str, topic: str | None = None) -> str:
        arguments = {"vehicle_id": vehicle_id, "topic": topic}
        return self._run_backend(
            "retrieve_vehicle_facts",
            arguments,
            lambda: self._backend.retrieve_vehicle_facts(vehicle_id, topic),
        )


class RetrieveServiceHistoryTool(_CrewSalesTool):
    name: str = "retrieve_service_history"
    description: str = "Retrieve the listing's service records and clearly labeled record provenance for one exact inventory vehicle."
    args_schema: type[BaseModel] = RetrieveServiceHistoryInput

    def _run(self, vehicle_id: str) -> str:
        return self._run_backend(
            "retrieve_service_history",
            {"vehicle_id": vehicle_id},
            lambda: self._backend.retrieve_service_history(vehicle_id),
        )


class RetrieveMagazineReviewsTool(_CrewSalesTool):
    name: str = "retrieve_magazine_reviews"
    description: str = "Retrieve curated Car and Driver or MotorTrend summaries and links for one exact inventory vehicle."
    args_schema: type[BaseModel] = RetrieveMagazineReviewsInput

    def _run(self, vehicle_id: str) -> str:
        return self._run_backend(
            "retrieve_magazine_reviews",
            {"vehicle_id": vehicle_id},
            lambda: self._backend.retrieve_magazine_reviews(vehicle_id),
        )


class CompareVehiclesTool(_CrewSalesTool):
    name: str = "compare_vehicles"
    description: str = "Compare exactly two inventory vehicles by their exact IDs."
    args_schema: type[BaseModel] = CompareVehiclesInput

    def _run(self, vehicle_ids: list[str]) -> str:
        return self._run_backend(
            "compare_vehicles",
            {"vehicle_ids": vehicle_ids},
            lambda: self._backend.compare_vehicles(vehicle_ids),
        )


class ScheduleTestDriveTool(_CrewSalesTool):
    name: str = "schedule_test_drive"
    description: str = "Validate shopper contact details and create a mock test-drive request."
    args_schema: type[BaseModel] = ScheduleTestDriveInput

    def _run(self, vehicle_id: str, name: str, email: str, preferred_time: str) -> str:
        arguments = {
            "vehicle_id": vehicle_id,
            "name": name,
            "email": email,
            "preferred_time": preferred_time,
        }
        return self._run_backend(
            "schedule_test_drive",
            arguments,
            lambda: self._backend.schedule_test_drive(
                vehicle_id=vehicle_id,
                name=name,
                email=email,
                preferred_time=preferred_time,
            ),
        )


class CrewAISalesAgent:
    """Conversation facade backed by CrewAI in live mode and local policy by default."""

    framework = "crewai"

    def __init__(
        self,
        tools: SalesTools | None = None,
        *,
        use_live_model: bool | None = None,
        llm: str | None = None,
        profiler: TimingRecorder | None = None,
    ) -> None:
        self.profiler = profiler or TimingRecorder(enabled=False)
        self.deterministic_agent = DemoSalesAgent(tools, profiler=self.profiler)
        self.tools = self.deterministic_agent.tools
        self.sessions = self.deterministic_agent.sessions
        self.turn_history: dict[str, list[ConversationTurn]] = {}
        self.use_live_model = (
            _env_truthy(os.getenv("CAR_AGENT_USE_CREWAI"))
            if use_live_model is None
            else use_live_model
        )
        self.llm = llm or os.getenv("CAR_AGENT_CREWAI_MODEL") or "openrouter/deepseek/deepseek-chat"

    def respond(
        self,
        conversation_id: str,
        user_message: str,
        *,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        response = self._respond(
            conversation_id,
            user_message,
            trace_observer=trace_observer,
            response_observer=response_observer,
        )
        self._record_turn(conversation_id, user_message, response)
        return response

    def _respond(
        self,
        conversation_id: str,
        user_message: str,
        *,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        if not self.use_live_model:
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Exact availability is a deterministic inventory contract. Handle it
        # before CrewAI so a live model cannot end a turn with "one moment"
        # without returning the lookup result and a complete next step.
        if self.deterministic_agent._exact_vehicle_query(user_message.strip()):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # A bare known make/model such as "Honda S2000" is still an inventory
        # lookup. Keep it grounded and traceable instead of allowing the model
        # to answer from memory without emitting a tool call.
        if self.deterministic_agent._is_model_reference_request(user_message):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Scheduling is a side effect, so it must go through the deterministic
        # validation path. This prevents the live model from claiming that a
        # drive was booked without actually calling schedule_test_drive.
        previous_state = self.sessions.get(conversation_id)
        if (
            self.deterministic_agent._is_schedule_request(user_message)
            or (previous_state and previous_state.stage == "scheduling")
        ):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # A follow-up such as "tell me about similar sports cars" refers to
        # grounded alternatives already stored by an unavailable lookup. Keep
        # this contextual handoff deterministic so the model cannot ask the
        # shopper to restate a clear request.
        if (
            previous_state
            and previous_state.last_vehicle_ids
            and self.deterministic_agent._is_alternative_request(user_message)
        ):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        if self.deterministic_agent._is_review_request(user_message):
            return self._respond_live_review(
                conversation_id,
                user_message,
                trace_observer,
                response_observer,
            )
        if (
            previous_state
            and previous_state.last_vehicle_ids
            and self.deterministic_agent._is_contextual_followup(user_message)
        ):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        return self._respond_live(
            conversation_id,
            user_message,
            trace_observer,
            response_observer,
        )

    def _respond_deterministic(
        self,
        conversation_id: str,
        user_message: str,
        *,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        """Run the local policy and expose its answer using the live stream contract."""

        response = self.deterministic_agent.respond(
            conversation_id,
            user_message,
            trace_observer=trace_observer,
        )
        if response_observer:
            _emit_response_chunks(response.message, response_observer)
        return response

    def _record_turn(
        self,
        conversation_id: str,
        user_message: str,
        response: AgentResponse,
    ) -> None:
        self.turn_history.setdefault(conversation_id, []).append(
            ConversationTurn(
                user_message=user_message.strip(),
                assistant_message=response.message,
                tool_calls=[call.to_dict(redact_sensitive=True) for call in response.trace],
            )
        )

    def build_crew(
        self,
        trace: list[ToolCall] | None = None,
        *,
        review_only: bool = False,
        trace_observer: TraceObserver | None = None,
        stream: bool = False,
    ) -> Crew:
        """Build the inspectable CrewAI objects without making an LLM call."""

        trace = trace if trace is not None else []
        crew_tools = [] if review_only else [
            SearchInventoryTool(self.tools, trace, self.profiler, trace_observer),
            LookupVehicleExactTool(self.tools, trace, self.profiler, trace_observer),
            GetVehicleTool(self.tools, trace, self.profiler, trace_observer),
            RetrieveVehicleFactsTool(self.tools, trace, self.profiler, trace_observer),
            RetrieveServiceHistoryTool(self.tools, trace, self.profiler, trace_observer),
            RetrieveMagazineReviewsTool(self.tools, trace, self.profiler, trace_observer),
            CompareVehiclesTool(self.tools, trace, self.profiler, trace_observer),
            ScheduleTestDriveTool(self.tools, trace, self.profiler, trace_observer),
        ]
        review_instructions = (
            "You are in review-synthesis mode. The supplied review context is the complete source "
            "set for this turn. Synthesize its common themes and meaningful differences without "
            "inventing facts. Mention each outlet and title, cite each source with a Markdown link "
            "using the supplied URL exactly, and state that the editorial material is not a condition "
            "report for the specific listing. Never say you lack access when review context is supplied."
            if review_only
            else "For a magazine-review request, call retrieve_magazine_reviews and include the short "
            "sourced summaries and links; do not claim review access is unavailable when the tool returns reviews."
        )
        salesperson = Agent(
            role=CLASSIC_CAR_PERSONA.role,
            goal=CLASSIC_CAR_PERSONA.goal,
            backstory=CLASSIC_CAR_PERSONA.backstory,
            llm=self._live_llm(),
            tools=crew_tools,
            allow_delegation=False,
            max_iter=8,
            verbose=False,
        )
        turn = Task(
            name="sales_conversation_turn",
            description=(
                "Handle one shopper turn for conversation {conversation_id}.\n"
                "Shopper message:\n{user_message}\n\n"
                "Current domain state as JSON:\n{state_json}\n\n"
                "Compact summary of older conversation turns:\n{conversation_summary}\n\n"
                "Recent conversation turns (at most four):\n{recent_history}\n\n"
                "Active vehicle record:\n{active_vehicle}\n\n"
                "Latest safe grounding result:\n{latest_grounding}\n\n"
                "Curated magazine review context for this turn:\n{review_context}\n\n"
                "Use the inventory and knowledge tools whenever a claim needs grounding. "
                "For an explicit year/make/model availability question, call lookup_vehicle_exact "
                "before claiming availability. Treat status=matched as an exact match and "
                "status=family_match as a unique same-year model-family match; clearly name the "
                "full trim in the latter case. Treat status=not_found as absence from the current "
                "snapshot and use search_inventory only to find grounded alternatives. "
                "Never turn a fuzzy search result into an exact availability claim. "
                "For service-history, service-record, or maintenance-record requests, call "
                "retrieve_service_history for the explicitly selected vehicle; do not substitute "
                "general ownership facts for listing history. Clearly label synthetic demo records. "
                "For any test-drive scheduling request, use schedule_test_drive when all required "
                "vehicle and contact details are present. Never claim that a test drive is scheduled "
                "unless that tool returned a successful request; otherwise ask for the missing details. "
                f"{review_instructions} "
                "Preserve prior state, enforce the budget as a hard constraint, and ask no more "
                "than two useful questions in one turn. Never guess an ambiguous model or an "
                "unsupported specification. "
                f"{CLASSIC_CAR_PERSONA.task_guidance} Return a concise response plus the complete "
                "updated domain state."
            ),
            expected_output="A JSON object with message (string) and state (object).",
            agent=salesperson,
            output_pydantic=CrewTurnOutput,
        )
        return Crew(
            name="classic_car_sales_crew",
            agents=[salesperson],
            tasks=[turn],
            process=Process.sequential,
            verbose=False,
            share_crew=False,
            tracing=False,
            stream=stream,
        )

    def _live_llm(self) -> LLM | None:
        if not self.use_live_model:
            return None
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Live CrewAI mode requires OPENROUTER_API_KEY in the environment or .env file."
            )
        model = self.llm
        if not model.startswith("openrouter/"):
            model = f"openrouter/{model}"
        return LLM(
            model=model,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    def _respond_live(
        self,
        conversation_id: str,
        user_message: str,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        with self.profiler.span("crewai.live_turn"):
            previous_state = self.sessions.setdefault(conversation_id, ConversationState(conversation_id))
            self._pin_explicit_vehicle(previous_state, user_message)
            trace: list[ToolCall] = []
            with self.profiler.span("crewai.crew_build"):
                build_kwargs: dict[str, Any] = {}
                if trace_observer:
                    build_kwargs["trace_observer"] = trace_observer
                if response_observer:
                    build_kwargs["stream"] = True
                crew = self.build_crew(trace, **build_kwargs)
            prompt_context = build_prompt_context(
                self.turn_history.get(conversation_id, []),
                previous_state,
                self.tools.inventory,
            ).as_prompt_inputs()
            with self.profiler.span("crewai.crew_kickoff"):
                result = self._kickoff(
                    crew,
                    {
                        "conversation_id": conversation_id,
                        "user_message": user_message.strip(),
                        "state_json": json.dumps(previous_state.to_dict()),
                        "review_context": "",
                        **prompt_context,
                    },
                    response_observer,
                )
            with self.profiler.span("crewai.output_normalization"):
                output = _coerce_crew_output(result)
                state = _state_from_dict(conversation_id, output.state, previous_state)
                self._pin_explicit_vehicle(state, user_message)
            self.sessions[conversation_id] = state
            return AgentResponse(output.message.strip(), state, trace)

    def _pin_explicit_vehicle(self, state: ConversationState, user_message: str) -> None:
        """Keep an explicitly named vehicle authoritative across live turns."""

        mentioned_vehicles = self.tools.inventory.find_in_text(user_message)
        if len(mentioned_vehicles) != 1:
            return
        vehicle = mentioned_vehicles[0]
        state.preferences.selected_vehicle_id = vehicle.id
        state.last_vehicle_ids = [vehicle.id]

    def _respond_live_review(
        self,
        conversation_id: str,
        user_message: str,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        """Retrieve local review records, then ask CrewAI to synthesize them."""

        prepared = self.deterministic_agent.respond(
            conversation_id,
            user_message,
            trace_observer=trace_observer,
        )
        if not prepared.trace or prepared.trace[-1].name != "retrieve_magazine_reviews":
            if response_observer:
                _emit_response_chunks(prepared.message, response_observer)
            return prepared
        review_result = prepared.trace[-1].result
        reviews = review_result.get("reviews", [])
        if not reviews:
            if response_observer:
                _emit_response_chunks(prepared.message, response_observer)
            return prepared

        trace = prepared.trace
        prompt_context = build_prompt_context(
            self.turn_history.get(conversation_id, []),
            prepared.state,
            self.tools.inventory,
        ).as_prompt_inputs()
        with self.profiler.span("crewai.live_review_turn"):
            with self.profiler.span("crewai.crew_build"):
                build_kwargs: dict[str, Any] = {"review_only": True}
                if trace_observer:
                    build_kwargs["trace_observer"] = trace_observer
                if response_observer:
                    build_kwargs["stream"] = True
                crew = self.build_crew(trace, **build_kwargs)
            with self.profiler.span("crewai.crew_kickoff"):
                result = self._kickoff(
                    crew,
                    {
                        "conversation_id": conversation_id,
                        "user_message": user_message.strip(),
                        "state_json": json.dumps(prepared.state.to_dict()),
                        "review_context": json.dumps(reviews, ensure_ascii=False),
                        **prompt_context,
                    },
                    response_observer,
                )
            with self.profiler.span("crewai.output_normalization"):
                output = _coerce_crew_output(result)
                state = _state_from_dict(conversation_id, output.state, prepared.state)
        self.sessions[conversation_id] = state
        message = _ensure_review_citations(output.message.strip(), reviews)
        return AgentResponse(message, state, trace)

    def _kickoff(
        self,
        crew: Crew,
        inputs: dict[str, Any],
        response_observer: ResponseObserver | None = None,
    ) -> Any:
        """Kick off a crew and optionally expose shopper-facing output deltas."""

        result = crew.kickoff(inputs=inputs)
        if response_observer is None or not isinstance(result, CrewStreamingOutput):
            return result

        message_stream = _MessageStream(response_observer)
        for chunk in result:
            if chunk.chunk_type == StreamChunkType.TEXT:
                message_stream.feed(chunk.content)

        final_result = result.result
        try:
            message_stream.finish(_coerce_crew_output(final_result).message)
        except ValueError:
            # Preserve the normal output-normalization error at the caller.
            pass
        return final_result


def _emit_response_chunks(message: str, observer: ResponseObserver, *, chunk_size: int = 32) -> None:
    """Emit deterministic text in the same delta shape as CrewAI streaming."""

    cursor = 0
    while cursor < len(message):
        end = min(len(message), cursor + chunk_size)
        if end < len(message):
            boundary = message.rfind(" ", cursor + 8, end)
            if boundary > cursor:
                end = boundary + 1
        observer(message[cursor:end])
        cursor = end


def _coerce_crew_output(result: Any) -> CrewTurnOutput:
    structured = getattr(result, "pydantic", None)
    if structured is not None:
        return CrewTurnOutput.model_validate(structured)
    raw = getattr(result, "raw", str(result))
    try:
        return CrewTurnOutput.model_validate_json(raw)
    except ValueError as exc:
        raise ValueError("CrewAI returned a response that does not match CrewTurnOutput") from exc


class _MessageStream:
    """Extract the shopper-facing message from streamed structured JSON."""

    _message_key = re.compile(r'"message"\s*:\s*"')

    def __init__(self, observer: ResponseObserver) -> None:
        self._observer = observer
        self._buffer = ""
        self._value_start: int | None = None
        self._emitted = ""

    def feed(self, chunk: str) -> None:
        if not chunk:
            return
        self._buffer += chunk
        if self._value_start is None:
            match = self._message_key.search(self._buffer)
            if not match:
                return
            self._value_start = match.end()

        value_end = self._find_string_end(self._value_start)
        raw_value = self._buffer[self._value_start:value_end]
        try:
            decoded_value = json.loads(f'"{raw_value}"')
        except json.JSONDecodeError:
            return

        if decoded_value.startswith(self._emitted):
            delta = decoded_value[len(self._emitted):]
            if delta:
                self._observer(delta)
                self._emitted = decoded_value

    def finish(self, message: str) -> None:
        if not message:
            return
        if not self._emitted:
            self._observer(message)
        elif message.startswith(self._emitted) and message != self._emitted:
            self._observer(message[len(self._emitted):])

    def _find_string_end(self, start: int) -> int:
        index = start
        while index < len(self._buffer):
            character = self._buffer[index]
            if character == "\\":
                index += 2
                continue
            if character == '"':
                return index
            index += 1
        return len(self._buffer)


def _ensure_review_citations(message: str, reviews: list[dict[str, Any]]) -> str:
    """Add source links if a model omits one of the supplied citations."""

    missing_sources = [
        f"- Source: [{review['outlet']}]({review['url']})"
        for review in reviews
        if review.get("url") and review["url"] not in message
    ]
    if not missing_sources:
        return message
    return f"{message}\n\nSources:\n" + "\n".join(missing_sources)


def _state_from_dict(
    conversation_id: str,
    payload: dict[str, Any],
    previous: ConversationState,
) -> ConversationState:
    preferences_payload = payload.get("preferences", {})
    if not isinstance(preferences_payload, dict):
        preferences_payload = {}
    fields = set(ShopperPreferences.__dataclass_fields__)
    preference_values = previous.preferences.to_dict()
    preference_values.update({key: value for key, value in preferences_payload.items() if key in fields})
    preferences = ShopperPreferences(**preference_values)
    stage = payload.get("stage") or previous.stage
    last_vehicle_ids = payload.get("last_vehicle_ids", previous.last_vehicle_ids)
    if not isinstance(last_vehicle_ids, list) or not all(isinstance(value, str) for value in last_vehicle_ids):
        last_vehicle_ids = previous.last_vehicle_ids
    return ConversationState(
        conversation_id=conversation_id,
        preferences=preferences,
        stage=stage,
        last_vehicle_ids=last_vehicle_ids,
    )


def _env_truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}
