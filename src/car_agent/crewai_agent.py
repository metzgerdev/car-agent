"""CrewAI live facade and deterministic routing."""

from __future__ import annotations

import json
import logging
import os
import re
from time import perf_counter
from typing import Any, Callable

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool
from crewai.types.streaming import CrewStreamingOutput, StreamChunkType
from dotenv import load_dotenv
from pydantic import BaseModel, Field, PrivateAttr

from .agent import DeterministicRouter, TraceObserver
from .conversation_context import ConversationTurn, build_prompt_context
from .intent_parser import IntentEnvelope, IntentParser, LLMIntentParser
from .lookup_models import ExactVehicleQuery
from .models import AgentResponse, ConversationState, LLMUsage, ShopperPreferences, ToolCall
from .persona import CLASSIC_CAR_PERSONA
from .profiling import TimingRecorder
from .repositories import PROJECT_ROOT
from .tools import SalesTools


load_dotenv(PROJECT_ROOT / ".env")


ResponseObserver = Callable[[str], None]
LOGGER = logging.getLogger(__name__)


class ListInventoryInput(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict, description="Hard and soft shopper filters")


class ExactVehicleLookupInput(ExactVehicleQuery):
    """Structured identity for an authoritative availability lookup."""


class GetVehicleInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")


class GetVehicleFactsInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")
    topic: str | None = Field(default=None, description="Optional fact topic such as maintenance")


class GetServiceHistoryInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")


class GetMagazineReviewsInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")


class GetVehicleComparisonInput(BaseModel):
    vehicle_ids: list[str] = Field(description="Exactly two inventory vehicle IDs", min_length=2, max_length=2)


class CreateTestDriveInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")
    name: str = Field(description="Shopper's full name")
    email: str = Field(description="Shopper's email address")
    preferred_time: str = Field(description="Shopper's preferred day and time")


class CrewTurnOutput(BaseModel):
    """Structured output required from a live CrewAI turn."""

    message: str = Field(description="The concise shopper-facing response")
    state: dict[str, Any] = Field(description="Updated conversation state matching the domain schema")


class BuyerDossierOutput(BaseModel):
    """A compact, evidence-bound purchase brief for one resolved listing."""

    summary: str = Field(description="A concise listing summary grounded in the supplied evidence")
    fit_reasons: list[str] = Field(default_factory=list)
    watchouts: list[str] = Field(default_factory=list)
    seller_questions: list[str] = Field(default_factory=list)
    inspection_priorities: list[str] = Field(default_factory=list)
    recommendation: str = Field(description="One of: buy, investigate, or pass")
    confidence: str = Field(description="One of: low, medium, or high")


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


