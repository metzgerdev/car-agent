from car_agent.agent import DeterministicRouter
from car_agent.repositories import InventoryRepository
from car_agent.tools import SalesTools


def test_agent_qualifies_then_searches_with_trace() -> None:
    agent = DeterministicRouter()

    first = agent.respond("one", "I want something under $45k.")
    assert first.state.stage == "qualifying"
    assert "use" in first.message.lower() or "driving" in first.message.lower()
    assert first.trace == []

    second = agent.respond("one", "It will be a weekend car for spirited driving, preferably a coupe.")
    assert second.state.stage == "recommending"
    assert second.state.preferences.budget_max == 45_000
    assert second.state.preferences.intended_use == "weekend"
    assert second.state.preferences.driving_style == "spirited"
    assert [call.name for call in second.trace] == [
        "list_inventory",
        "get_vehicle_facts",
    ]
    assert second.state.last_vehicle_ids
    assert "I found" in second.message


def test_inventory_search_respects_budget() -> None:
    tools = SalesTools()
    result = tools.list_inventory({"budget_max": 40_000, "intended_use": "weekend"})

    assert result["count"] == 3
    assert all(vehicle["price"] <= 40_000 for vehicle in result["vehicles"])


def test_compare_uses_last_recommendations() -> None:
    agent = DeterministicRouter()
    agent.respond("compare", "I have $80k for a daily car and like spirited driving.")
    response = agent.respond("compare", "Can you compare those two?")

    assert [call.name for call in response.trace] == ["get_vehicle_comparison"]
    assert "Here’s the short version" in response.message


def test_facts_are_retrieved_for_a_mentioned_vehicle() -> None:
    agent = DeterministicRouter()
    agent.respond("facts", "I have $40k for a weekend car and want analog driving.")
    response = agent.respond("facts", "What should I inspect on the Honda S2000?")

    assert [call.name for call in response.trace] == ["get_vehicle_facts"]
    assert "soft top" in response.message
    assert response.state.preferences.selected_vehicle_id == "honda-s2000-2004"


def test_service_history_is_a_separate_grounded_tool_call() -> None:
    agent = DeterministicRouter()

    response = agent.respond("service-history", "What service history does the Honda S2000 have?")

    assert [call.name for call in response.trace] == ["get_service_history"]
    result = response.trace[0].result
    assert result["vehicle_id"] == "honda-s2000-2004"
    assert result["record_count"] == 3
    assert result["synthetic"] is True
    listing = agent.tools.get_vehicle("honda-s2000-2004")
    assert "service_history" not in listing["vehicle"]
    assert "synthetic demo records" in response.message


def test_service_history_prefers_an_explicit_year_make_model_over_prior_context() -> None:
    agent = DeterministicRouter()

    agent.respond("service-history-explicit", "Show me classic BMWs")
    response = agent.respond(
        "service-history-explicit",
        "What is the maintenance history on the 1971 BMW 2002?",
    )

    assert [call.name for call in response.trace] == ["get_service_history"]
    assert response.trace[0].arguments == {"vehicle_id": "mock-0037"}
    assert "1971 BMW 2002" in response.message
    assert "2008 BMW Z4 M Coupe" not in response.message


def test_detail_request_resolves_a_broad_model_to_one_recent_match() -> None:
    agent = DeterministicRouter()

    browse = agent.respond("recent-model-detail", "Show me classic BMWs")
    shown_vehicle_ids = list(browse.state.shown_vehicle_ids)
    assert shown_vehicle_ids == browse.state.last_vehicle_ids
    assert browse.state.focused_vehicle_id is None

    response = agent.respond("recent-model-detail", "Tell me about the BMW 2002.")

    assert [call.name for call in response.trace] == ["get_vehicle"]
    assert response.trace[0].arguments == {"vehicle_id": "mock-0037"}
    assert "1971 BMW 2002" in response.message
    assert "2008 BMW Z4 M Coupe" not in response.message
    assert response.state.shown_vehicle_ids == shown_vehicle_ids
    assert response.state.focused_vehicle_id == "mock-0037"


