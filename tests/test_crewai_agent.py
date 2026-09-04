from crewai import Crew

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


def test_live_facade_completes_bare_vehicle_lookup_without_model_call(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("bare exact vehicle identity should use the deterministic lookup path")

    monkeypatch.setattr(agent, "_respond_live", fail_if_called)

    response = agent.respond("live-bare-exact", "2001 bmw m3")

    assert [call.name for call in response.trace] == ["lookup_vehicle_exact", "search_inventory"]
    assert response.trace[0].result["exact_match"] is False
    assert "2001 bmw m3" in response.message.lower()


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
