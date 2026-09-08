import json

import pytest

from car_agent.data_pipeline import (
    InventoryValidationError,
    load_inventory_fixture,
)
from car_agent.repositories import InventoryRepository, KnowledgeRepository
from scripts.generate_mock_inventory import CATALOG, generate_record


def _record(**overrides):
    record = {
        "id": "fixture-car",
        "make": "Fixture",
        "model": "Sport",
        "year": 2005,
        "price": 25_000,
        "mileage": 50_000,
        "body_style": "coupe",
        "transmission": "manual",
        "drivetrain": "RWD",
        "horsepower": 250,
        "description": "fixture vehicle",
        "tags": ["weekend"],
        "provenance": {
            "source_url": "local://phase2/fixture-car",
            "source_type": "test_fixture",
            "retrieved_at": "2026-09-03T00:00:00Z",
        },
    }
    record.update(overrides)
    return record


def _write_fixture(path, records):
    path.write_text(json.dumps(records))
    return path


def test_phase2_fixture_normalizes_and_preserves_provenance(tmp_path) -> None:
    vehicles = load_inventory_fixture(_write_fixture(tmp_path / "valid.json", [_record()]))

    assert len(vehicles) == 1
    assert vehicles[0].year == 2005
    assert vehicles[0].provenance.source_url == "local://phase2/fixture-car"


def test_phase2_rejects_missing_provenance(tmp_path) -> None:
    record = _record()
    del record["provenance"]

    with pytest.raises(InventoryValidationError, match="provenance"):
        load_inventory_fixture(_write_fixture(tmp_path / "missing-provenance.json", [record]))


def test_phase2_rejects_incomplete_provenance(tmp_path) -> None:
    record = _record()
    del record["provenance"]["source_url"]

    with pytest.raises(InventoryValidationError, match="source_url"):
        load_inventory_fixture(_write_fixture(tmp_path / "incomplete-provenance.json", [record]))


def test_phase2_loading_mock_fixture_is_deterministic(tmp_path) -> None:
    fixture_path = _write_fixture(tmp_path / "valid.json", [_record()])

    first = load_inventory_fixture(fixture_path)
    second = load_inventory_fixture(fixture_path)

    assert [vehicle.id for vehicle in first] == ["fixture-car"]
    assert [vehicle.id for vehicle in second] == ["fixture-car"]
    assert first == second


def test_phase2_rejects_out_of_range_year_and_invalid_price(tmp_path) -> None:
    record = _record(year=1959, price=0)

    with pytest.raises(InventoryValidationError, match="year.*price|price.*year"):
        load_inventory_fixture(_write_fixture(tmp_path / "invalid.json", [record]))


@pytest.mark.parametrize(
    ("overrides", "error_field"),
    [({"mileage": -1}, "mileage"), ({"id": ""}, "id")],
)
def test_phase2_rejects_invalid_mileage_and_id(tmp_path, overrides, error_field) -> None:
    with pytest.raises(InventoryValidationError, match=error_field):
        load_inventory_fixture(
            _write_fixture(tmp_path / f"invalid-{error_field}.json", [_record(**overrides)])
        )


def test_phase2_rejects_duplicate_ids_in_one_fixture(tmp_path) -> None:
    with pytest.raises(InventoryValidationError, match="duplicate id"):
        load_inventory_fixture(_write_fixture(tmp_path / "duplicate.json", [_record(), _record()]))


def test_phase2_knowledge_retrieval_is_model_specific() -> None:
    repository = KnowledgeRepository()

    facts = repository.retrieve("honda-s2000-2004", topic="ownership")

    assert facts
    assert all(fact.vehicle_id == "honda-s2000-2004" for fact in facts)
    assert all(fact.source for fact in facts)


def test_phase2_checked_in_inventory_has_50_typed_records_and_real_photos() -> None:
    vehicles = InventoryRepository().all()

    assert len(vehicles) == 50
    assert len({vehicle.id for vehicle in vehicles}) == 50
    assert [vehicle.id for vehicle in vehicles[:6]] == [
        "mazda-rx7-1992",
        "honda-s2000-2004",
        "bmw-z4-m-2008",
        "porsche-911-1999",
        "nissan-gt-r-2012",
        "porsche-718-2018",
    ]
    generated = vehicles[6:]
    assert all(vehicle.image_url for vehicle in vehicles)
    assert all(vehicle.image_source_url for vehicle in vehicles)
    assert all(vehicle.image_license for vehicle in vehicles)
    assert all(vehicle.id.startswith("mock-") for vehicle in generated)
    assert all(vehicle.provenance.source_type == "illustrative_fixture" for vehicle in vehicles)
    assert all(vehicle.service_history for vehicle in vehicles)
    assert all(record.source == "synthetic_demo" for vehicle in generated for record in vehicle.service_history)
    assert all(
        "Synthetic auction-style listing for an" not in vehicle.description
        for vehicle in vehicles
    )


def test_generated_model_years_stay_inside_their_production_ranges() -> None:
    for index, spec in enumerate(CATALOG):
        record = generate_record(index)
        assert any(
            start <= record["year"] <= end
            for start, end in spec["production_year_ranges"]
        ), f"{record['make']} {record['model']} generated invalid year {record['year']}"


def test_checked_in_inventory_has_no_known_impossible_model_years() -> None:
    vehicles = InventoryRepository().all()
    by_model = {
        (spec["make"], spec["model"]): spec["production_year_ranges"]
        for spec in CATALOG
    }

    for vehicle in vehicles[6:]:
        ranges = by_model[(vehicle.make, vehicle.model)]
        assert any(start <= vehicle.year <= end for start, end in ranges)