def test_detail_request_clarifies_when_a_broad_model_is_still_ambiguous() -> None:
    response = DeterministicRouter().respond("ambiguous-model-detail", "Tell me about the BMW 2002.")

    assert response.trace == []
    assert "multiple listings" in response.message
    assert "1970 BMW 2002" in response.message
    assert "1971 BMW 2002" in response.message


def test_inventory_reference_index_scopes_broad_names_but_keeps_exact_names_global() -> None:
    inventory = InventoryRepository()

    ambiguous = inventory.resolve_reference("Tell me about the BMW 2002")
    assert ambiguous.source == "make_model"
    assert {vehicle.id for vehicle in ambiguous.candidates} == {"mock-0005", "mock-0037"}

    recent = inventory.resolve_reference(
        "Tell me about the BMW 2002",
        scope_vehicle_ids=["bmw-z4-m-2008", "mock-0037"],
    )
    assert recent.source == "recent_results"
    assert recent.vehicle_id == "mock-0037"

    exact = inventory.resolve_reference(
        "Tell me about the 1970 BMW 2002",
        scope_vehicle_ids=["bmw-z4-m-2008", "mock-0037"],
    )
    assert exact.source == "exact_identity"
    assert exact.vehicle_id == "mock-0005"

    assert inventory.resolve_reference("Why is this a good fit for a long trip?").candidates == ()


def test_unqualified_notes_after_a_multi_vehicle_browse_require_a_selection() -> None:
    agent = DeterministicRouter()

    agent.respond("unqualified-notes", "Show me classic BMWs")
    response = agent.respond("unqualified-notes", "Notes")

    assert response.trace == []
    assert "which specific vehicle" in response.message.lower()
    assert response.state.focused_vehicle_id is None


def test_schedule_request_collects_details_then_creates_request() -> None:
    agent = DeterministicRouter()
    recommendation = agent.respond("schedule", "I want a weekend car under $40k with spirited driving.")
    vehicle_name = recommendation.state.last_vehicle_ids[0]

    missing = agent.respond("schedule", f"Please schedule a test drive for {vehicle_name}.")
    assert missing.state.stage == "scheduling"
    assert "name" in missing.message.lower()
    assert "comma-separated list: name, email, time, date" in missing.message

    booked = agent.respond(
        "schedule",
        "Alex Rivera, alex@example.com, 10:00 AM, 2026-09-30",
    )
    assert booked.state.stage == "scheduled"
    assert [call.name for call in booked.trace] == ["create_test_drive"]
    assert "td-0001" in booked.message


def test_schedule_form_normalizes_mailto_and_rejects_invalid_calendar_dates() -> None:
    agent = DeterministicRouter()
    agent.respond("schedule-form", "I want a weekend car under $40k with spirited driving.")

    prompt = agent.respond("schedule-form", "Arrange a test drive.")
    invalid_date = agent.respond(
        "schedule-form",
        "Joe Bob, mailto:joeboab@yolo.com, 10:00 AM, September 31, 2026",
    )

    assert "comma-separated list: name, email, time, date" in prompt.message
    assert invalid_date.state.stage == "scheduling"
    assert "not a valid calendar date" in invalid_date.message
    assert invalid_date.trace == []
    assert invalid_date.state.preferences.name == "Joe Bob"
    assert invalid_date.state.preferences.email == "joeboab@yolo.com"

    booked = agent.respond(
        "schedule-form",
        "Joe Bob, mailto:joeboab@yolo.com, 10:00 AM, September 30, 2026",
    )

    assert booked.state.stage == "scheduled"
    assert booked.trace[-1].arguments["email"] == "joeboab@yolo.com"
    assert booked.trace[-1].arguments["preferred_time"] == "2026-09-30 at 10:00 AM"


def test_repository_can_load_a_custom_inventory(tmp_path) -> None:
    path = tmp_path / "inventory.json"
    path.write_text(
        '[{"id":"test-car","make":"Test","model":"Car","year":2000,"price":1,"mileage":2,"body_style":"coupe","transmission":"manual","drivetrain":"RWD","horsepower":3,"description":"demo","provenance":{"source_url":"local://test/test-car","source_type":"test_fixture","retrieved_at":"2026-09-03T00:00:00Z"}}]'
    )

    inventory = InventoryRepository(path)
    assert inventory.get("test-car").name == "2000 Test Car"
