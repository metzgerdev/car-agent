"""CrewAI orchestration for the classic-car sales conversation.

CrewAI owns the live agent/task/crew boundary in this module. The deterministic
policy remains available as the offline execution mode so the product can keep
its current acceptance tests independent of API keys and network access.
"""

from __future__ import annotations

import json
import os
from typing import Any

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field, PrivateAttr

from .agent import DemoSalesAgent
from .models import AgentResponse, ConversationState, ShopperPreferences, ToolCall
from .repositories import PROJECT_ROOT
from .tools import SalesTools


load_dotenv(PROJECT_ROOT / ".env")


class SearchInventoryInput(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict, description="Hard and soft shopper filters")


class GetVehicleInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")


class RetrieveVehicleFactsInput(BaseModel):
    vehicle_id: str = Field(description="Exact inventory vehicle ID")
    topic: str | None = Field(default=None, description="Optional fact topic such as maintenance")


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
    _trace: list[ToolCall] = PrivateAttr()

    def __init__(self, backend: SalesTools, trace: list[ToolCall]) -> None:
        super().__init__()
        self._backend = backend
        self._trace = trace

    def _record(self, name: str, arguments: dict[str, Any], result: dict[str, Any]) -> str:
        self._trace.append(ToolCall(name=name, arguments=arguments, result=result))
        return json.dumps(result)


class SearchInventoryTool(_CrewSalesTool):
    name: str = "search_inventory"
    description: str = "Search the current used classic sports-car inventory using shopper filters."
    args_schema: type[BaseModel] = SearchInventoryInput

    def _run(self, filters: dict[str, Any]) -> str:
        return self._record("search_inventory", {"filters": filters}, self._backend.search_inventory(filters))


class GetVehicleTool(_CrewSalesTool):
    name: str = "get_vehicle"
    description: str = "Fetch one complete inventory record by its exact vehicle ID."
    args_schema: type[BaseModel] = GetVehicleInput

    def _run(self, vehicle_id: str) -> str:
        return self._record("get_vehicle", {"vehicle_id": vehicle_id}, self._backend.get_vehicle(vehicle_id))


class RetrieveVehicleFactsTool(_CrewSalesTool):
    name: str = "retrieve_vehicle_facts"
    description: str = "Retrieve sourced ownership and vehicle facts for one exact vehicle ID."
    args_schema: type[BaseModel] = RetrieveVehicleFactsInput

    def _run(self, vehicle_id: str, topic: str | None = None) -> str:
        arguments = {"vehicle_id": vehicle_id, "topic": topic}
        return self._record(
            "retrieve_vehicle_facts",
            arguments,
            self._backend.retrieve_vehicle_facts(vehicle_id, topic),
        )


class CompareVehiclesTool(_CrewSalesTool):
    name: str = "compare_vehicles"
    description: str = "Compare exactly two inventory vehicles by their exact IDs."
    args_schema: type[BaseModel] = CompareVehiclesInput

    def _run(self, vehicle_ids: list[str]) -> str:
        return self._record(
            "compare_vehicles",
            {"vehicle_ids": vehicle_ids},
            self._backend.compare_vehicles(vehicle_ids),
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
        result = self._backend.schedule_test_drive(
            vehicle_id=vehicle_id,
            name=name,
            email=email,
            preferred_time=preferred_time,
        )
        return self._record("schedule_test_drive", arguments, result)


class CrewAISalesAgent:
    """Conversation facade backed by CrewAI in live mode and local policy by default."""

    framework = "crewai"

    def __init__(
        self,
        tools: SalesTools | None = None,
        *,
        use_live_model: bool | None = None,
        llm: str | None = None,
    ) -> None:
        self.deterministic_agent = DemoSalesAgent(tools)
        self.tools = self.deterministic_agent.tools
        self.sessions = self.deterministic_agent.sessions
        self.use_live_model = (
            _env_truthy(os.getenv("CAR_AGENT_USE_CREWAI"))
            if use_live_model is None
            else use_live_model
        )
        self.llm = llm or os.getenv("CAR_AGENT_CREWAI_MODEL") or "openrouter/deepseek/deepseek-chat"
        self.last_crew: Crew | None = None

    def respond(self, conversation_id: str, user_message: str) -> AgentResponse:
        if not self.use_live_model:
            return self.deterministic_agent.respond(conversation_id, user_message)
        return self._respond_live(conversation_id, user_message)

    def build_crew(self, trace: list[ToolCall] | None = None) -> Crew:
        """Build the inspectable CrewAI objects without making an LLM call."""

        trace = trace if trace is not None else []
        crew_tools = [
            SearchInventoryTool(self.tools, trace),
            GetVehicleTool(self.tools, trace),
            RetrieveVehicleFactsTool(self.tools, trace),
            CompareVehiclesTool(self.tools, trace),
            ScheduleTestDriveTool(self.tools, trace),
        ]
        salesperson = Agent(
            role="Classic Sports Car Sales Advisor",
            goal="Qualify a shopper, recommend only grounded inventory, and convert interest into a validated test-drive request.",
            backstory=(
                "You are a careful specialist in used classic and modern-classic sports cars. "
                "You ask only useful questions, respect hard budgets, distinguish sourced facts "
                "from judgment, and never invent inventory or ownership claims."
            ),
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
                "Use the inventory and knowledge tools whenever a claim needs grounding. "
                "Preserve prior state, enforce the budget, and return a concise response plus "
                "the complete updated domain state."
            ),
            expected_output="A JSON object with message (string) and state (object).",
            agent=salesperson,
            output_pydantic=CrewTurnOutput,
        )
        self.last_crew = Crew(
            name="classic_car_sales_crew",
            agents=[salesperson],
            tasks=[turn],
            process=Process.sequential,
            verbose=False,
            share_crew=False,
            tracing=False,
        )
        return self.last_crew

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

    def _respond_live(self, conversation_id: str, user_message: str) -> AgentResponse:
        previous_state = self.sessions.setdefault(conversation_id, ConversationState(conversation_id))
        trace: list[ToolCall] = []
        crew = self.build_crew(trace)
        result = crew.kickoff(
            inputs={
                "conversation_id": conversation_id,
                "user_message": user_message.strip(),
                "state_json": json.dumps(previous_state.to_dict()),
            }
        )
        output = _coerce_crew_output(result)
        state = _state_from_dict(conversation_id, output.state, previous_state)
        self.sessions[conversation_id] = state
        return AgentResponse(output.message.strip(), state, trace)


def _coerce_crew_output(result: Any) -> CrewTurnOutput:
    structured = getattr(result, "pydantic", None)
    if structured is not None:
        return CrewTurnOutput.model_validate(structured)
    raw = getattr(result, "raw", str(result))
    try:
        return CrewTurnOutput.model_validate_json(raw)
    except ValueError as exc:
        raise ValueError("CrewAI returned a response that does not match CrewTurnOutput") from exc


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
