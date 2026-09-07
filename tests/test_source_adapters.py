import json
from pathlib import Path

from car_agent.source_adapters import (
    epa_vehicle_to_facts,
    nhtsa_recalls_to_facts,
    nhtsa_vpic_to_facts,
)
from car_agent.source_models import (
    EPAFuelEconomyVehicle,
    NHTSARecallResponse,
    NHTSAVPICResponse,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_nhtsa_vpic_fixture_is_typed_and_grounded() -> None:
    payload = _load("nhtsa_vpic.json")
    response = NHTSAVPICResponse.model_validate(payload)
    facts = nhtsa_vpic_to_facts(
        payload,
        vehicle_id="honda-s2000-2004",
        source_url="https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/JHMAP11404T000001",
        retrieved_at="2026-09-03T00:00:00Z",
    )

    assert response.results[0].variable == "Make"
    assert len(facts) == 5
    assert all(fact.source == "NHTSA vPIC" for fact in facts)
    assert all(fact.source_url.startswith("https://vpic.nhtsa.dot.gov") for fact in facts)
    assert any("Plant Country: Japan" in fact.fact for fact in facts)


def test_nhtsa_recall_fixture_is_typed_and_explicit_about_vin_scope() -> None:
    payload = _load("nhtsa_recalls.json")
    response = NHTSARecallResponse.model_validate(payload)
    facts = nhtsa_recalls_to_facts(
        payload,
        vehicle_id="honda-s2000-2004",
        source_url="https://api.nhtsa.gov/recalls/recallsByVehicle?make=honda&model=s2000&modelYear=2004",
        retrieved_at="2026-09-03T00:00:00Z",
    )

    assert response.count == 1
    assert len(facts) == 1
    assert facts[0].topic == "safety_recall"
    assert "04V176000" in facts[0].fact
    assert "Verify applicability and repair status by VIN" in facts[0].fact


def test_epa_fixture_is_typed_and_maps_efficiency_facts() -> None:
    payload = _load("epa_vehicle.json")
    vehicle = EPAFuelEconomyVehicle.model_validate(payload["vehicle"])
    facts = epa_vehicle_to_facts(
        payload,
        vehicle_id="honda-s2000-2004",
        source_url="https://www.fueleconomy.gov/ws/rest/vehicle/31873",
        retrieved_at="2026-09-03T00:00:00Z",
    )

    assert vehicle.combined_mpg == 22
    assert len(facts) == 9
    assert any(fact.topic == "efficiency" and "22 MPG" in fact.fact for fact in facts)
    assert any(fact.topic == "ownership" and "2100 USD" in fact.fact for fact in facts)
    assert all(fact.source == "EPA FuelEconomy.gov" for fact in facts)
    assert all(fact.retrieved_at == "2026-09-03T00:00:00Z" for fact in facts)
