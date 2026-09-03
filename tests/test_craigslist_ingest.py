from pathlib import Path

import pytest

from car_agent.craigslist_ingest import ingest_craigslist_csv
from car_agent.crewai_agent import CrewAISalesAgent
from car_agent.repositories import InventoryRepository
from car_agent.tools import SalesTools


PROJECT_ROOT = Path(__file__).parents[1]
SAMPLE_CSV = PROJECT_ROOT / "data" / "craigslist_sample.csv"
HORSEPOWER_MAP = {
    "1234567890": 240,
    "1234567891": 200,
    "1234567892": 343,
    "1234567893": 365,
}


def test_craigslist_sample_ingests_into_sqlite_and_feeds_search(tmp_path) -> None:
    database_path = tmp_path / "craigslist-sample.sqlite"

    accepted, total = ingest_craigslist_csv(
        SAMPLE_CSV,
        database_path,
        HORSEPOWER_MAP,
        retrieved_at="2026-09-03T00:00:00Z",
    )

    repository = InventoryRepository(database_path)
    result = SalesTools(inventory=repository).search_inventory(
        {"budget_max": 40_000, "intended_use": "weekend", "driving_style": "spirited"}
    )

    assert (accepted, total) == (4, 4)
    assert len(repository.all()) == 4
    assert all(vehicle.id.startswith("craigslist-") for vehicle in repository.all())
    assert all(vehicle.provenance.source_type == "craigslist_snapshot" for vehicle in repository.all())
    assert result["count"] == 3
    assert {vehicle["id"] for vehicle in result["vehicles"]} == {
        "craigslist-1234567890",
        "craigslist-1234567891",
        "craigslist-1234567892",
    }

    agent = CrewAISalesAgent(
        tools=SalesTools(inventory=repository),
        use_live_model=False,
    )
    response = agent.respond(
        "craigslist-sample-agent",
        "I want a weekend coupe under $40k with spirited driving.",
    )

    assert response.state.stage == "recommending"
    assert response.state.last_vehicle_ids
    assert response.trace[0].name == "search_inventory"
    assert response.trace[1].result["vehicle"]["provenance"]["source_type"] == "craigslist_snapshot"


def test_craigslist_sample_ingestion_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "craigslist-sample.sqlite"

    first = ingest_craigslist_csv(
        SAMPLE_CSV,
        database_path,
        HORSEPOWER_MAP,
        retrieved_at="2026-09-03T00:00:00Z",
    )
    second = ingest_craigslist_csv(
        SAMPLE_CSV,
        database_path,
        HORSEPOWER_MAP,
        retrieved_at="2026-09-03T00:00:00Z",
    )

    assert first == (4, 4)
    assert second == (4, 4)
    assert len(InventoryRepository(database_path).all()) == 4


def test_missing_craigslist_enrichment_rolls_back_the_batch(tmp_path) -> None:
    database_path = tmp_path / "craigslist-sample.sqlite"

    with pytest.raises(ValueError, match="1234567893"):
        ingest_craigslist_csv(
            SAMPLE_CSV,
            database_path,
            {"1234567890": 240, "1234567891": 200, "1234567892": 343},
            retrieved_at="2026-09-03T00:00:00Z",
        )

    assert InventoryRepository(database_path).all() == []
