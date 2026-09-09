from car_agent.agent import DeterministicRouter
from car_agent.evaluation import run_phase3_evaluation
from car_agent.models import ConversationState
from car_agent.tools import SalesTools


def test_phase3_progressive_qualification_preserves_state_and_limits_questions() -> None:
    agent = DeterministicRouter()

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

    convertible = tools.list_inventory(
        {"budget_max": 40_000, "intended_use": "weekend", "driving_style": "spirited", "body_style": "convertible"}
    )
    coupe = tools.list_inventory(
        {"budget_max": 40_000, "intended_use": "weekend", "driving_style": "spirited", "body_style": "coupe"}
    )

    assert all(vehicle["price"] <= 40_000 for vehicle in convertible["vehicles"])
    assert all(vehicle["price"] <= 40_000 for vehicle in coupe["vehicles"])
    assert convertible["vehicles"][0]["id"] == "honda-s2000-2004"
    assert coupe["vehicles"][0]["id"] == "mazda-rx7-1992"


def test_phase3_exact_lookup_returns_authoritative_match_status() -> None:
    tools = SalesTools()

    found = tools.lookup_vehicle_exact({"year": 2008, "make": "bmw", "model": "z4-m coupe"})
    family = tools.lookup_vehicle_exact({"year": 2008, "make": "BMW", "model": "Z4"})
    missing = tools.lookup_vehicle_exact({"year": 2011, "make": "BMW", "model": "M3"})

    assert found["exact_match"] is True
    assert found["status"] == "matched"
    assert found["vehicle_id"] == "bmw-z4-m-2008"
    assert family["exact_match"] is False
    assert family["status"] == "family_match"
    assert family["vehicle_id"] == "bmw-z4-m-2008"
    assert family["family_matches"][0]["name"] == "2008 BMW Z4 M Coupe"
    assert missing["exact_match"] is False
    assert missing["status"] == "not_found"
    assert missing["vehicle"] is None


def test_phase3_partial_model_identity_returns_family_match_to_shopper() -> None:
    response = DeterministicRouter().respond("phase3-family-match", "2008 BMW Z4")

    assert [call.name for call in response.trace] == ["lookup_vehicle_exact"]
    assert response.trace[0].result["status"] == "family_match"
    assert "found the 2008 BMW Z4 M Coupe" in response.message
    assert "I don’t have" not in response.message


def test_phase3_unavailable_exact_request_searches_only_after_lookup() -> None:
    response = DeterministicRouter().respond("phase3-exact-availability", "Do you have a 2011 BMW M3 in inventory?")

    assert [call.name for call in response.trace] == ["lookup_vehicle_exact", "list_inventory"]
    assert response.trace[0].result["exact_match"] is False
    assert response.trace[0].result["status"] == "not_found"
    assert "2011 BMW M3" in response.message
    assert "2008 BMW Z4 M Coupe" in response.message


def test_phase3_bare_vehicle_identity_is_an_exact_availability_request() -> None:
    response = DeterministicRouter().respond("phase3-bare-exact", "2001 bmw m3")

    assert [call.name for call in response.trace] == ["lookup_vehicle_exact", "list_inventory"]
    assert response.trace[0].result["status"] == "not_found"
    assert "2001 bmw m3" in response.message.lower()


def test_phase3_bare_model_family_reference_checks_inventory() -> None:
    response = DeterministicRouter().respond("phase3-bare-family", "bmw z4")

    assert [call.name for call in response.trace] == ["list_inventory", "get_vehicle"]
    assert response.state.preferences.selected_vehicle_id == "bmw-z4-m-2008"
    assert "2008 BMW Z4 M Coupe" in response.message


def test_phase3_unique_bare_model_token_checks_inventory() -> None:
    response = DeterministicRouter().respond("phase3-bare-token", "911")

    assert [call.name for call in response.trace] == ["list_inventory", "get_vehicle"]
    assert response.state.preferences.selected_vehicle_id == "porsche-911-1999"
    assert "1999 Porsche 911 Carrera" in response.message


def test_phase3_explicit_make_browse_returns_grounded_inventory_options() -> None:
    response = DeterministicRouter().respond("phase3-browse-make", "Show me classic BMWs")

    assert response.trace[0].name == "list_inventory"
    assert response.trace[0].arguments == {"filters": {"query": "BMW"}}
    assert "2008 BMW Z4 M Coupe" in response.message
    assert "1998 BMW E36 328is" in response.message
    assert "Specs: coupe, 6-speed manual, RWD, 343 hp." in response.message


