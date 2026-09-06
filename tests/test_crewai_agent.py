import json

from crewai import Crew
from crewai.types.streaming import CrewStreamingOutput, StreamChunk, StreamChunkType

from car_agent.conversation_context import ConversationTurn
from car_agent.crewai_agent import CrewAISalesAgent, CrewTurnOutput
from car_agent.models import ConversationState, ShopperPreferences
from car_agent.profiling import TimingRecorder


def test_crewai_crew_is_constructed_without_an_api_key() -> None:
    agent = CrewAISalesAgent()

    crew = agent.build_crew()

    assert isinstance(crew, Crew)
    assert crew.name == "classic_car_sales_crew"
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Classic Sports Car Sales Advisor"
    assert {tool.name for tool in crew.agents[0].tools} == {
        "search_inventory",
        "lookup_vehicle_exact",
        "get_vehicle",
        "retrieve_vehicle_facts",
        "retrieve_service_history",
        "retrieve_magazine_reviews",
        "compare_vehicles",
        "schedule_test_drive",
    }
    assert crew.tasks[0].output_pydantic is not None


def test_openrouter_llm_configuration_uses_only_the_openrouter_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-be-used")
    agent = CrewAISalesAgent(use_live_model=True)

    crew = agent.build_crew()
    llm = crew.agents[0].llm

    assert llm.model == "deepseek/deepseek-chat"
    assert llm.provider == "openrouter"
    assert llm.base_url == "https://openrouter.ai/api/v1"
    assert llm.api_key == "test-openrouter-key"


def test_crewai_facade_keeps_offline_acceptance_behavior() -> None:
    agent = CrewAISalesAgent()

    first = agent.respond("crewai-offline", "I want something under $45k.")
    first_stage = first.state.stage
    second = agent.respond(
        "crewai-offline",
        "It will be a weekend car for spirited driving, preferably a coupe.",
    )

    assert first_stage == "qualifying"
    assert second.state.stage == "recommending"
    assert [call.name for call in second.trace] == [
        "search_inventory",
        "get_vehicle",
        "get_vehicle",
        "retrieve_vehicle_facts",
    ]


def test_deterministic_facade_emits_response_deltas() -> None:
    agent = CrewAISalesAgent(use_live_model=False)
    deltas: list[str] = []

    response = agent.respond(
        "offline-stream",
        "I want a weekend car under $45k with spirited driving in a coupe.",
        response_observer=deltas.append,
    )

    assert len(deltas) > 1
    assert "".join(deltas) == response.message


