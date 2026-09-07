"""Validation for mock inventory records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import Provenance, ServiceRecord, Vehicle

MIN_YEAR = 1990
MAX_YEAR = 2020
REQUIRED_FIELDS = {
    "id",
    "make",
    "model",
    "year",
    "price",
    "mileage",
    "body_style",
    "transmission",
    "drivetrain",
    "horsepower",
    "description",
    "provenance",
}


class InventoryValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def normalize_inventory_record(record: dict[str, Any]) -> Vehicle:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - record.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")

    _require_text(record, "id", errors)
    _require_text(record, "make", errors)
    _require_text(record, "model", errors)
    _require_text(record, "body_style", errors)
    _require_text(record, "transmission", errors)
    _require_text(record, "drivetrain", errors)
    _require_text(record, "description", errors)
    _require_positive_number(record, "price", errors)
    _require_nonnegative_number(record, "mileage", errors)
    _require_positive_number(record, "horsepower", errors)

    year = record.get("year")
    if not isinstance(year, int) or isinstance(year, bool) or not MIN_YEAR <= year <= MAX_YEAR:
        errors.append(f"year must be an integer from {MIN_YEAR} to {MAX_YEAR}")

    provenance = _parse_provenance(record.get("provenance"), errors)
    service_history = _parse_service_history(
        record.get("service_history"),
        vehicle_id=record.get("id"),
        mileage=record.get("mileage"),
        errors=errors,
    )
    if errors:
        raise InventoryValidationError(errors)

    return Vehicle(
        id=record["id"].strip(),
        make=record["make"].strip(),
        model=record["model"].strip(),
        year=year,
        price=int(record["price"]),
        mileage=int(record["mileage"]),
        body_style=record["body_style"].strip(),
        transmission=record["transmission"].strip(),
        drivetrain=record["drivetrain"].strip(),
        horsepower=int(record["horsepower"]),
        description=record["description"].strip(),
        tags=tuple(str(tag).strip() for tag in record.get("tags", []) if str(tag).strip()),
        service_history=service_history,
        provenance=provenance,
    )


def load_inventory_fixture(path: str | Path) -> list[Vehicle]:
    records = json.loads(Path(path).read_text())
    if not isinstance(records, list):
        raise InventoryValidationError(["inventory fixture must contain a JSON list"])

    vehicles: list[Vehicle] = []
    seen_ids: set[str] = set()
    errors: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"row {index}: record must be a JSON object")
            continue
        try:
            vehicle = normalize_inventory_record(record)
        except InventoryValidationError as exc:
            errors.extend(f"row {index}: {error}" for error in exc.errors)
            continue
        if vehicle.id in seen_ids:
            errors.append(f"row {index}: duplicate id '{vehicle.id}'")
        seen_ids.add(vehicle.id)
        vehicles.append(vehicle)
    if errors:
        raise InventoryValidationError(errors)
    return vehicles


def _parse_service_history(
    value: Any,
    *,
    vehicle_id: Any,
    mileage: Any,
    errors: list[str],
) -> tuple[ServiceRecord, ...]:
    """Validate supplied records and synthesize a clearly labeled fallback."""

    if value is None:
        if isinstance(mileage, (int, float)) and not isinstance(mileage, bool):
            return _synthetic_service_history(str(vehicle_id), int(mileage))
        return ()
    if not isinstance(value, list):
        errors.append("service_history must be a list")
        return ()

    records: list[ServiceRecord] = []
    for index, item in enumerate(value):
        prefix = f"service_history[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        valid_text = True
        for field in ("date", "service_type", "details", "source"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
                valid_text = False
        record_mileage = item.get("mileage")
        if (
            not isinstance(record_mileage, (int, float))
            or isinstance(record_mileage, bool)
            or record_mileage < 0
        ):
            errors.append(f"{prefix}.mileage must be non-negative")
            continue
        if not valid_text:
            continue
        records.append(
            ServiceRecord(
                date=item["date"].strip(),
                mileage=int(record_mileage),
                service_type=item["service_type"].strip(),
                details=item["details"].strip(),
                source=item["source"].strip(),
            )
        )
    return tuple(records)


def _synthetic_service_history(vehicle_id: str, mileage: int) -> tuple[ServiceRecord, ...]:
    """Create deterministic placeholder history for source rows without records."""

    first_mileage = max(1_000, int(mileage * 0.55))
    second_mileage = max(first_mileage, int(mileage * 0.82))
    return (
        ServiceRecord(
            date="2021-05-15",
            mileage=first_mileage,
            service_type="Scheduled maintenance",
            details=f"Synthetic demo record generated for {vehicle_id}: fluids, filters, and belts inspected.",
        ),
        ServiceRecord(
            date="2024-09-21",
            mileage=second_mileage,
            service_type="Annual inspection",
            details=f"Synthetic demo record generated for {vehicle_id}: brakes, tires, and suspension inspected.",
        ),
    )


def _require_text(record: dict[str, Any], field: str, errors: list[str]) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")


def _require_positive_number(record: dict[str, Any], field: str, errors: list[str]) -> None:
    value = record.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        errors.append(f"{field} must be positive")


def _require_nonnegative_number(record: dict[str, Any], field: str, errors: list[str]) -> None:
    value = record.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        errors.append(f"{field} must be non-negative")


def _parse_provenance(value: Any, errors: list[str]) -> Provenance | None:
    if not isinstance(value, dict):
        errors.append("provenance must be an object")
        return None
    for field in ("source_url", "source_type", "retrieved_at"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append(f"provenance.{field} must be a non-empty string")
    source_url = value.get("source_url", "")
    if isinstance(source_url, str) and urlparse(source_url).scheme not in {"http", "https", "local"}:
        errors.append("provenance.source_url must use http, https, or local scheme")
    return Provenance(
        source_url=source_url,
        source_type=value.get("source_type", ""),
        retrieved_at=value.get("retrieved_at", ""),
        source_record_id=value.get("source_record_id"),
        license=value.get("license"),
    )
