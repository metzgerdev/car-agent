"""Deterministic router for grounded sales responses."""

from __future__ import annotations

import re
from contextvars import ContextVar
from datetime import datetime
from difflib import get_close_matches
from time import perf_counter
from typing import Any, Callable, Literal

from .intent_parser import IntentEnvelope
from .lookup_models import ExactVehicleQuery
from .models import (
    AgentResponse,
    ConversationState,
    ShopperPreferences,
    ToolCall,
    Vehicle,
    is_valid_email_address,
    normalize_email_address,
)
from .persona import CLASSIC_CAR_PERSONA
from .profiling import TimingRecorder
from .tools import SalesTools


TraceObserver = Callable[[Literal["start", "complete"], str, dict[str, Any], ToolCall | None], None]
_trace_observer: ContextVar[TraceObserver | None] = ContextVar("trace_observer", default=None)
_SCHEDULING_FORM_INSTRUCTION = (
    "Reply with a comma-separated list: name, email, time, date "
    "(for example, Alex Rivera, alex@example.com, 10:00 AM, 2026-09-30)."
)


class DeterministicRouter:
    """Handle grounded and safety-sensitive turns without an LLM call."""

    def __init__(self, tools: SalesTools | None = None, profiler: TimingRecorder | None = None) -> None:
        self.tools = tools or SalesTools()
        self.profiler = profiler or TimingRecorder(enabled=False)
        self.sessions: dict[str, ConversationState] = {}

    def respond(
        self,
        conversation_id: str,
        user_message: str,
        *,
        trace_observer: TraceObserver | None = None,
    ) -> AgentResponse:
        observer_token = _trace_observer.set(trace_observer)
        try:
            with self.profiler.span("agent.turn"):
                return self._respond(conversation_id, user_message)
        finally:
            _trace_observer.reset(observer_token)

    def respond_to_intent(
        self,
        conversation_id: str,
        user_message: str,
        intent: IntentEnvelope,
        *,
        initial_trace: list[ToolCall] | None = None,
        trace_observer: TraceObserver | None = None,
    ) -> AgentResponse:
        """Execute a validated read-only intent without reparsing raw text."""

        observer_token = _trace_observer.set(trace_observer)
        try:
            with self.profiler.span("agent.intent_route"):
                state = self.sessions.setdefault(conversation_id, ConversationState(conversation_id))
                self._update_preferences(state.preferences, user_message.strip())
                trace = list(initial_trace or [])
                filters = intent.filters.model_dump(exclude_none=True)
                query = filters.pop("query", None)
                for field_name in ("budget_max", "intended_use", "body_style", "driving_style"):
                    if field_name in filters:
                        setattr(state.preferences, field_name, filters[field_name])
                return self._recommend(state, trace, query=query, filter_overrides=filters)
        finally:
            _trace_observer.reset(observer_token)

    def _respond(self, conversation_id: str, user_message: str) -> AgentResponse:
        state = self.sessions.setdefault(conversation_id, ConversationState(conversation_id))
        message = user_message.strip()
        trace: list[ToolCall] = []
        if not message:
            return AgentResponse(
                f"{CLASSIC_CAR_PERSONA.greeting} Tell me a little about the car you’re shopping for.",
                state,
                trace,
            )

        with self.profiler.span("agent.preference_parsing"):
            preference_changed = self._update_preferences(state.preferences, message)
        with self.profiler.span("agent.inventory_mention_detection"):
            reference = self.tools.inventory.resolve_reference(
                message,
                scope_vehicle_ids=self._shown_vehicle_ids(state),
            )
            mentioned_vehicles = list(reference.candidates)

        affirmative_followup = (
            state.pending_followup == "service_history"
            and self._is_affirmative(message)
        )
        if state.pending_followup and not affirmative_followup:
            # Clear the previous follow-up for a new request.
            state.pending_followup = None
        if affirmative_followup:
            vehicle_context = mentioned_vehicles[0] if len(mentioned_vehicles) == 1 else None
            if not mentioned_vehicles and self._has_vehicle_focus(state):
                vehicle_context = self._last_vehicle(state)
            if vehicle_context:
                return self._service_history_summary(state, vehicle_context, trace)
            state.pending_followup = None

        if self._is_schedule_request(message) or state.stage == "scheduling":
            return self._schedule(state, message, mentioned_vehicles, trace)

        if self._is_compare_request(message):
            return self._compare(state, mentioned_vehicles, trace)

        exact_query = self._exact_vehicle_query(message)
        if exact_query:
            return self._lookup_exact(state, exact_query, trace)

        if self._is_alternative_request(message) and self._shown_vehicle_ids(state):
            return self._similar_options(state, mentioned_vehicles, trace)

        if self._is_inventory_browse_request(message):
            return self._browse_inventory(state, message, mentioned_vehicles, trace)

        ambiguous_make = self._ambiguous_make(message, mentioned_vehicles)
        if ambiguous_make:
            state.stage = "qualifying"
            return AgentResponse(ambiguous_make, state, trace)

        vehicle_context = mentioned_vehicles[0] if len(mentioned_vehicles) == 1 else None
        if not mentioned_vehicles and (
            self._has_vehicle_focus(state) or self._has_anaphoric_vehicle_reference(message)
        ):
            vehicle_context = self._last_vehicle(state)
        if len(mentioned_vehicles) > 1 and self._requires_specific_vehicle(message):
            state.stage = "qualifying"
            return AgentResponse(
                self._ambiguous_vehicle_message(mentioned_vehicles),
                state,
                trace,
            )
        if self._is_review_request(message):
            if not vehicle_context:
                state.stage = "qualifying"
                return AgentResponse(
                    "Which specific vehicle should I summarize reviews for? Please name the year and model.",
                    state,
                    trace,
                )
            return self._review_summary(state, vehicle_context, trace)

        if self._is_service_history_request(message):
            if not vehicle_context:
                state.stage = "qualifying"
                return AgentResponse(
                    "Which specific vehicle should I check service history for? Please name the year and model.",
                    state,
                    trace,
                )
            return self._service_history_summary(state, vehicle_context, trace)

        if vehicle_context and self._is_unsupported_spec_question(message):
            self._focus_vehicle(state, vehicle_context.id)
            state.stage = "recommending"
            return AgentResponse(
                f"I don’t have a sourced answer for that specification on the {vehicle_context.name}, so I won’t guess. I can check an official source or arrange an inspection and test drive.",
                state,
                trace,
            )

        if vehicle_context and self._is_objection(message):
            return self._handle_objection(state, vehicle_context, trace, message)

        if self._is_fact_question(message):
            if not vehicle_context:
                state.stage = "qualifying"
                return AgentResponse(
                    "Which specific vehicle would you like notes for? Please name the year and model.",
                    state,
                    trace,
                )
            self._focus_vehicle(state, vehicle_context.id)
            facts = self._call(
                trace,
                "get_vehicle_facts",
                {"vehicle_id": vehicle_context.id},
                lambda: self.tools.get_vehicle_facts(vehicle_context.id),
            )
            state.stage = "recommending"
            return AgentResponse(self._facts_message(vehicle_context, facts), state, trace)

        if vehicle_context and self._is_vehicle_detail_request(message):
            return self._vehicle_details(state, vehicle_context, trace)

        if self._is_model_reference_request(message, mentioned_vehicles):
            return self._model_reference(state, mentioned_vehicles[0], trace)

        if self._needs_qualification(state.preferences):
            state.stage = "qualifying"
            return AgentResponse(self._qualification_question(state.preferences), state, trace)

        if preference_changed or not self._shown_vehicle_ids(state):
            return self._recommend(state, trace)

        if len(mentioned_vehicles) == 1:
            self._focus_vehicle(state, mentioned_vehicles[0].id)
            vehicle_result = self._call(
                trace,
                "get_vehicle",
                {"vehicle_id": mentioned_vehicles[0].id},
                lambda: self.tools.get_vehicle(mentioned_vehicles[0].id),
            )
            return AgentResponse(self._vehicle_message(vehicle_result), state, trace)

        return AgentResponse(
            "Those are the strongest matches so far. Which one would you like to explore, or would you like me to arrange a test drive?",
            state,
            trace,
        )

    def _vehicle_details(
        self,
        state: ConversationState,
        vehicle: Vehicle,
        trace: list[ToolCall],
    ) -> AgentResponse:
        """Resolve a vehicle reference such as "it" and return its listing."""

        self._focus_vehicle(state, vehicle.id)
        state.stage = "recommending"
        result = self._call(
            trace,
            "get_vehicle",
            {"vehicle_id": vehicle.id},
            lambda: self.tools.get_vehicle(vehicle.id),
        )
        return AgentResponse(self._vehicle_message(result), state, trace)

    def _model_reference(
        self,
        state: ConversationState,
        vehicle: Vehicle,
        trace: list[ToolCall],
    ) -> AgentResponse:
        """Ground a bare make/model reference."""

        filters = {"query": f"{vehicle.make} {vehicle.model}"}
        search = self._call(
            trace,
            "list_inventory",
            {"filters": filters},
            lambda: self.tools.list_inventory(filters),
        )
        matches = search.get("vehicles", [])
        if not matches:
            state.stage = "qualifying"
            return AgentResponse(
                f"I don’t have a current {vehicle.make} {vehicle.model} listing to show. What budget and driving use should I keep in mind?",
                state,
                trace,
            )

        # Keep the detected vehicle as the authoritative match.
        self._set_shown_vehicles(state, [vehicle.id])
        self._focus_vehicle(state, vehicle.id)
        state.stage = "recommending"
        result = self._call(
            trace,
            "get_vehicle",
            {"vehicle_id": vehicle.id},
            lambda: self.tools.get_vehicle(vehicle.id),
        )
        return AgentResponse(self._vehicle_message(result), state, trace)

    def _similar_options(
        self,
        state: ConversationState,
        mentioned_vehicles: list[Vehicle],
        trace: list[ToolCall],
    ) -> AgentResponse:
        """Return grounded alternatives."""

        excluded_ids = {
            vehicle.id for vehicle in mentioned_vehicles
        }
        if state.preferences.selected_vehicle_id:
            excluded_ids.add(state.preferences.selected_vehicle_id)
        candidate_ids = [
            vehicle_id
            for vehicle_id in self._shown_vehicle_ids(state)
            if vehicle_id not in excluded_ids
        ]

        # Search inventory when no alternative IDs remain.
        if not candidate_ids:
            preferences = state.preferences
            filters = {
                key: value
                for key, value in {
                    "budget_max": preferences.budget_max,
                    "intended_use": preferences.intended_use,
                    "body_style": preferences.body_style,
                    "driving_style": preferences.driving_style,
                    "query": "sports car",
                }.items()
                if value is not None
            }
            search = self._call(
                trace,
                "list_inventory",
                {"filters": filters},
                lambda: self.tools.list_inventory(filters),
            )
            candidate_ids = [
                vehicle.get("id")
                for vehicle in search.get("vehicles", [])
                if vehicle.get("id") not in excluded_ids
            ]

        vehicles: list[dict[str, Any]] = []
        for vehicle_id in candidate_ids[:3]:
            result = self._call(
                trace,
                "get_vehicle",
                {"vehicle_id": vehicle_id},
                lambda vehicle_id=vehicle_id: self.tools.get_vehicle(vehicle_id),
            )
            if result.get("found") and result.get("vehicle"):
                vehicles.append(result["vehicle"])

        if not vehicles:
            state.stage = "qualifying"
            return AgentResponse(
                "I don’t have other grounded sports-car options to show right now. Would you like to broaden the model or budget criteria?",
                state,
                trace,
            )

        self._set_shown_vehicles(state, [vehicle["id"] for vehicle in vehicles])
        state.stage = "recommending"
        lines = ["Absolutely—here are similar sports cars currently in inventory:"]
        for vehicle in vehicles:
            lines.append(
                f"- {vehicle['name']} — ${vehicle['price']:,}, {vehicle['mileage']:,} miles; {vehicle['description']}"
            )
        lines.append("Would you like more details on one of these?")
        return AgentResponse("\n".join(lines), state, trace)

    def _lookup_exact(
        self,
        state: ConversationState,
        query: ExactVehicleQuery,
        trace: list[ToolCall],
    ) -> AgentResponse:
        with self.profiler.span("agent.exact_availability_flow"):
            return self._lookup_exact_impl(state, query, trace)

    def _lookup_exact_impl(
        self,
        state: ConversationState,
        query: ExactVehicleQuery,
        trace: list[ToolCall],
    ) -> AgentResponse:
        arguments = query.model_dump()
        result = self._call(
            trace,
            "lookup_vehicle_exact",
            arguments,
            lambda: self.tools.lookup_vehicle_exact(arguments),
        )
        requested = f"{query.year} {query.make} {query.model}"

        if result.get("exact_match") and result.get("vehicle"):
            vehicle = result["vehicle"]
            self._set_shown_vehicles(state, [vehicle["id"]])
            self._focus_vehicle(state, vehicle["id"])
            state.stage = "recommending"
            return AgentResponse(self._vehicle_message({"found": True, "vehicle": vehicle}), state, trace)

        if result.get("status") == "family_match" and result.get("vehicle"):
            vehicle = result["vehicle"]
            self._set_shown_vehicles(state, [vehicle["id"]])
            self._focus_vehicle(state, vehicle["id"])
            state.stage = "recommending"
            return AgentResponse(
                f"I found the {vehicle['name']} in inventory. Your request names the {query.make} {query.model} model family; this listing includes the full trim name.\n"
                f"{self._vehicle_message({'found': True, 'vehicle': vehicle})}",
                state,
                trace,
            )

        if result.get("status") == "ambiguous":
            matches = result.get("matches", [])
            self._set_shown_vehicles(state, [vehicle["id"] for vehicle in matches if vehicle.get("id")])
            state.stage = "qualifying"
            names = ", ".join(vehicle.get("name", vehicle.get("id", "unknown")) for vehicle in matches)
            return AgentResponse(
                f"I found multiple current listings matching {requested}: {names}. Which specific listing would you like to explore?",
                state,
                trace,
            )

        preferences = state.preferences
        filters = {
            key: value
            for key, value in {
                "budget_max": preferences.budget_max,
                "intended_use": preferences.intended_use,
                "body_style": preferences.body_style,
                "driving_style": preferences.driving_style,
                "query": f"{query.make} {query.model}",
            }.items()
            if value is not None
        }
        search = self._call(
            trace,
            "list_inventory",
            {"filters": filters},
            lambda: self.tools.list_inventory(filters),
        )
        alternatives = search.get("vehicles", [])
        self._set_shown_vehicles(state, [vehicle["id"] for vehicle in alternatives])
        state.stage = "recommending" if alternatives else "qualifying"

        if not alternatives:
            return AgentResponse(
                f"I don’t have a {requested} in the current inventory, and I don’t have a grounded alternative within those constraints. Would you like to relax a preference?",
                state,
                trace,
            )

        lines = [f"I don’t have a {requested} in the current inventory.", "The closest current alternatives I found are:"]
        for vehicle in alternatives[:3]:
            lines.append(f"- {vehicle['name']} — ${vehicle['price']:,}, {vehicle['mileage']:,} miles; {vehicle['description']}")
        lines.append("Would you like more details on one of these?")
        return AgentResponse("\n".join(lines), state, trace)

    def _recommend(
        self,
        state: ConversationState,
        trace: list[ToolCall],
        query: str | None = None,
        filter_overrides: dict[str, Any] | None = None,
        include_ownership_note: bool = True,
    ) -> AgentResponse:
        with self.profiler.span("agent.recommendation_flow"):
            return self._recommend_impl(
                state,
                trace,
                query=query,
                filter_overrides=filter_overrides,
                include_ownership_note=include_ownership_note,
            )

    def _recommend_impl(
        self,
        state: ConversationState,
        trace: list[ToolCall],
        *,
        query: str | None = None,
        filter_overrides: dict[str, Any] | None = None,
        include_ownership_note: bool = True,
    ) -> AgentResponse:
        preferences = state.preferences
        filters = {
            key: value
            for key, value in {
                "budget_max": preferences.budget_max,
                "intended_use": preferences.intended_use,
                "body_style": preferences.body_style,
                "driving_style": preferences.driving_style,
            }.items()
            if value is not None
        }
        if filter_overrides:
            filters.update(filter_overrides)
        if query:
            filters["query"] = query
        search = self._call(
            trace,
            "list_inventory",
            {"filters": filters},
            lambda: self.tools.list_inventory(filters),
        )
        vehicles = search["vehicles"]
        if not vehicles:
            self._set_shown_vehicles(state, [])
            return AgentResponse(
                "I don’t have a vehicle in the current inventory that fits that budget. Would you like to raise the budget or relax the body-style preference?",
                state,
                trace,
            )

        self._set_shown_vehicles(state, [vehicle["id"] for vehicle in vehicles])
        state.stage = "recommending"
        facts: dict[str, Any] = {}
        if include_ownership_note:
            top_vehicle = vehicles[0]
            facts = self._call(
                trace,
                "get_vehicle_facts",
                {"vehicle_id": top_vehicle["id"]},
                lambda: self.tools.get_vehicle_facts(top_vehicle["id"]),
            )
            # The response names this as the top match and supplies its facts,
            # so it is the only implicit vehicle follow-up can safely target.
            self._focus_vehicle(state, top_vehicle["id"])
        return AgentResponse(self._recommendation_message(vehicles, facts), state, trace)

    def _browse_inventory(
        self,
        state: ConversationState,
        message: str,
        mentioned_vehicles: list[Vehicle],
        trace: list[ToolCall],
    ) -> AgentResponse:
        """Handle an explicit inventory browse request."""

        query = self._inventory_search_query(message, mentioned_vehicles)
        return self._recommend(state, trace, query=query, include_ownership_note=False)

    def _schedule(
        self,
        state: ConversationState,
        message: str,
        mentioned_vehicles: list[Vehicle],
        trace: list[ToolCall],
    ) -> AgentResponse:
        with self.profiler.span("agent.scheduling_flow"):
            return self._schedule_impl(state, message, mentioned_vehicles, trace)

    def _schedule_impl(
        self,
        state: ConversationState,
        message: str,
        mentioned_vehicles: list[Vehicle],
        trace: list[ToolCall],
    ) -> AgentResponse:
        vehicle = mentioned_vehicles[0] if len(mentioned_vehicles) == 1 else None
        if not mentioned_vehicles and self._has_vehicle_focus(state):
            vehicle = self._last_vehicle(state)
        if not vehicle:
            return AgentResponse(
                "Which specific car would you like to drive? Please include its year and model.",
                state,
                trace,
            )

        self._focus_vehicle(state, vehicle.id)
        contact_error = self._update_contact(state.preferences, message)
        if contact_error:
            state.stage = "scheduling"
            return AgentResponse(
                f"I couldn't use that appointment detail: {contact_error} "
                f"{_SCHEDULING_FORM_INSTRUCTION}",
                state,
                trace,
            )
        missing = []
        if not state.preferences.name:
            missing.append("your name")
        if not SalesTools.valid_email(state.preferences.email):
            missing.append("your email")
        if not state.preferences.preferred_time:
            missing.append("a preferred day and time")
        if missing:
            state.stage = "scheduling"
            return AgentResponse(
                f"I can help with the {vehicle.name}. To request it, I still need "
                f"{self._join(missing)}. {_SCHEDULING_FORM_INSTRUCTION}",
                state,
                trace,
            )

        result = self._call(
            trace,
            "create_test_drive",
            {
                "vehicle_id": vehicle.id,
                "name": state.preferences.name,
                "email": state.preferences.email,
                "preferred_time": state.preferences.preferred_time,
            },
            lambda: self.tools.create_test_drive(
                vehicle_id=vehicle.id,
                name=state.preferences.name or "",
                email=state.preferences.email or "",
                preferred_time=state.preferences.preferred_time or "",
            ),
        )
        if not result.get("ok"):
            return AgentResponse(result["error"], state, trace)
        state.stage = "scheduled"
        request = result["request"]
        return AgentResponse(
            f"Your test-drive request is in: {vehicle.name} on {request['preferred_time']}. Request {request['request_id']}.",
            state,
            trace,
        )

    def _compare(
        self,
        state: ConversationState,
        mentioned_vehicles: list[Vehicle],
        trace: list[ToolCall],
    ) -> AgentResponse:
        with self.profiler.span("agent.comparison_flow"):
            return self._compare_impl(state, mentioned_vehicles, trace)

    def _compare_impl(
        self,
        state: ConversationState,
        mentioned_vehicles: list[Vehicle],
        trace: list[ToolCall],
    ) -> AgentResponse:
        vehicles = mentioned_vehicles[:2]
        if len(vehicles) < 2:
            vehicles = [
                self.tools.inventory.get(vehicle_id)
                for vehicle_id in self._shown_vehicle_ids(state)[:2]
            ]
            vehicles = [vehicle for vehicle in vehicles if vehicle]
        if len(vehicles) < 2:
            return AgentResponse(
                "Tell me the two models you want to compare, or let me show you a couple of matches first.",
                state,
                trace,
            )
        result = self._call(
            trace,
            "get_vehicle_comparison",
            {"vehicle_ids": [vehicle.id for vehicle in vehicles]},
            lambda: self.tools.get_vehicle_comparison([vehicle.id for vehicle in vehicles]),
        )
        state.stage = "recommending"
        self._set_shown_vehicles(state, [vehicle.id for vehicle in vehicles])
        first, second = result["vehicles"]
        return AgentResponse(
            f"Here’s the short version: the {first['name']} is ${first['price']:,} and {first['description'].lower()} The {second['name']} is ${second['price']:,} and {second['description'].lower()} Based on your stated preferences, I’d start with the {first['name']}. Want to inspect one or schedule a drive?",
            state,
            trace,
        )

    def _handle_objection(
        self,
        state: ConversationState,
        vehicle: Vehicle,
        trace: list[ToolCall],
        message: str,
    ) -> AgentResponse:
        with self.profiler.span("agent.objection_flow"):
            return self._handle_objection_impl(state, vehicle, trace, message)

    def _handle_objection_impl(
        self,
        state: ConversationState,
        vehicle: Vehicle,
        trace: list[ToolCall],
        message: str,
    ) -> AgentResponse:
        self._focus_vehicle(state, vehicle.id)
        state.stage = "recommending"
        facts = self._call(
            trace,
            "get_vehicle_facts",
            {"vehicle_id": vehicle.id, "topic": "ownership"},
            lambda: self.tools.get_vehicle_facts(vehicle.id, "ownership"),
        )
        fact_text = facts["facts"][0]["fact"] if facts.get("facts") else None
        lowered = message.lower()
        if "price" in lowered or "expensive" in lowered or "cost" in lowered:
            budget = state.preferences.budget_max
            budget_context = (
                f" It is within your ${budget:,} cap, though it uses ${budget - vehicle.price:,} of remaining room."
                if budget is not None and vehicle.price <= budget
                else ""
            )
            tradeoff = (
                f"The trade-off is the asking price of ${vehicle.price:,} for this particular enthusiast model.{budget_context}"
            )
        else:
            tradeoff = "The trade-off is a specialist-oriented ownership profile in exchange for the driving character you asked for."
        grounded_note = f" The sourced ownership note is: {fact_text}" if fact_text else " I do not have a sourced ownership note for it yet."
        return AgentResponse(
            f"That’s a fair concern. {tradeoff}{grounded_note} The next step is a pre-purchase inspection so we can verify condition rather than assume it. Would you like to compare it with another match?",
            state,
            trace,
        )

    def _review_summary(
        self,
        state: ConversationState,
        vehicle: Vehicle,
        trace: list[ToolCall],
    ) -> AgentResponse:
        self._focus_vehicle(state, vehicle.id)
        state.stage = "recommending"
        result = self._call(
            trace,
            "get_magazine_reviews",
            {"vehicle_id": vehicle.id},
            lambda: self.tools.get_magazine_reviews(vehicle.id),
        )
        reviews = result.get("reviews", [])
        if not reviews:
            return AgentResponse(
                f"I don’t have curated magazine reviews for the {vehicle.name} in the current review dataset. I can still provide sourced ownership facts or arrange an inspection.",
                state,
                trace,
            )

        state.pending_followup = "service_history"
        lines = [f"Here’s the magazine-review summary for the {vehicle.name}:"]
        for review in reviews:
            lines.append(
                f"- {review['outlet']} — {review['title']}: {review['summary']} "
                f"Read it: [{review['outlet']}]({review['url']})"
            )
        lines.append("These are editorial impressions, not a condition report for this specific listing.")
        return AgentResponse("\n".join(lines), state, trace)

    def _service_history_summary(
        self,
        state: ConversationState,
        vehicle: Vehicle,
        trace: list[ToolCall],
    ) -> AgentResponse:
        """Return listing service records."""

        self._focus_vehicle(state, vehicle.id)
        state.stage = "recommending"
        state.pending_followup = None
        result = self._call(
            trace,
            "get_service_history",
            {"vehicle_id": vehicle.id},
            lambda: self.tools.get_service_history(vehicle.id),
        )
        records = result.get("service_history", [])
        if not records:
            return AgentResponse(
                f"I don’t have service history on file for the {vehicle.name}. I can arrange an inspection and test drive so its condition can be verified.",
                state,
                trace,
            )

        lines = [f"Here’s the service history on file for the {vehicle.name}:"]
        for record in records:
            lines.append(
                f"- {record['date']} at {record['mileage']:,} miles — {record['service_type']}: {record['details']}"
            )
        if result.get("synthetic"):
            lines.append("These are synthetic demo records, not seller documents or a condition report.")
        lines.append("A pre-purchase inspection is still the right next step. Would you like to arrange one or a test drive?")
        return AgentResponse("\n".join(lines), state, trace)

    def _call(
        self,
        trace: list[ToolCall],
        name: str,
        arguments: dict[str, Any],
        function: Any,
    ) -> dict[str, Any]:
        observer = _trace_observer.get()
        if observer:
            observer("start", name, arguments, None)
        started = perf_counter()
        with self.profiler.span(f"tool.{name}"):
            result = function()
        duration_ms = (perf_counter() - started) * 1000
        call = ToolCall(
            name=name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )
        trace.append(call)
        if observer:
            observer("complete", name, arguments, call)
        return result

    @staticmethod
    def _needs_qualification(preferences: ShopperPreferences) -> bool:
        return preferences.budget_max is None or preferences.intended_use is None or preferences.driving_style is None

    @staticmethod
    def _qualification_question(preferences: ShopperPreferences) -> str:
        if preferences.budget_max is None:
            return "What’s your maximum budget, and are you picturing a coupe or a convertible?"
        missing = []
        if preferences.intended_use is None:
            missing.append("how you’ll use it (daily, weekend, or track)")
        if preferences.driving_style is None:
            missing.append("your driving style (relaxed, spirited, or analog/raw)")
        if len(missing) == 2:
            return f"Great—up to ${preferences.budget_max:,}. Could you tell me {missing[0]} and {missing[1]}?"
        return f"Great—up to ${preferences.budget_max:,}. Could you tell me {missing[0]}?"

    @staticmethod
    def _recommendation_message(vehicles: list[dict[str, Any]], facts: dict[str, Any]) -> str:
        lines = [f"{CLASSIC_CAR_PERSONA.recommendation_opening}:"]
        for vehicle in vehicles[:3]:
            specs = ", ".join(
                str(value)
                for value in (
                    vehicle.get("body_style"),
                    vehicle.get("transmission"),
                    vehicle.get("drivetrain"),
                    f"{vehicle['horsepower']} hp" if vehicle.get("horsepower") is not None else None,
                )
                if value
            )
            specs_suffix = f" Specs: {specs}." if specs else ""
            lines.append(
                f"- {vehicle['name']} — ${vehicle['price']:,}, {vehicle['mileage']:,} miles; "
                f"{vehicle['description']}{specs_suffix}"
            )
        if facts.get("facts"):
            fact = facts["facts"][0]
            lines.append(f"One ownership note on the top match: {fact['fact']} ({fact['source']}).")
        lines.append("Which one should we dig into, or would you like to request a test drive?")
        return "\n".join(lines)

    @staticmethod
    def _facts_message(vehicle: Vehicle, facts: dict[str, Any]) -> str:
        if not facts.get("facts"):
            return f"I don’t have a sourced note for the {vehicle.name} yet. I can still arrange an inspection or test drive."
        fact_text = " ".join(f"{fact['topic'].title()}: {fact['fact']}" for fact in facts["facts"])
        return f"For the {vehicle.name}: {fact_text} The next sensible step is a specialist inspection and a drive."

    @staticmethod
    def _vehicle_message(result: dict[str, Any]) -> str:
        if not result.get("found"):
            return "I couldn’t find that vehicle in the current inventory."
        vehicle = result["vehicle"]
        return f"{CLASSIC_CAR_PERSONA.detail_opening}: the {vehicle['name']} is listed at ${vehicle['price']:,} with {vehicle['mileage']:,} miles. {vehicle['description']} Would you like the ownership notes or a test drive?"

    @staticmethod
    def _facts_question(message: str) -> bool:
        return bool(
            re.search(
                r"\b(ownership|maintenance|inspect|inspection|service|spec|reliable|reliability|common|notes?)\b",
                message.lower(),
            )
        )

    @classmethod
    def _is_fact_question(cls, message: str) -> bool:
        return cls._facts_question(message)

    @staticmethod
    def _is_review_request(message: str) -> bool:
        lowered = message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "magazine review",
                "magazine reviews",
                "press review",
                "press reviews",
                "automotive press",
                "car reviews",
                "auto reviews",
                "car and driver",
                "motortrend",
                "motor trend",
                "road test",
                "editorial review",
            )
        )

    @staticmethod
    def _is_service_history_request(message: str) -> bool:
        lowered = message.lower()
        if any(
            phrase in lowered
            for phrase in (
                "service history",
                "service record",
                "service records",
                "maintenance history",
                "maintenance records",
                "maintenance record",
                "work has been done",
                "previous service",
                "service receipts",
            )
        ):
            return True

        # Require a record term with the fuzzy maintenance match.
        tokens = re.findall(r"[a-z]+", lowered)
        has_record_term = any(
            token in {"history", "record", "records", "receipt", "receipts", "done", "work"}
            for token in tokens
        )
        return has_record_term and bool(get_close_matches("maintenance", tokens, n=1, cutoff=0.72))

    @staticmethod
    def _is_affirmative(message: str) -> bool:
        normalized = re.sub(r"[.!?]+$", "", message.strip().lower())
        return normalized in {
            "yes",
            "yeah",
            "yep",
            "yup",
            "sure",
            "please",
            "please do",
            "go ahead",
            "that sounds good",
        }

    @staticmethod
    def _is_compare_request(message: str) -> bool:
        return "compar" in message.lower() or "versus" in message.lower() or re.search(r"\bvs\.?\b", message.lower()) is not None

    @staticmethod
    def _is_alternative_request(message: str) -> bool:
        lowered = message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "similar sports car",
                "similar car",
                "similar vehicle",
                "something similar",
                "other option",
                "other car",
                "alternative",
                "what else",
            )
        )

    @staticmethod
    def _is_vehicle_detail_request(message: str) -> bool:
        lowered = message.lower()
        if any(
            phrase in lowered
            for phrase in (
                "tell me more",
                "more details",
                "more info",
                "more information",
                "learn more",
                "tell me about",
                "what about",
                "how about",
                "what is it like",
                "what's it like",
            )
        ):
            return True
        return re.search(r"\b(it|that one|that car|the car|the vehicle)\b", lowered) is not None

    def _is_model_reference_request(
        self,
        message: str,
        mentioned_vehicles: list[Vehicle] | None = None,
    ) -> bool:
        """Identify a known make/model reference."""

        vehicles = mentioned_vehicles if mentioned_vehicles is not None else self.tools.inventory.find_in_text(message)
        if len(vehicles) != 1:
            return False
        normalized_message = _normalize_vehicle_identity(message.strip(" .?!"))
        vehicle = vehicles[0]
        identities = {
            _normalize_vehicle_identity(f"{vehicle.make} {vehicle.model}"),
            _normalize_vehicle_identity(vehicle.model),
            _normalize_vehicle_identity(vehicle.name),
            _normalize_vehicle_identity(
                f"{vehicle.make} {vehicle.model.split()[0]}"
            ),
            _normalize_vehicle_identity(vehicle.model.split()[0]),
        }
        return normalized_message in identities

    @classmethod
    def _is_contextual_followup(cls, message: str) -> bool:
        return any(
            predicate(message)
            for predicate in (
                cls._is_alternative_request,
                cls._is_compare_request,
                cls._is_schedule_request,
                cls._is_fact_question,
                cls._is_vehicle_detail_request,
            )
        )

    def _exact_vehicle_query(self, message: str) -> ExactVehicleQuery | None:
        if not self._is_availability_request(message):
            return None

        year_match = re.search(r"\b(?:19|20)\d{2}\b", message)
        if not year_match:
            return None
        year = int(year_match.group(0))

        # Prefer complete inventory names for multi-word models.
        inventory = self.tools.inventory.all()
        normalized_message = _normalize_vehicle_identity(message)
        for vehicle in inventory:
            if _normalize_vehicle_identity(vehicle.name) in normalized_message:
                return ExactVehicleQuery(year=vehicle.year, make=vehicle.make, model=vehicle.model)

        makes = sorted({vehicle.make for vehicle in inventory}, key=len, reverse=True)
        for make in makes:
            match = re.search(rf"\b{re.escape(make)}\b", message, re.IGNORECASE)
            if not match:
                continue
            model_tokens = self._model_tokens_after_make(message[match.end() :], year)
            if model_tokens:
                return ExactVehicleQuery(year=year, make=make, model=" ".join(model_tokens))

        # Build a make-only fallback for unknown models.
        generic = re.search(
            r"\b(?:19|20)\d{2}\s+([A-Za-z][A-Za-z0-9-]*)\s+([A-Za-z0-9][A-Za-z0-9-]*)",
            message,
        )
        if generic:
            return ExactVehicleQuery(year=year, make=generic.group(1), model=generic.group(2))
        return None

    @staticmethod
    def _is_availability_request(message: str) -> bool:
        lowered = message.lower()
        if any(
            phrase in lowered
            for phrase in (
                "do you have",
                "have any",
                "in inventory",
                "in stock",
                "available",
                "carry",
                "looking for",
                "find me",
                "is there",
            )
        ):
            return True
        # Treat a compact year/make/model identity as an availability request.
        return re.fullmatch(
            r"\s*(?:19|20)\d{2}\s+[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z0-9][A-Za-z0-9-]*){1,5}\s*(?:[?.!]\s*)?$",
            message,
        ) is not None

    @staticmethod
    def _model_tokens_after_make(text: str, year: int) -> list[str]:
        stop_words = {
            "a",
            "an",
            "the",
            "from",
            "in",
            "under",
            "with",
            "for",
            "or",
            "and",
            "available",
            "inventory",
            "stock",
            "please",
            "similar",
            "something",
            "do",
            "you",
            "have",
            "is",
            "there",
        }
        tokens: list[str] = []
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", text):
            lowered = token.casefold()
            if lowered in stop_words or token == str(year):
                break
            tokens.append(token)
        return tokens

    @staticmethod
    def _is_schedule_request(message: str) -> bool:
        lowered = message.lower()
        return "test drive" in lowered or "test-drive" in lowered or "schedule" in lowered or "book" in lowered

    @staticmethod
    def _is_inventory_browse_request(message: str) -> bool:
        """Recognize requests that explicitly ask to see available inventory."""

        lowered = message.lower()
        browse_phrase = bool(re.search(r"\bfind(?:\s+me)?\b", lowered)) or any(
            phrase in lowered
            for phrase in (
                "show me",
                "what do you have",
                "what's available",
                "what is available",
                "browse",
                "list",
                "give me options",
                "show me options",
            )
        )
        if any(phrase in lowered for phrase in ("review", "service history", "maintenance record")):
            return False
        inventory_subject = any(
            term in lowered
            for term in (
                "car",
                "cars",
                "vehicle",
                "vehicles",
                "inventory",
                "sports",
                "classic",
                "roadster",
                "coupe",
                "convertible",
                "options",
            )
        )
        return browse_phrase and inventory_subject

    def _inventory_search_query(self, message: str, mentioned_vehicles: list[Vehicle]) -> str | None:
        """Reduce natural-language browse text to a searchable identity hint."""

        if len(mentioned_vehicles) == 1:
            vehicle = mentioned_vehicles[0]
            return f"{vehicle.make} {vehicle.model}"

        lowered = message.lower()
        makes = sorted({vehicle.make for vehicle in self.tools.inventory.all()}, key=len, reverse=True)
        for make in makes:
            # Match singular and plural make names.
            if re.search(rf"\b{re.escape(make.lower())}s?\b", lowered):
                return make
        return None

    def _ambiguous_make(self, message: str, mentioned_vehicles: list[Vehicle]) -> str | None:
        if mentioned_vehicles:
            return None
        lowered = message.lower()
        vehicles = self.tools.inventory.all()
        makes = {vehicle.make.lower(): vehicle.make for vehicle in vehicles}
        for make_lower, make in makes.items():
            if not re.search(rf"\b{re.escape(make_lower)}\b", lowered):
                continue
            candidates = [vehicle for vehicle in vehicles if vehicle.make.lower() == make_lower]
            model_names = ", ".join(vehicle.model for vehicle in candidates)
            return f"{make} has a few different directions here ({model_names}). Which specific model would you like me to consider?"
        return None

    @staticmethod
    def _shown_vehicle_ids(state: ConversationState) -> list[str]:
        """Return the current result set, including state created before focus support."""

        return state.shown_vehicle_ids or state.last_vehicle_ids

    @staticmethod
    def _set_shown_vehicles(state: ConversationState, vehicle_ids: list[str]) -> None:
        """Replace the visible result set and clear any prior single-vehicle focus."""

        unique_ids = list(dict.fromkeys(vehicle_id for vehicle_id in vehicle_ids if vehicle_id))
        state.shown_vehicle_ids = unique_ids
        # Keep the legacy field synchronized for existing clients and persisted sessions.
        state.last_vehicle_ids = list(unique_ids)
        state.focused_vehicle_id = None
        state.preferences.selected_vehicle_id = None

    @staticmethod
    def _focus_vehicle(state: ConversationState, vehicle_id: str) -> None:
        """Pin subsequent contextual requests to an inventory-backed vehicle ID."""

        state.focused_vehicle_id = vehicle_id
        state.preferences.selected_vehicle_id = vehicle_id
        if not state.shown_vehicle_ids and not state.last_vehicle_ids:
            state.shown_vehicle_ids = [vehicle_id]
            state.last_vehicle_ids = [vehicle_id]

    @staticmethod
    def _has_vehicle_focus(state: ConversationState) -> bool:
        return bool(
            state.focused_vehicle_id
            or state.preferences.selected_vehicle_id
            # Legacy persisted state had one vehicle list serving as the focus.
            # A single current result is similarly unambiguous.
            or len(DeterministicRouter._shown_vehicle_ids(state)) == 1
        )

    @staticmethod
    def _has_anaphoric_vehicle_reference(message: str) -> bool:
        return re.search(r"\b(it|that one|that car|the car|the vehicle)\b", message.lower()) is not None

    @staticmethod
    def _ambiguous_vehicle_message(vehicles: list[Vehicle]) -> str:
        names = ", ".join(vehicle.name for vehicle in vehicles)
        return f"I found multiple listings matching that model: {names}. Which year or listing would you like to explore?"

    def _requires_specific_vehicle(self, message: str) -> bool:
        return any(
            (
                self._is_review_request(message),
                self._is_service_history_request(message),
                self._is_fact_question(message),
                self._is_vehicle_detail_request(message),
                self._is_unsupported_spec_question(message),
                self._is_objection(message),
            )
        )

    @staticmethod
    def _is_unsupported_spec_question(message: str) -> bool:
        lowered = message.lower()
        unsupported = (
            "adaptive cruise",
            "blind spot",
            "lane keep",
            "lane assist",
            "four-wheel steering",
            "4-wheel steering",
            "carfax",
            "title history",
            "warranty",
            "towing capacity",
        )
        return any(phrase in lowered for phrase in unsupported)

    @staticmethod
    def _is_objection(message: str) -> bool:
        lowered = message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "too expensive",
                "price",
                "cost",
                "maintenance",
                "repair bill",
                "worried",
                "concern",
                "reliability",
            )
        )

    def _last_vehicle(self, state: ConversationState) -> Vehicle | None:
        vehicle_id = state.focused_vehicle_id or state.preferences.selected_vehicle_id
        if vehicle_id:
            return self.tools.inventory.get(vehicle_id)
        shown_vehicle_ids = self._shown_vehicle_ids(state)
        if shown_vehicle_ids:
            return self.tools.inventory.get(shown_vehicle_ids[0])
        return None

    @classmethod
    def _update_preferences(cls, preferences: ShopperPreferences, message: str) -> bool:
        changed = False
        budget = cls._parse_budget(message)
        if budget is not None and budget != preferences.budget_max:
            preferences.budget_max = budget
            changed = True

        lowered = message.lower()
        for phrases, attribute, value in [
            (["convertible", "roadster", "open air", "open-air"], "body_style", "convertible"),
            (["coupe"], "body_style", "coupe"),
            (["daily", "commute"], "intended_use", "daily"),
            (["weekend", "Sunday drive"], "intended_use", "weekend"),
            (["track", "autocross"], "intended_use", "track"),
            (["grand tour", "long distance", "long-distance"], "intended_use", "grand-tourer"),
            (["spirited", "twisty", "fun driving"], "driving_style", "spirited"),
            (["analog", "raw", "engaging"], "driving_style", "analog"),
            (["relaxed", "comfortable", "cruising"], "driving_style", "relaxed"),
        ]:
            if any(phrase.lower() in lowered for phrase in phrases) and getattr(preferences, attribute) != value:
                setattr(preferences, attribute, value)
                changed = True
        return changed

    @staticmethod
    def _parse_budget(message: str) -> int | None:
        patterns = [
            r"(?:under|below|up to|max(?:imum)?(?: budget)?|budget(?: of)?|spend(?:ing)?(?: up to)?)\s*\$?\s*(\d+(?:[,.]\d+)*)\s*([km])?",
            r"\$\s*(\d+(?:[,.]\d+)*)\s*([km])?\s*(?:budget|max(?:imum)?)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                amount = float(match.group(1).replace(",", ""))
                suffix = match.group(2)
                if suffix == "k":
                    amount *= 1_000
                elif suffix == "m":
                    amount *= 1_000_000
                return int(amount)
        return None

    @staticmethod
    def _update_contact(preferences: ShopperPreferences, message: str) -> str | None:
        """Update scheduling details, preferring the explicit comma-separated form."""

        form_parts = [part.strip() for part in message.split(",", maxsplit=3)]
        is_explicit_form = (
            len(form_parts) == 4
            and not re.search(r"\b(?:schedule|arrange|book|test drive)\b", form_parts[0], re.IGNORECASE)
        )
        if is_explicit_form:
            name, email, appointment_time, appointment_date = form_parts
            if not name:
                return "The name field is blank."
            preferences.name = name

            normalized_email = normalize_email_address(email)
            if not is_valid_email_address(normalized_email):
                return "The email address is not valid."
            preferences.email = normalized_email

            normalized_time = DeterministicRouter._parse_appointment_time(appointment_time)
            if not normalized_time:
                return "The time must look like 10:00 AM or 14:00."
            normalized_date = DeterministicRouter._parse_appointment_date(appointment_date)
            if not normalized_date:
                return f"{appointment_date!r} is not a valid calendar date."
            preferences.preferred_time = f"{normalized_date} at {normalized_time}"
            return None

        email = re.search(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
            message,
        )
        if email:
            preferences.email = normalize_email_address(email.group(0).rstrip(".,"))
        name = re.search(r"(?:my name is|i am|i'm|im)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", message, re.IGNORECASE)
        if name and name.group(1).lower().split()[0] not in {"looking", "interested", "hoping", "trying"}:
            preferences.name = name.group(1).strip(" .,!?")
        time = re.search(
            r"\b(today|tomorrow|(?:this\s+)?(?:sat(?:urday)?|sun(?:day)?|mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?))\b(?:\s+(?:at|around)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?))?",
            message,
            re.IGNORECASE,
        )
        if time:
            preferences.preferred_time = " ".join(part for part in time.groups() if part).strip()
        return None

    @staticmethod
    def _parse_appointment_time(value: str) -> str | None:
        candidate = re.sub(
            r"(?i)\b([0-9]{1,2}(?::[0-9]{2})?)\s*(am|pm)\b",
            r"\1 \2",
            value.strip(),
        ).upper()
        for time_format in ("%I:%M %p", "%I %p", "%H:%M"):
            try:
                return datetime.strptime(candidate, time_format).strftime("%I:%M %p").lstrip("0")
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_appointment_date(value: str) -> str | None:
        candidate = value.strip()
        for date_format in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(candidate, date_format).date().isoformat()
            except ValueError:
                continue
        return None

    @staticmethod
    def _join(items: list[str]) -> str:
        if len(items) == 1:
            return items[0]
        if len(items) == 2:
            return f"{items[0]} and {items[1]}"
        return ", ".join(items[:-1]) + f", and {items[-1]}"


def _normalize_vehicle_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())