def test_phase3_category_browse_returns_a_search_trace_before_qualification() -> None:
    response = DeterministicRouter().respond("phase3-browse-category", "Find a weekend sports car")

    assert response.trace[0].name == "list_inventory"
    assert response.trace[0].arguments == {"filters": {"intended_use": "weekend"}}
    assert "I found a few promising matches" in response.message


def test_phase3_similar_followup_uses_grounded_alternatives_from_unavailable_lookup() -> None:
    agent = DeterministicRouter()

    first = agent.respond("phase3-similar", "Do you have a 1999 BMW Z4 in inventory?")
    followup = agent.respond("phase3-similar", "Yeah, tell me about similar sports cars.")

    assert first.state.last_vehicle_ids
    assert [call.name for call in followup.trace] == ["get_vehicle", "get_vehicle", "get_vehicle"]
    assert "similar sports cars currently in inventory" in followup.message
    assert "2008 BMW Z4 M Coupe" in followup.message
    assert "2004 Honda S2000" in followup.message
    assert "clarify" not in followup.message.lower()


def test_phase3_vehicle_reference_followup_resolves_it_to_latest_match() -> None:
    agent = DeterministicRouter()
    recommendation = agent.respond(
        "phase3-context",
        "I want a weekend convertible under $40k with spirited driving.",
    )

    followup = agent.respond("phase3-context", "Tell me more about it.")

    selected_id = recommendation.state.last_vehicle_ids[0]
    selected_vehicle = agent.tools.inventory.get(selected_id)
    assert [call.name for call in followup.trace] == ["get_vehicle"]
    assert selected_vehicle is not None
    assert followup.state.preferences.selected_vehicle_id == selected_id
    assert selected_vehicle.name in followup.message
    assert "Would you like the ownership notes" in followup.message


def test_phase3_agent_summarizes_reviews_for_the_last_vehicle() -> None:
    agent = DeterministicRouter()
    agent.respond("phase3-reviews", "I want a weekend roadster under $40k with spirited driving.")

    response = agent.respond("phase3-reviews", "Summarize magazine reviews of the car.")

    assert [call.name for call in response.trace] == ["get_magazine_reviews"]
    assert "Car and Driver" in response.message
    assert "MotorTrend" in response.message
    assert "Read it: [" in response.message
    assert "https://" in response.message


def test_phase3_agent_treats_press_reviews_as_a_magazine_review_request() -> None:
    agent = DeterministicRouter()
    agent.respond("phase3-press-reviews", "2008 BMW Z4")

    response = agent.respond("phase3-press-reviews", "What are the press reviews of the car?")

    assert [call.name for call in response.trace] == ["get_magazine_reviews"]
    assert "MotorTrend" in response.message
    assert "condition report" in response.message


def test_phase3_agent_retrieves_service_history_for_the_explicit_vehicle() -> None:
    response = DeterministicRouter().respond(
        "phase3-service-history",
        "Show me the maintenance records for the 2004 Honda S2000.",
    )

    assert [call.name for call in response.trace] == ["get_service_history"]
    assert "2004 Honda S2000" in response.message
    assert "synthetic demo records" in response.message
    assert response.trace[0].result["service_history"]


def test_phase3_agent_tolerates_a_service_history_typo() -> None:
    agent = DeterministicRouter()
    agent.sessions["phase3-service-typo"] = ConversationState(
        "phase3-service-typo",
        stage="recommending",
        last_vehicle_ids=["honda-s2000-2004"],
    )

    response = agent.respond("phase3-service-typo", "maintanece records")

    assert [call.name for call in response.trace] == ["get_service_history"]
    assert "2004 Honda S2000" in response.message


def test_phase3_ambiguity_does_not_guess_a_porsche_model() -> None:
    response = DeterministicRouter().respond("phase3-ambiguity", "I like Porsche.")

    assert response.state.stage == "qualifying"
    assert response.trace == []
    assert "specific model" in response.message
    assert "911 Carrera" in response.message
    assert "718 Cayman GTS" in response.message


def test_phase3_unsupported_specification_is_explicitly_qualified() -> None:
    agent = DeterministicRouter()
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
    agent = DeterministicRouter()
    agent.respond("phase3-objection", "I want a weekend roadster under $40k with spirited driving.")

    response = agent.respond(
        "phase3-objection",
        "I’m worried about maintenance on the Honda S2000.",
    )

    assert [call.name for call in response.trace] == ["get_vehicle_facts"]
    assert "trade-off" in response.message
    assert "soft top" in response.message
    assert "inspection" in response.message


def test_phase3_evaluation_meets_the_exit_gate() -> None:
    report = run_phase3_evaluation()

    assert report.total_count == 20
    assert report.passed_count >= 18
    assert report.budget_violation_count == 0
    assert all(result.passed for result in report.results)