def test_live_facade_completes_bare_vehicle_lookup_without_model_call(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("bare exact vehicle identity should use the deterministic lookup path")

    monkeypatch.setattr(agent, "_respond_live", fail_if_called)

    response = agent.respond("live-bare-exact", "2001 bmw m3")

    assert [call.name for call in response.trace] == ["lookup_vehicle_exact", "search_inventory"]
    assert response.trace[0].result["exact_match"] is False
    assert "2001 bmw m3" in response.message.lower()


def test_live_facade_routes_test_drive_booking_through_traceable_safety_path(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True)
    agent.sessions["live-schedule"] = ConversationState(
        "live-schedule",
        stage="recommending",
        last_vehicle_ids=["honda-s2000-2004"],
        preferences=ShopperPreferences(selected_vehicle_id="honda-s2000-2004"),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("test-drive scheduling must not be delegated to the live model")

    monkeypatch.setattr(agent, "_respond_live", fail_if_called)

    response = agent.respond(
        "live-schedule",
        "Schedule a test drive for the Honda S2000. My name is Alex Rivera, "
        "my email is alex@example.com, and Saturday at 10am works.",
    )

    assert agent.evaluation_route("live-schedule", "Schedule a test drive.")[0] == "deterministic"
    assert response.state.stage == "scheduled"
    assert [call.name for call in response.trace] == ["schedule_test_drive"]
    assert response.trace[0].result["ok"] is True


def test_live_facade_routes_clear_similar_followup_to_grounded_alternatives(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True)
    agent.respond("live-similar", "Do you have a 1999 BMW Z4 in inventory?")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("a clear alternatives follow-up should not ask the model to clarify")

    monkeypatch.setattr(agent, "_respond_live", fail_if_called)

    response = agent.respond("live-similar", "Yeah, tell me about similar sports cars.")

    assert [call.name for call in response.trace] == ["get_vehicle", "get_vehicle", "get_vehicle"]
    assert "2008 BMW Z4 M Coupe" in response.message
    assert "2004 Honda S2000" in response.message


def test_live_facade_routes_vehicle_reference_followup_to_grounded_listing(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True)
    initial = agent.deterministic_agent.respond(
        "live-context-detail",
        "I want a weekend convertible under $40k with spirited driving.",
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("a clear vehicle reference should use the grounded listing")

    monkeypatch.setattr(agent, "_respond_live", fail_if_called)

    response = agent.respond("live-context-detail", "Tell me more about it.")

    assert response.state.preferences.selected_vehicle_id == initial.state.last_vehicle_ids[0]
    assert [call.name for call in response.trace] == ["get_vehicle"]
    assert "Would you like the ownership notes" in response.message


def test_live_facade_synthesizes_contextual_magazine_reviews_with_model(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True, llm="test-model")
    agent.sessions["live-review"] = ConversationState(
        "live-review",
        stage="recommending",
        last_vehicle_ids=["honda-s2000-2004"],
    )

    class FakeCrew:
        def kickoff(self, *, inputs):
            assert inputs["conversation_id"] == "live-review"
            assert "Car and Driver" in inputs["review_context"]
            assert "MotorTrend" in inputs["review_context"]
            assert "https://" in inputs["review_context"]
            return type(
                "FakeCrewOutput",
                (),
                {
                    "pydantic": CrewTurnOutput(
                        message=(
                            "The reviews agree that the Honda S2000 rewards an engaged driver. "
                            "Car and Driver emphasizes its high-revving character, while "
                            "MotorTrend highlights the communicative chassis. "
                            "[Car and Driver](https://www.caranddriver.com/reviews/a15133774/honda-s2000-short-take-road-test/) "
                            "[MotorTrend](https://www.motortrend.com/reviews/honda-s2000-3)"
                        ),
                        state={"stage": "recommending", "last_vehicle_ids": ["honda-s2000-2004"]},
                    )
                },
            )()

    monkeypatch.setattr(agent, "build_crew", lambda trace, review_only=False: FakeCrew())

    response = agent.respond("live-review", "Summarize magazine reviews of the car.")

    assert [call.name for call in response.trace] == ["retrieve_magazine_reviews"]
    assert "Car and Driver" in response.message
    assert "MotorTrend" in response.message
    assert response.message.count("https://") >= 2


def test_live_explicit_vehicle_wins_over_stale_state_for_review_followup(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True, llm="test-model")
    agent.sessions["live-rx7"] = ConversationState(
        "live-rx7",
        stage="recommending",
        last_vehicle_ids=["bmw-z4-m-2008"],
        preferences=ShopperPreferences(selected_vehicle_id="bmw-z4-m-2008"),
    )

    class InitialCrew:
        def kickoff(self, *, inputs):
            assert '"selected_vehicle_id": "mazda-rx7-1992"' in inputs["state_json"]
            return type(
                "FakeCrewOutput",
                (),
                {
                    "pydantic": CrewTurnOutput(
                        message="The 1992 Mazda RX-7 is the rotary-powered lightweight option.",
                        state={
                            "stage": "recommending",
                            "preferences": {"selected_vehicle_id": "bmw-z4-m-2008"},
                            "last_vehicle_ids": ["bmw-z4-m-2008"],
                        },
                    )
                },
            )()

    class ReviewCrew:
        def kickoff(self, *, inputs):
            assert "mazda-rx7-1992" in inputs["review_context"]
            assert "bmw-z4-m-2008" not in inputs["review_context"]
            return type(
                "FakeCrewOutput",
                (),
                {
                    "pydantic": CrewTurnOutput(
                        message="The Car and Driver review places the RX-7 in a lightweight, rotary-powered group.",
                        state={"stage": "recommending", "last_vehicle_ids": ["mazda-rx7-1992"]},
                    )
                },
            )()

    def build_crew(trace, review_only=False):
        return ReviewCrew() if review_only else InitialCrew()

    monkeypatch.setattr(agent, "build_crew", build_crew)

    first = agent.respond("live-rx7", "Tell me more about the RX-7.")
    second = agent.respond("live-rx7", "What do the magazine reviews say about it?")

    assert first.state.preferences.selected_vehicle_id == "mazda-rx7-1992"
    assert second.state.preferences.selected_vehicle_id == "mazda-rx7-1992"
    assert [call.name for call in second.trace] == ["retrieve_magazine_reviews"]


def test_live_crewai_output_is_normalized_to_the_domain_contract(monkeypatch) -> None:
    recorder = TimingRecorder()
    agent = CrewAISalesAgent(use_live_model=True, llm="test-model", profiler=recorder)
    agent.sessions["live-contract"] = ConversationState(
        "live-contract",
        preferences=ShopperPreferences(budget_max=40000),
    )

    class FakeCrew:
        def kickoff(self, *, inputs):
            assert inputs["conversation_id"] == "live-contract"
            return type(
                "FakeCrewOutput",
                (),
                {
                    "pydantic": CrewTurnOutput(
                        message="I found a grounded match.",
                        state={
                            "stage": "recommending",
                            "last_vehicle_ids": ["honda-s2000-2004"],
                        },
                    )
                },
            )()

    monkeypatch.setattr(agent, "build_crew", lambda trace: FakeCrew())

    response = agent.respond("live-contract", "Find me a weekend car.")

    assert response.message == "I found a grounded match."
    assert response.state.stage == "recommending"
    assert response.state.preferences.budget_max == 40000
    assert response.state.last_vehicle_ids == ["honda-s2000-2004"]
    assert {summary.name for summary in recorder.summaries()} >= {
        "crewai.live_turn",
        "crewai.crew_build",
        "crewai.crew_kickoff",
        "crewai.output_normalization",
    }


def test_live_turn_receives_bounded_history_and_grounded_context(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True, llm="test-model")
    conversation_id = "live-hybrid-context"
    agent.sessions[conversation_id] = ConversationState(
        conversation_id,
        stage="recommending",
        preferences=ShopperPreferences(selected_vehicle_id="honda-s2000-2004"),
        last_vehicle_ids=["honda-s2000-2004"],
    )
    agent.turn_history[conversation_id] = [
        ConversationTurn(
            user_message=f"Earlier question {index}",
            assistant_message=f"Earlier answer {index}",
            tool_calls=(
                [
                    {
                        "name": "search_inventory",
                        "arguments": {"filters": {"intended_use": "weekend"}},
                        "result": {"vehicles": [{"id": "honda-s2000-2004"}]},
                    }
                ]
                if index == 0
                else []
            ),
        )
        for index in range(5)
    ]

    class FakeCrew:
        def kickoff(self, *, inputs):
            recent = json.loads(inputs["recent_history"])
            active_vehicle = json.loads(inputs["active_vehicle"])
            grounding = json.loads(inputs["latest_grounding"])
            assert len(recent) == 4
            assert recent[0]["user"] == "Earlier question 1"
            assert "Earlier question 0" in inputs["conversation_summary"]
            assert active_vehicle["id"] == "honda-s2000-2004"
            assert grounding["name"] == "search_inventory"
            return type(
                "FakeCrewOutput",
                (),
                {
                    "pydantic": CrewTurnOutput(
                        message="The S2000 remains the active grounded vehicle.",
                        state={
                            "stage": "recommending",
                            "last_vehicle_ids": ["honda-s2000-2004"],
                        },
                    )
                },
            )()

    monkeypatch.setattr(agent, "build_crew", lambda trace: FakeCrew())

    response = agent.respond(conversation_id, "Why is this a good fit for a long trip?")

    assert response.message == "The S2000 remains the active grounded vehicle."
    assert len(agent.turn_history[conversation_id]) == 6


def test_live_crewai_stream_emits_only_the_shopper_message(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True, llm="test-model")

    final_output = type(
        "FakeCrewOutput",
        (),
        {
            "pydantic": CrewTurnOutput(
                message="The 2004 Honda S2000 is a high-revving roadster.",
                state={"stage": "recommending", "last_vehicle_ids": ["honda-s2000-2004"]},
            )
        },
    )()

    class FakeCrew:
        def kickoff(self, *, inputs):
            stream = CrewStreamingOutput(
                sync_iterator=iter(
                    [
                        StreamChunk(
                            content='{"message":"The 2004 Honda ',
                            chunk_type=StreamChunkType.TEXT,
                        ),
                        StreamChunk(
                            content="S2000 is a high-revving ",
                            chunk_type=StreamChunkType.TEXT,
                        ),
                        StreamChunk(
                            content='roadster.","state":{}}',
                            chunk_type=StreamChunkType.TEXT,
                        ),
                        StreamChunk(
                            content='{"vehicle_id":"honda-s2000-2004"}',
                            chunk_type=StreamChunkType.TOOL_CALL,
                        ),
                    ]
                )
            )
            stream._set_result(final_output)
            return stream

    def build_crew(trace, *, stream=False, trace_observer=None):
        assert stream is True
        return FakeCrew()

    monkeypatch.setattr(agent, "build_crew", build_crew)
    deltas: list[str] = []

    response = agent.respond(
        "live-stream",
        "Tell me more about the S2000.",
        response_observer=deltas.append,
    )

    assert "".join(deltas) == response.message
    assert all("state" not in delta and "vehicle_id" not in delta for delta in deltas)
