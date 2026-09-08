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
        "search_inventory",
        "get_vehicle",
        "get_vehicle",
        "retrieve_vehicle_facts",
    ]
    assert second.state.last_vehicle_ids
    assert "I found" in second.message


def test_inventory_search_respects_budget() -> None:
    tools = SalesTools()
    result = tools.search_inventory({"budget_max": 40_000, "intended_use": "weekend"})

    assert result["count"] == 3
    assert all(vehicle["price"] <= 40_000 for vehicle in result["vehicles"])


def test_compare_uses_last_recommendations() -> None:
    agent = DeterministicRouter()
    agent.respond("compare", "I have $80k for a daily car and like spirited driving.")
    response = agent.respond("compare", "Can you compare those two?")

    assert [call.name for call in response.trace] == ["compare_vehicles"]
    assert "Here’s the short version" in response.message


def test_facts_are_retrieved_for_a_mentioned_vehicle() -> None:
    agent = DeterministicRouter()
    agent.respond("facts", "I have $40k for a weekend car and want analog driving.")
    response = agent.respond("facts", "What should I inspect on the Honda S2000?")

    assert [call.name for call in response.trace] == ["retrieve_vehicle_facts"]
    assert "soft top" in response.message
    assert response.state.preferences.selected_vehicle_id == "honda-s2000-2004"


def test_service_history_is_a_separate_grounded_tool_call() -> None:
    agent = DeterministicRouter()

    response = agent.respond("service-history", "What service history does the Honda S2000 have?")

    assert [call.name for call in response.trace] == ["retrieve_service_history"]
    result = response.trace[0].result
    assert result["vehicle_id"] == "honda-s2000-2004"
    assert result["record_count"] == 3
    assert result["synthetic"] is True
    listing = agent.tools.get_vehicle("honda-s2000-2004")
    assert "service_history" not in listing["vehicle"]
    assert "synthetic demo records" in response.message


def test_schedule_request_collects_details_then_creates_request() -> None:
    agent = DeterministicRouter()
    recommendation = agent.respond("schedule", "I want a weekend car under $40k with spirited driving.")
    vehicle_name = recommendation.state.last_vehicle_ids[0]

    missing = agent.respond("schedule", f"Please schedule a test drive for {vehicle_name}.")
    assert missing.state.stage == "scheduling"
    assert "name" in missing.message.lower()

    booked = agent.respond(
        "schedule",
        "My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works.",
    )
    assert booked.state.stage == "scheduled"
    assert [call.name for call in booked.trace] == ["schedule_test_drive"]
    assert "td-0001" in booked.message


def test_repository_can_load_a_custom_inventory(tmp_path) -> None:
    path = tmp_path / "inventory.json"
    path.write_text(
        '[{"id":"test-car","make":"Test","model":"Car","year":2000,"price":1,"mileage":2,"body_style":"coupe","transmission":"manual","drivetrain":"RWD","horsepower":3,"description":"demo","provenance":{"source_url":"local://test/test-car","source_type":"test_fixture","retrieved_at":"2026-09-03T00:00:00Z"}}]'
    )

    inventory = InventoryRepository(path)
    assert inventory.get("test-car").name == "2000 Test Car"
