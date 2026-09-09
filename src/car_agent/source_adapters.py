"""Adapters that turn validated source payloads into domain records."""

from __future__ import annotations

from datetime import datetime
from collections.abc import Mapping
from typing import Any

from .models import VehicleFact
from .source_models import (
    EPAFuelEconomyVehicle,
    NHTSARecallResponse,
    NHTSAVPICResponse,
)


def nhtsa_vpic_to_facts(
    payload: Mapping[str, Any],
    *,
    vehicle_id: str,
    source_url: str,
    retrieved_at: datetime | str,
) -> list[VehicleFact]:
    """Convert NHTSA vPIC identity fields into provenance-backed facts."""

    response = NHTSAVPICResponse.model_validate(payload)
    relevant_variables = {
        "Body Class",
        "Drive Type",
        "Make",
        "Manufacturer Name",
        "Model",
        "Model Year",
        "Plant City",
        "Plant Country",
        "Vehicle Type",
    }
    timestamp = _timestamp(retrieved_at)
    return [
        VehicleFact(
            vehicle_id=vehicle_id,
            topic="identity",
            fact=f"{result.variable}: {result.value}",
            source="NHTSA vPIC",
            source_url=source_url,
            retrieved_at=timestamp,
        )
        for result in response.results
        if result.variable in relevant_variables and _clean_text(result.value)
    ]


def nhtsa_recalls_to_facts(
    payload: Mapping[str, Any],
    *,
    vehicle_id: str,
    source_url: str,
    retrieved_at: datetime | str,
    vin_specific: bool = False,
) -> list[VehicleFact]:
    """Convert NHTSA recall records into safety facts with VIN verification."""

    response = NHTSARecallResponse.model_validate(payload)
    timestamp = _timestamp(retrieved_at)
    facts: list[VehicleFact] = []
    for recall in response.results:
        details = [
            recall.component,
            recall.summary,
            f"Consequence: {recall.consequence}" if recall.consequence else None,
            f"Remedy: {recall.remedy}" if recall.remedy else None,
        ]
        text = ". ".join(item for item in details if item)
        if not vin_specific:
            text = f"{text} Verify applicability and repair status by VIN." if text else "Verify applicability and repair status by VIN."
        if recall.campaign_number:
            text = f"{recall.campaign_number}: {text}"
        facts.append(
            VehicleFact(
                vehicle_id=vehicle_id,
                topic="safety_recall",
                fact=text,
                source="NHTSA recalls",
                source_url=source_url,
                retrieved_at=timestamp,
            )
        )
    return facts


def epa_vehicle_to_facts(
    payload: Mapping[str, Any],
    *,
    vehicle_id: str,
    source_url: str,
    retrieved_at: datetime | str,
) -> list[VehicleFact]:
    """Convert a FuelEconomy.gov vehicle record into typed sales facts."""

    vehicle = EPAFuelEconomyVehicle.model_validate(_unwrap_epa_vehicle(payload))
    timestamp = _timestamp(retrieved_at)
    values = (
        ("Fuel type", vehicle.fuel_type, "specification"),
        ("City fuel economy", _with_unit(vehicle.city_mpg, "MPG"), "efficiency"),
        ("Highway fuel economy", _with_unit(vehicle.highway_mpg, "MPG"), "efficiency"),
        ("Combined fuel economy", _with_unit(vehicle.combined_mpg, "MPG"), "efficiency"),
        ("Estimated annual fuel cost", _with_unit(vehicle.annual_fuel_cost, "USD"), "ownership"),
        ("Tailpipe CO2", _with_unit(vehicle.co2_grams_per_mile, "g/mile"), "emissions"),
        ("Drive type", vehicle.drive, "specification"),
        ("Transmission", vehicle.transmission, "specification"),
        ("Vehicle class", vehicle.vehicle_class, "specification"),
        ("Estimated electric range", _with_unit(vehicle.range_miles, "miles"), "efficiency"),
    )
    return [
        VehicleFact(
            vehicle_id=vehicle_id,
            topic=topic,
            fact=f"{label}: {value}",
            source="EPA FuelEconomy.gov",
            source_url=source_url,
            retrieved_at=timestamp,
        )
        for label, value, topic in values
        if value is not None
    ]


def _unwrap_epa_vehicle(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(payload.get("vehicle"), Mapping):
        return payload["vehicle"]
    if isinstance(payload.get("vehicles"), list) and len(payload["vehicles"]) == 1:
        return payload["vehicles"][0]
    return payload


def _timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _with_unit(value: int | None, unit: str) -> str | None:
    return f"{value} {unit}" if value is not None and value >= 0 else None
