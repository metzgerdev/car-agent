from crewai import Crew

from car_agent.crewai_agent import CrewAISalesAgent, CrewTurnOutput
from car_agent.models import ConversationState, ShopperPreferences


def test_crewai_crew_is_constructed_without_an_api_key() -> None:
    agent = CrewAISalesAgent()

    crew = agent.build_crew()

    assert isinstance(crew, Crew)
    assert crew.name == "classic_car_sales_crew"
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Classic Sports Car Sales Advisor"
    assert {tool.name for tool in crew.agents[0].tools} == {
        "search_inventory",
        "get_vehicle",
        "retrieve_vehicle_facts",
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


def test_live_crewai_output_is_normalized_to_the_domain_contract(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True, llm="test-model")
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
