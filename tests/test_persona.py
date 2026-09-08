from car_agent.agent import DeterministicRouter
from car_agent.crewai_agent import CrewAISalesAgent
from car_agent.persona import CLASSIC_CAR_PERSONA


def test_persona_contract_is_attached_to_the_crewai_agent() -> None:
    crew = CrewAISalesAgent().build_crew()
    salesperson = crew.agents[0]

    assert salesperson.role == CLASSIC_CAR_PERSONA.role
    assert salesperson.goal == CLASSIC_CAR_PERSONA.goal
    assert salesperson.backstory == CLASSIC_CAR_PERSONA.backstory
    assert "Never invent specifications" in salesperson.backstory
    assert "Never pressure the shopper" in salesperson.backstory
    assert CLASSIC_CAR_PERSONA.task_guidance in crew.tasks[0].description


def test_offline_advisor_uses_the_same_consultative_voice() -> None:
    agent = DeterministicRouter()

    greeting = agent.respond("persona-greeting", "")
    recommendation = agent.respond(
        "persona-recommendation",
        "I want a weekend car under $45k with spirited driving.",
    )

    assert CLASSIC_CAR_PERSONA.greeting in greeting.message
    assert CLASSIC_CAR_PERSONA.recommendation_opening in recommendation.message
    assert "Which one should we dig into" in recommendation.message


def test_offline_vehicle_details_end_with_a_natural_next_step() -> None:
    response = DeterministicRouter().respond("persona-details", "Tell me about the 2004 Honda S2000.")

    assert CLASSIC_CAR_PERSONA.detail_opening in response.message
    assert response.message.endswith("Would you like the ownership notes or a test drive?")