class ListInventoryTool(_CrewSalesTool):
    name: str = "list_inventory"
    description: str = "List ranked current used classic sports-car inventory records matching filters."
    args_schema: type[BaseModel] = ListInventoryInput

    def _run(self, filters: dict[str, Any]) -> str:
        return self._run_backend(
            "list_inventory",
            {"filters": filters},
            lambda: self._backend.list_inventory(filters),
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


class GetVehicleFactsTool(_CrewSalesTool):
    name: str = "get_vehicle_facts"
    description: str = "Get sourced ownership and vehicle facts for one exact vehicle ID."
    args_schema: type[BaseModel] = GetVehicleFactsInput

    def _run(self, vehicle_id: str, topic: str | None = None) -> str:
        arguments = {"vehicle_id": vehicle_id, "topic": topic}
        return self._run_backend(
            "get_vehicle_facts",
            arguments,
            lambda: self._backend.get_vehicle_facts(vehicle_id, topic),
        )


class GetServiceHistoryTool(_CrewSalesTool):
    name: str = "get_service_history"
    description: str = "Get listing-level service records and provenance for one exact inventory vehicle."
    args_schema: type[BaseModel] = GetServiceHistoryInput

    def _run(self, vehicle_id: str) -> str:
        return self._run_backend(
            "get_service_history",
            {"vehicle_id": vehicle_id},
            lambda: self._backend.get_service_history(vehicle_id),
        )


class GetMagazineReviewsTool(_CrewSalesTool):
    name: str = "get_magazine_reviews"
    description: str = "Get curated Car and Driver or MotorTrend summaries and links for one exact inventory vehicle."
    args_schema: type[BaseModel] = GetMagazineReviewsInput

    def _run(self, vehicle_id: str) -> str:
        return self._run_backend(
            "get_magazine_reviews",
            {"vehicle_id": vehicle_id},
            lambda: self._backend.get_magazine_reviews(vehicle_id),
        )


class GetVehicleComparisonTool(_CrewSalesTool):
    name: str = "get_vehicle_comparison"
    description: str = "Get a comparison of exactly two inventory vehicles by exact IDs."
    args_schema: type[BaseModel] = GetVehicleComparisonInput

    def _run(self, vehicle_ids: list[str]) -> str:
        return self._run_backend(
            "get_vehicle_comparison",
            {"vehicle_ids": vehicle_ids},
            lambda: self._backend.get_vehicle_comparison(vehicle_ids),
        )


class CreateTestDriveTool(_CrewSalesTool):
    name: str = "create_test_drive"
    description: str = "Create a mock test-drive request after validating shopper contact details."
    args_schema: type[BaseModel] = CreateTestDriveInput

    def _run(self, vehicle_id: str, name: str, email: str, preferred_time: str) -> str:
        arguments = {
            "vehicle_id": vehicle_id,
            "name": name,
            "email": email,
            "preferred_time": preferred_time,
        }
        return self._run_backend(
            "create_test_drive",
            arguments,
            lambda: self._backend.create_test_drive(
                vehicle_id=vehicle_id,
                name=name,
                email=email,
                preferred_time=preferred_time,
            ),
        )


class CrewAISalesAgent:
    """Live conversation facade with deterministic grounding and safety routes."""

    framework = "crewai"

    def __init__(
        self,
        tools: SalesTools | None = None,
        *,
        use_live_model: bool | None = None,
        llm: str | None = None,
        profiler: TimingRecorder | None = None,
        intent_parser: IntentParser | None = None,
    ) -> None:
        self.profiler = profiler or TimingRecorder(enabled=False)
        self.router = DeterministicRouter(tools, profiler=self.profiler)
        self.tools = self.router.tools
        self.sessions = self.router.sessions
        self.turn_history: dict[str, list[ConversationTurn]] = {}
        self.conversation_llm_usage: dict[str, LLMUsage] = {}
        self.use_live_model = (
            _env_truthy(os.getenv("CAR_AGENT_USE_CREWAI"))
            if use_live_model is None
            else use_live_model
        )
        self.llm = llm or os.getenv("CAR_AGENT_CREWAI_MODEL") or "openrouter/deepseek/deepseek-chat"
        self.intent_parser = intent_parser

    def respond(
        self,
        conversation_id: str,
        user_message: str,
        *,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        try:
            response = self._respond(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        except Exception:
            if not self.use_live_model:
                raise
            LOGGER.warning(
                "Live model turn failed; returning the deterministic fallback for conversation %s",
                conversation_id,
                exc_info=True,
            )
            response = self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        response = self._with_conversation_usage(conversation_id, response)
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
        previous_state = self.sessions.get(conversation_id)
        scope_vehicle_ids = (
            self.router._shown_vehicle_ids(previous_state)
            if previous_state
            else None
        )
        mentioned_vehicles = list(
            self.tools.inventory.resolve_reference(
                user_message,
                scope_vehicle_ids=scope_vehicle_ids,
            ).candidates
        )
        # Route exact availability deterministically.
        if self.router._exact_vehicle_query(user_message.strip()):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Route comparisons deterministically.
        if self.router._is_compare_request(user_message):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Route bare model references through inventory grounding.
        if self.router._is_model_reference_request(user_message, mentioned_vehicles):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Factual follow-ups must be resolved from inventory context. This also
        # gives a safe clarification after a browser reload instead of calling
        # the live model with an ungrounded request such as "notes".
        if self.router._is_fact_question(user_message):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Route explicit vehicle details through inventory grounding.
        if mentioned_vehicles and self.router._is_vehicle_detail_request(user_message):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Route explicit browse requests through grounded inventory search.
        if self.router._is_inventory_browse_request(user_message):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Route service-history requests through deterministic retrieval.
        if self.router._is_service_history_request(user_message):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Route scheduling through deterministic validation.
        # Resolve affirmative replies against pending follow-ups.
        if (
            previous_state
            and previous_state.pending_followup
            and self.router._is_affirmative(user_message)
        ):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        if (
            self.router._is_schedule_request(user_message)
            or (previous_state and previous_state.stage == "scheduling")
        ):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        # Route grounded alternative follow-ups deterministically.
        if (
            previous_state
            and self.router._shown_vehicle_ids(previous_state)
            and self.router._is_alternative_request(user_message)
        ):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        if self.router._is_review_request(user_message):
            return self._respond_live_review(
                conversation_id,
                user_message,
                trace_observer,
                response_observer,
            )
        if (
            previous_state
            and self.router._shown_vehicle_ids(previous_state)
            and self.router._is_contextual_followup(user_message)
        ):
            return self._respond_deterministic(
                conversation_id,
                user_message,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        intent_trace: list[ToolCall] = []
        parsed_intent = self._parse_intent(conversation_id, user_message, intent_trace, trace_observer)
        if (
            parsed_intent
            and parsed_intent.intent == "list_inventory"
            and parsed_intent.confidence >= LLMIntentParser.MIN_CONFIDENCE
        ):
            return self._respond_to_intent(
                conversation_id,
                user_message,
                parsed_intent,
                intent_trace,
                trace_observer=trace_observer,
                response_observer=response_observer,
            )
        return self._respond_live(
            conversation_id,
            user_message,
            trace_observer,
            response_observer,
            initial_trace=intent_trace,
        )

    def _respond_deterministic(
        self,
        conversation_id: str,
        user_message: str,
        *,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        """Run the deterministic router through the live stream contract."""

        response = self.router.respond(
            conversation_id,
            user_message,
            trace_observer=trace_observer,
        )
        if response_observer:
            _emit_response_chunks(response.message, response_observer)
        return response

    def _respond_to_intent(
        self,
        conversation_id: str,
        user_message: str,
        intent: IntentEnvelope,
        initial_trace: list[ToolCall],
        *,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        response = self.router.respond_to_intent(
            conversation_id,
            user_message,
            intent,
            initial_trace=initial_trace,
            trace_observer=trace_observer,
        )
        if response_observer:
            _emit_response_chunks(response.message, response_observer)
        return response

    def _parse_intent(
        self,
        conversation_id: str,
        user_message: str,
        trace: list[ToolCall],
        trace_observer: TraceObserver | None,
    ) -> IntentEnvelope | None:
        """Parse only after deterministic guards, recording a safe trace entry."""

        arguments = {"message_length": len(user_message.strip())}
        if trace_observer:
            trace_observer("start", "parse_intent", arguments, None)
        started = perf_counter()
        parser: IntentParser | None = None
        usage_before = LLMUsage()
        try:
            parser = self.intent_parser or self._new_intent_parser()
            usage_before = _llm_usage_snapshot(getattr(parser, "llm", None))
            intent = IntentEnvelope.model_validate(
                parser.parse(
                    user_message.strip(),
                    known_makes=sorted({vehicle.make for vehicle in self.tools.inventory.all()}),
                )
            )
            result = intent.model_dump()
        except Exception:
            # Continue to CrewAI when parsing fails.
            intent = None
            result = {
                "intent": "general_conversation",
                "confidence": 0.0,
                "fallback": True,
            }
        finally:
            if parser is not None:
                usage_after = _llm_usage_snapshot(getattr(parser, "llm", None))
                self._add_conversation_usage(
                    conversation_id,
                    _usage_delta(usage_after, usage_before),
                )
        call = ToolCall(
            name="parse_intent",
            arguments=arguments,
            result=result,
            duration_ms=(perf_counter() - started) * 1000,
        )
        trace.append(call)
        if trace_observer:
            trace_observer("complete", "parse_intent", arguments, call)
        return intent

    def _new_intent_parser(self) -> IntentParser:
        parser = LLMIntentParser(self._live_llm(), profiler=self.profiler)
        self.intent_parser = parser
        return parser

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

    def _with_conversation_usage(self, conversation_id: str, response: AgentResponse) -> AgentResponse:
        return AgentResponse(
            message=response.message,
            state=response.state,
            trace=response.trace,
            metrics=self.conversation_llm_usage.get(conversation_id, LLMUsage()),
        )

    def _add_conversation_usage(self, conversation_id: str, usage: LLMUsage) -> None:
        current = self.conversation_llm_usage.get(conversation_id, LLMUsage())
        self.conversation_llm_usage[conversation_id] = LLMUsage(
            llm_calls=current.llm_calls + usage.llm_calls,
            prompt_tokens=current.prompt_tokens + usage.prompt_tokens,
            completion_tokens=current.completion_tokens + usage.completion_tokens,
            total_tokens=current.total_tokens + usage.total_tokens,
        )

    def _record_crew_usage(self, conversation_id: str, result: Any) -> None:
        self._add_conversation_usage(conversation_id, _crew_result_usage(result))

    def generate_buyer_dossier(self, conversation_id: str, vehicle_id: str) -> dict[str, Any]:
        """Create an evidence-bound buyer brief for the currently focused listing.

        The target is intentionally validated against conversation state before any
        model work. This keeps the dossier coupled to the same inventory identity
        that was resolved in the chat, rather than letting a model select a nearby
        make/model match from a prompt.
        """

        state = self.sessions.get(conversation_id)
        if state is None or state.focused_vehicle_id != vehicle_id:
            raise ValueError("Resolve this listing in the conversation before generating its dossier.")

        vehicle = self.tools.inventory.get(vehicle_id)
        if vehicle is None:
            raise LookupError("Vehicle not found.")

        facts_result = self.tools.get_vehicle_facts(vehicle_id)
        service_result = self.tools.get_service_history(vehicle_id)
        reviews_result = self.tools.get_magazine_reviews(vehicle_id)
        evidence = self._buyer_dossier_evidence(
            vehicle.to_dict(include_service_history=False),
            facts_result,
            service_result,
            reviews_result,
            state.preferences,
        )
        fallback = _grounded_buyer_dossier(evidence)
        if not self.use_live_model:
            return self._with_dossier_metrics(conversation_id, fallback, mode="grounded_fallback")

        try:
            with self.profiler.span("crewai.buyer_dossier"):
                crew = self.build_buyer_dossier_crew()
                result = crew.kickoff(
                    inputs={
                        "vehicle_name": vehicle.name,
                        "evidence_json": json.dumps(evidence, ensure_ascii=False),
                    }
                )
            self._record_crew_usage(conversation_id, result)
            output = _coerce_buyer_dossier_output(result)
            normalized = _normalize_buyer_dossier_output(output, fallback)
            return self._with_dossier_metrics(conversation_id, normalized, mode="llm")
        except Exception:
            # The dossier is an enhancement, not a reason to make a grounded
            # listing unavailable. Preserve the fully sourced deterministic brief.
            LOGGER.warning(
                "Buyer dossier synthesis failed; returning grounded fallback for conversation %s",
                conversation_id,
                exc_info=True,
            )
            return self._with_dossier_metrics(conversation_id, fallback, mode="grounded_fallback")

    def _with_dossier_metrics(
        self,
        conversation_id: str,
        dossier: dict[str, Any],
        *,
        mode: str,
    ) -> dict[str, Any]:
        return {
            **dossier,
            "mode": mode,
            "metrics": self.conversation_llm_usage.get(conversation_id, LLMUsage()).to_dict(),
        }

    @staticmethod
    def _buyer_dossier_evidence(
        vehicle: dict[str, Any],
        facts_result: dict[str, Any],
        service_result: dict[str, Any],
        reviews_result: dict[str, Any],
        preferences: ShopperPreferences,
    ) -> dict[str, Any]:
        """Limit model input to the exact listing and non-sensitive shopper fit data."""

        return {
            "vehicle": vehicle,
            "shopper_preferences": {
                key: value
                for key, value in preferences.to_dict().items()
                if key in {"budget_max", "intended_use", "body_style", "driving_style", "timeline"}
                and value is not None
            },
            "ownership_facts": facts_result.get("facts", []),
            "service_history": {
                "records": service_result.get("service_history", []),
                "record_count": service_result.get("record_count", 0),
                "synthetic": service_result.get("synthetic", False),
            },
            "editorial_reviews": reviews_result.get("reviews", []),
        }

    def build_buyer_dossier_crew(self) -> Crew:
        """Build a no-tools CrewAI synthesis that can only see supplied evidence."""

        analyst = Agent(
            role="Grounded classic-car buyer analyst",
            goal="Turn one supplied vehicle evidence packet into a cautious purchase brief.",
            backstory=(
                "You separate listing claims, maintenance evidence, ownership notes, and editorial "
                "context. You never fill gaps with automotive lore or assumptions."
            ),
            llm=self._live_llm(),
            tools=[],
            allow_delegation=False,
            max_iter=1,
            verbose=False,
        )
        dossier = Task(
            name="buyer_dossier",
            description=(
                "Write a buyer dossier for {vehicle_name} using only this JSON evidence packet:\n"
                "{evidence_json}\n\n"
                "Every statement must be directly supported by that packet. Do not invent condition, "
                "ownership, pricing, rarity, maintenance, or suitability claims. Treat editorial reviews "
                "as general vehicle context, never as a condition report for this listing. Keep seller "
                "questions and inspection priorities framed as questions or verification steps. If service "
                "records are marked synthetic or the listing provenance is illustrative, say that evidence "
                "needs verification and set recommendation to investigate. Otherwise use buy, investigate, "
                "or pass only when the supplied evidence supports it. Set confidence to low, medium, or high."
            ),
            expected_output=(
                "JSON with summary, fit_reasons, watchouts, seller_questions, inspection_priorities, "
                "recommendation, and confidence."
            ),
            agent=analyst,
            output_pydantic=BuyerDossierOutput,
        )
        return Crew(
            name="buyer_dossier_crew",
            agents=[analyst],
            tasks=[dossier],
            process=Process.sequential,
            verbose=False,
            share_crew=False,
            tracing=False,
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
            ListInventoryTool(self.tools, trace, self.profiler, trace_observer),
            LookupVehicleExactTool(self.tools, trace, self.profiler, trace_observer),
            GetVehicleTool(self.tools, trace, self.profiler, trace_observer),
            GetVehicleFactsTool(self.tools, trace, self.profiler, trace_observer),
            GetServiceHistoryTool(self.tools, trace, self.profiler, trace_observer),
            GetMagazineReviewsTool(self.tools, trace, self.profiler, trace_observer),
            GetVehicleComparisonTool(self.tools, trace, self.profiler, trace_observer),
            CreateTestDriveTool(self.tools, trace, self.profiler, trace_observer),
        ]
        review_instructions = (
            "You are in review-synthesis mode. The supplied review context is the complete source "
            "set for this turn. Synthesize its common themes and meaningful differences without "
            "inventing facts. Mention each outlet and title, cite each source with a Markdown link "
            "using the supplied URL exactly, and state that the editorial material is not a condition "
            "report for the specific listing. Never say you lack access when review context is supplied."
            if review_only
            else "For a magazine-review request, call get_magazine_reviews and include the short "
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
                "snapshot and use list_inventory only to find grounded alternatives. "
                "Never turn a fuzzy search result into an exact availability claim. "
                "For service-history, service-record, or maintenance-record requests, call "
                "get_service_history for the explicitly selected vehicle; do not substitute "
                "general ownership facts for listing history. Clearly label synthetic demo records. "
                "For any test-drive scheduling request, use create_test_drive when all required "
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
        *,
        initial_trace: list[ToolCall] | None = None,
    ) -> AgentResponse:
        with self.profiler.span("crewai.live_turn"):
            previous_state = self.sessions.setdefault(conversation_id, ConversationState(conversation_id))
            self._pin_explicit_vehicle(previous_state, user_message)
            trace: list[ToolCall] = list(initial_trace or [])
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
            self._record_crew_usage(conversation_id, result)
            with self.profiler.span("crewai.output_normalization"):
                output = _coerce_crew_output(result)
                state = _state_from_dict(
                    conversation_id,
                    output.state,
                    previous_state,
                    valid_vehicle_ids=self._inventory_vehicle_ids(),
                )
                self._pin_explicit_vehicle(state, user_message)
            self.sessions[conversation_id] = state
            return AgentResponse(output.message.strip(), state, trace)

    def _pin_explicit_vehicle(self, state: ConversationState, user_message: str) -> None:
        """Keep an explicitly named vehicle authoritative across live turns."""

        mentioned_vehicles = self.tools.inventory.resolve_reference(
            user_message,
            scope_vehicle_ids=self.router._shown_vehicle_ids(state),
        ).candidates
        if len(mentioned_vehicles) != 1:
            return
        vehicle = mentioned_vehicles[0]
        self.router._focus_vehicle(state, vehicle.id)

    def _inventory_vehicle_ids(self) -> set[str]:
        return {vehicle.id for vehicle in self.tools.inventory.all()}

    def _respond_live_review(
        self,
        conversation_id: str,
        user_message: str,
        trace_observer: TraceObserver | None = None,
        response_observer: ResponseObserver | None = None,
    ) -> AgentResponse:
        """Retrieve local review records, then ask CrewAI to synthesize them."""

        prepared = self.router.respond(
            conversation_id,
            user_message,
            trace_observer=trace_observer,
        )
        if not prepared.trace or prepared.trace[-1].name != "get_magazine_reviews":
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
            self._record_crew_usage(conversation_id, result)
            with self.profiler.span("crewai.output_normalization"):
                output = _coerce_crew_output(result)
                state = _state_from_dict(
                    conversation_id,
                    output.state,
                    prepared.state,
                    valid_vehicle_ids=self._inventory_vehicle_ids(),
                )
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
            # Let the caller normalize the final result.
            pass
        return final_result


def _llm_usage_snapshot(llm: Any) -> LLMUsage:
    """Read CrewAI's cumulative usage counter without assuming a provider shape."""

    summary = getattr(llm, "get_token_usage_summary", None)
    if not callable(summary):
        return LLMUsage()
    try:
        return _coerce_llm_usage(summary())
    except Exception:  # pragma: no cover - metrics must never fail a shopper turn
        LOGGER.debug("Could not read LLM usage summary", exc_info=True)
        return LLMUsage()


def _crew_result_usage(result: Any) -> LLMUsage:
    """Extract per-kickoff usage reported by CrewAI, including streamed outputs."""

    # Some streamed CrewAI results retain an empty ``token_usage`` object while
    # exposing the finalized provider totals through ``usage_metrics``. Read
    # both representations so a review synthesis cannot erase metrics simply
    # because the first shape exists but has no values.
    token_usage = _coerce_llm_usage(getattr(result, "token_usage", None))
    usage_metrics = _coerce_llm_usage(getattr(result, "usage_metrics", None))
    return LLMUsage(
        llm_calls=max(token_usage.llm_calls, usage_metrics.llm_calls),
        prompt_tokens=max(token_usage.prompt_tokens, usage_metrics.prompt_tokens),
        completion_tokens=max(token_usage.completion_tokens, usage_metrics.completion_tokens),
        total_tokens=max(token_usage.total_tokens, usage_metrics.total_tokens),
    )


def _coerce_llm_usage(value: Any) -> LLMUsage:
    if value is None:
        return LLMUsage()
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return LLMUsage()

    def as_nonnegative_int(name: str) -> int:
        try:
            return max(0, int(value.get(name, 0)))
        except (TypeError, ValueError):
            return 0

    return LLMUsage(
        llm_calls=as_nonnegative_int("successful_requests"),
        prompt_tokens=as_nonnegative_int("prompt_tokens"),
        completion_tokens=as_nonnegative_int("completion_tokens"),
        total_tokens=as_nonnegative_int("total_tokens"),
    )


def _usage_delta(after: LLMUsage, before: LLMUsage) -> LLMUsage:
    return LLMUsage(
        llm_calls=max(0, after.llm_calls - before.llm_calls),
        prompt_tokens=max(0, after.prompt_tokens - before.prompt_tokens),
        completion_tokens=max(0, after.completion_tokens - before.completion_tokens),
        total_tokens=max(0, after.total_tokens - before.total_tokens),
    )


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


def _coerce_buyer_dossier_output(result: Any) -> BuyerDossierOutput:
    """Normalize a CrewAI result without accepting free-form output as evidence."""

    structured = getattr(result, "pydantic", None)
    if structured is not None:
        return BuyerDossierOutput.model_validate(structured)
    raw = getattr(result, "raw", str(result))
    try:
        return BuyerDossierOutput.model_validate_json(raw)
    except ValueError as exc:
        raise ValueError("CrewAI returned a response that does not match BuyerDossierOutput") from exc


def _normalize_buyer_dossier_output(
    output: BuyerDossierOutput,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Keep an LLM brief bounded and retain deterministic provenance language."""

    recommendation = output.recommendation.strip().lower()
    confidence = output.confidence.strip().lower()
    if recommendation not in {"buy", "investigate", "pass"}:
        recommendation = fallback["recommendation"]
    # A synthetic-only record set never supports a purchase recommendation,
    # even if a model disregards the task instruction.
    if fallback["confidence"] == "low":
        recommendation = fallback["recommendation"]
    if confidence not in {"low", "medium", "high"}:
        confidence = fallback["confidence"]
    if fallback["confidence"] == "low":
        confidence = "low"

    def compact(items: list[str], default: list[str]) -> list[str]:
        cleaned = [item.strip() for item in items if isinstance(item, str) and item.strip()]
        return cleaned[:4] or default

    return {
        "vehicle_id": fallback["vehicle_id"],
        "vehicle_name": fallback["vehicle_name"],
        "summary": output.summary.strip() or fallback["summary"],
        "fit_reasons": compact(output.fit_reasons, fallback["fit_reasons"]),
        "watchouts": compact(output.watchouts, fallback["watchouts"]),
        "seller_questions": compact(output.seller_questions, fallback["seller_questions"]),
        "inspection_priorities": compact(output.inspection_priorities, fallback["inspection_priorities"]),
        "recommendation": recommendation,
        "confidence": confidence,
        # Generated deterministically so the UI can always distinguish listing
        # evidence from editorial context, regardless of model wording.
        "evidence_note": fallback["evidence_note"],
    }


def _grounded_buyer_dossier(evidence: dict[str, Any]) -> dict[str, Any]:
    """Build a useful no-model buyer dossier from the exact evidence packet."""

    vehicle = evidence["vehicle"]
    preferences = evidence["shopper_preferences"]
    facts = evidence["ownership_facts"]
    service = evidence["service_history"]
    reviews = evidence["editorial_reviews"]
    name = str(vehicle["name"])
    price = int(vehicle["price"])
    mileage = int(vehicle["mileage"])
    configuration = ", ".join(
        str(vehicle[key]) for key in ("body_style", "transmission", "drivetrain") if vehicle.get(key)
    )
    summary = (
        f"{name} is listed at ${price:,.0f} with {mileage:,} miles. "
        f"The listing identifies it as a {configuration} vehicle."
    )

    fit_reasons: list[str] = []
    budget = preferences.get("budget_max")
    if isinstance(budget, int):
        relation = "within" if price <= budget else "above"
        fit_reasons.append(
            f"The ${price:,.0f} asking price is {relation} the stated ${budget:,.0f} budget."
        )
    if preferences.get("intended_use"):
        fit_reasons.append(
            f"Your stated use is {preferences['intended_use']}; validate the listing's {configuration} configuration on a drive."
        )
    if preferences.get("driving_style"):
        fit_reasons.append(
            f"Your stated driving preference is {preferences['driving_style']}; keep the test drive focused on whether this configuration fits it."
        )
    if not fit_reasons:
        fit_reasons.append(
            f"The current listing records a {configuration} configuration; use a drive to decide whether it fits your needs."
        )

    watchouts: list[str] = []
    if service.get("synthetic"):
        watchouts.append(
            "The service entries are synthetic demo records, not seller documents or a condition report."
        )
    description = str(vehicle.get("description", "")).strip()
    if description:
        watchouts.append(f"Listing note: {description}")
    for fact in facts[:2]:
        if isinstance(fact, dict) and fact.get("fact"):
            watchouts.append(f"Sourced ownership note: {fact['fact']}")
    if not watchouts:
        watchouts.append("The current packet does not include verified seller documents or an independent condition report.")

    last_record = service.get("records", [])[-1] if service.get("records") else None
    seller_questions = [
        "Can you provide itemized invoices and seller documentation for the listed maintenance?",
        "Are there any condition issues, repairs, or modifications beyond what is described in the listing?",
    ]
    inspection_priorities = [
        "Arrange an independent pre-purchase inspection before relying on the listing or editorial context.",
    ]
    if isinstance(last_record, dict) and last_record.get("service_type"):
        inspection_priorities.append(
            f"Verify the scope and supporting paperwork for the {last_record['service_type']} recorded on {last_record.get('date', 'the latest entry')}."
        )
    else:
        inspection_priorities.append("Confirm the service history with supporting paperwork and a specialist inspection.")

    fact_count = len(facts)
    record_count = int(service.get("record_count", 0))
    review_count = len(reviews)
    service_provenance = " Service history is marked synthetic demo data." if service.get("synthetic") else ""
    evidence_note = (
        f"Grounded in the current inventory listing, {fact_count} ownership fact(s), "
        f"{record_count} service record(s), and {review_count} editorial review(s)."
        f"{service_provenance} Editorial reviews describe the model, not this listing's condition."
    )
    return {
        "vehicle_id": vehicle["id"],
        "vehicle_name": name,
        "summary": summary,
        "fit_reasons": fit_reasons,
        "watchouts": watchouts[:4],
        "seller_questions": seller_questions,
        "inspection_priorities": inspection_priorities,
        "recommendation": "investigate",
        "confidence": "low" if service.get("synthetic") else "medium",
        "evidence_note": evidence_note,
    }


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
    *,
    valid_vehicle_ids: set[str] | None = None,
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
    shown_vehicle_ids = payload.get("shown_vehicle_ids", last_vehicle_ids)
    if not isinstance(shown_vehicle_ids, list) or not all(isinstance(value, str) for value in shown_vehicle_ids):
        shown_vehicle_ids = previous.shown_vehicle_ids or last_vehicle_ids
    shown_vehicle_ids = list(dict.fromkeys(shown_vehicle_ids))
    focused_vehicle_id = payload.get("focused_vehicle_id", preferences.selected_vehicle_id)
    if focused_vehicle_id is not None and not isinstance(focused_vehicle_id, str):
        focused_vehicle_id = previous.focused_vehicle_id
    if valid_vehicle_ids is not None:
        shown_vehicle_ids = [vehicle_id for vehicle_id in shown_vehicle_ids if vehicle_id in valid_vehicle_ids]
        if focused_vehicle_id not in valid_vehicle_ids:
            focused_vehicle_id = None
    # `selected_vehicle_id` is retained for compatibility, but it represents
    # the same concrete focus as the explicit state field.
    preferences.selected_vehicle_id = focused_vehicle_id
    pending_followup = payload.get("pending_followup", previous.pending_followup)
    if pending_followup not in {None, "service_history"}:
        pending_followup = previous.pending_followup
    return ConversationState(
        conversation_id=conversation_id,
        preferences=preferences,
        stage=stage,
        last_vehicle_ids=list(shown_vehicle_ids),
        shown_vehicle_ids=shown_vehicle_ids,
        focused_vehicle_id=focused_vehicle_id,
        pending_followup=pending_followup,
    )


def _env_truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}
