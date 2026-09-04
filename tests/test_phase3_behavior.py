from car_agent.agent import DemoSalesAgent
from car_agent.evaluation import run_phase3_evaluation
from car_agent.tools import SalesTools


def test_phase3_progressive_qualification_preserves_state_and_limits_questions() -> None:
    agent = DemoSalesAgent()

    first = agent.respond("phase3-progressive", "My maximum is $40k.")
    second = agent.respond("phase3-progressive", "I will use it on weekends.")
    final = agent.respond("phase3-progressive", "I prefer spirited driving in a coupe.")

    assert first.state.preferences.budget_max == 40_000
    assert second.state.preferences.budget_max == 40_000
    assert second.state.preferences.intended_use == "weekend"
    assert final.state.preferences.driving_style == "spirited"
    assert final.state.stage == "recommending"
    assert all(response.message.count("?") <= 2 for response in (first, second, final))


def test_phase3_budget_is_hard_and_body_style_is_a_soft_ranking_preference() -> None:
    tools = SalesTools()

    convertible = tools.search_inventory(
        {"budget_max": 40_000, "intended_use": "weekend", "driving_style": "spirited", "body_style": "convertible"}
    )
    coupe = tools.search_inventory(
        {"budget_max": 40_000, "intended_use": "weekend", "driving_style": "spirited", "body_style": "coupe"}
    )

    assert all(vehicle["price"] <= 40_000 for vehicle in convertible["vehicles"])
    assert all(vehicle["price"] <= 40_000 for vehicle in coupe["vehicles"])
    assert convertible["vehicles"][0]["id"] == "honda-s2000-2004"
    assert coupe["vehicles"][0]["id"] == "mazda-rx7-1992"


def test_phase3_exact_lookup_returns_authoritative_match_status() -> None:
    tools = SalesTools()

    found = tools.lookup_vehicle_exact({"year": 2008, "make": "bmw", "model": "z4-m coupe"})
    missing = tools.lookup_vehicle_exact({"year": 2011, "make": "BMW", "model": "M3"})

    assert found["exact_match"] is True
    assert found["status"] == "matched"
    assert found["vehicle_id"] == "bmw-z4-m-2008"
    assert missing["exact_match"] is False
    assert missing["status"] == "not_found"
    assert missing["vehicle"] is None


def test_phase3_unavailable_exact_request_searches_only_after_lookup() -> None:
    response = DemoSalesAgent().respond("phase3-exact-availability", "Do you have a 2011 BMW M3 in inventory?")

    assert [call.name for call in response.trace] == ["lookup_vehicle_exact", "search_inventory"]
    assert response.trace[0].result["exact_match"] is False
    assert response.trace[0].result["status"] == "not_found"
    assert "2011 BMW M3" in response.message
    assert "2008 BMW Z4 M Coupe" in response.message


def test_phase3_bare_vehicle_identity_is_an_exact_availability_request() -> None:
    response = DemoSalesAgent().respond("phase3-bare-exact", "2001 bmw m3")

    assert [call.name for call in response.trace] == ["lookup_vehicle_exact", "search_inventory"]
    assert response.trace[0].result["status"] == "not_found"
    assert "2001 bmw m3" in response.message.lower()


def test_phase3_agent_summarizes_reviews_for_the_last_vehicle() -> None:
    agent = DemoSalesAgent()
    agent.respond("phase3-reviews", "I want a weekend roadster under $40k with spirited driving.")

    response = agent.respond("phase3-reviews", "Summarize magazine reviews of the car.")

    assert [call.name for call in response.trace] == ["retrieve_magazine_reviews"]
    assert "Car and Driver" in response.message
    assert "MotorTrend" in response.message
    assert "Read it: https://" in response.message


def test_phase3_ambiguity_does_not_guess_a_porsche_model() -> None:
    response = DemoSalesAgent().respond("phase3-ambiguity", "I like Porsche.")

    assert response.state.stage == "qualifying"
    assert response.trace == []
    assert "specific model" in response.message
    assert "911 Carrera" in response.message
    assert "718 Cayman GTS" in response.message


def test_phase3_unsupported_specification_is_explicitly_qualified() -> None:
    agent = DemoSalesAgent()
    agent.respond("phase3-uncertainty", "I want a weekend coupe under $50k with spirited driving.")

    response = agent.respond(
        "phase3-uncertainty",
        "Does the Porsche 911 Carrera have adaptive cruise?",
    )

    assert response.state.stage == "recommending"
    assert response.trace == []
    assert "won’t guess" in response.message
    assert "official source" in response.message


def test_phase3_objection_uses_a_sourced_tradeoff() -> None:
    agent = DemoSalesAgent()
    agent.respond("phase3-objection", "I want a weekend roadster under $40k with spirited driving.")

    response = agent.respond(
        "phase3-objection",
        "I’m worried about maintenance on the Honda S2000.",
    )

    assert [call.name for call in response.trace] == ["retrieve_vehicle_facts"]
    assert "trade-off" in response.message
    assert "soft top" in response.message
    assert "inspection" in response.message


def test_phase3_evaluation_meets_the_exit_gate() -> None:
    report = run_phase3_evaluation()

    assert report.total_count == 20
    assert report.passed_count >= 18
    assert report.budget_violation_count == 0
    assert all(result.passed for result in report.results)
