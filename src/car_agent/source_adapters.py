"""Adapters that turn validated source payloads into domain records."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from collections.abc import Iterator, Mapping
from typing import Any

from .models import VehicleFact
from .source_models import (
    CraigslistInventoryCandidate,
    CraigslistVehicleRow,
    EPAFuelEconomyVehicle,
    NHTSARecallResponse,
    NHTSAVPICResponse,
    SourceProvenanceModel,
)


def iter_craigslist_rows(path: str | Path) -> Iterator[CraigslistVehicleRow]:
    """Stream a Craigslist CSV as validated Pydantic rows.

    The published file is large, so this intentionally yields one row at a
    time instead of loading the complete dataset into memory.
    """

    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            cleaned_row = {
                key: (value.strip() if isinstance(value, str) and value.strip() else None)
                for key, value in raw_row.items()
            }
            yield CraigslistVehicleRow.model_validate(cleaned_row)


def normalize_craigslist_row(
    row: CraigslistVehicleRow | Mapping[str, Any],
    *,
    retrieved_at: datetime | str,
) -> CraigslistInventoryCandidate:
    """Map a raw Craigslist row to a typed, enrichment-ready candidate."""

    source_row = row if isinstance(row, CraigslistVehicleRow) else CraigslistVehicleRow.model_validate(row)
    if not source_row.url:
        raise ValueError("Craigslist row requires a listing URL for provenance")

    candidate = CraigslistInventoryCandidate(
        id=f"craigslist-{source_row.id}",
        make=_clean_text(source_row.manufacturer),
        model=_clean_text(source_row.model),
        year=_whole_number(source_row.year, "year"),
        price=_whole_number(source_row.price, "price"),
        mileage=_whole_number(source_row.odometer, "odometer"),
        body_style=_normalize_category(source_row.type),
        transmission=_normalize_transmission(source_row.transmission),
        drivetrain=_normalize_drivetrain(source_row.drive),
        description=_clean_text(source_row.description),
        tags=_tags(source_row),
        provenance=SourceProvenanceModel(
            source_url=source_row.url,
            source_type="craigslist_snapshot",
            retrieved_at=retrieved_at,
            source_record_id=str(source_row.id),
            license="CC0: Public Domain",
        ),
    )
    return candidate


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
    """Convert NHTSA recall records into explicit safety facts.

    Model/year recall searches are not proof that a particular VIN is affected
    or that a repair is outstanding, so the default fact says to verify by VIN.
    """

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


def _whole_number(value: int | float | None, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or int(value) != value:
        raise ValueError(f"{field} must be a whole number")
    return int(value)


def _normalize_category(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    return cleaned.lower() if cleaned else None


def _normalize_transmission(value: str | None) -> str | None:
    cleaned = _normalize_category(value)
    if cleaned == "automatic":
        return "automatic"
    if cleaned == "manual":
        return "manual"
    return cleaned


def _normalize_drivetrain(value: str | None) -> str | None:
    cleaned = _normalize_category(value)
    return {
        "awd": "AWD",
        "4wd": "4WD",
        "fwd": "FWD",
        "rwd": "RWD",
    }.get(cleaned or "", cleaned)


def _tags(row: CraigslistVehicleRow) -> list[str]:
    tags = []
    for value in (row.condition, row.fuel, row.paint_color, row.state):
        cleaned = _normalize_category(value)
        if cleaned:
            tags.append(cleaned)
    return tags


def _with_unit(value: int | None, unit: str) -> str | None:
    return f"{value} {unit}" if value is not None and value >= 0 else None
