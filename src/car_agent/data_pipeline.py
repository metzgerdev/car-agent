"""Validation and idempotent storage for inventory source records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import Provenance, Vehicle

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


class SQLiteInventoryStore:
    """Normalized inventory store with idempotent upsert semantics."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id TEXT PRIMARY KEY,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER NOT NULL,
                price INTEGER NOT NULL,
                mileage INTEGER NOT NULL,
                body_style TEXT NOT NULL,
                transmission TEXT NOT NULL,
                drivetrain TEXT NOT NULL,
                horsepower INTEGER NOT NULL,
                description TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source_record_id TEXT,
                license TEXT
            )
            """
        )
        self.connection.commit()

    def ingest(self, vehicles: Iterable[Vehicle]) -> int:
        count = 0
        try:
            for vehicle in vehicles:
                if not vehicle.provenance:
                    raise InventoryValidationError([f"vehicle '{vehicle.id}' has no provenance"])
                provenance = vehicle.provenance
                self.connection.execute(
                    """
                    INSERT INTO inventory (
                        id, make, model, year, price, mileage, body_style, transmission,
                        drivetrain, horsepower, description, tags_json, source_url,
                        source_type, retrieved_at, source_record_id, license
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        make=excluded.make, model=excluded.model, year=excluded.year,
                        price=excluded.price, mileage=excluded.mileage,
                        body_style=excluded.body_style, transmission=excluded.transmission,
                        drivetrain=excluded.drivetrain, horsepower=excluded.horsepower,
                        description=excluded.description, tags_json=excluded.tags_json,
                        source_url=excluded.source_url, source_type=excluded.source_type,
                        retrieved_at=excluded.retrieved_at,
                        source_record_id=excluded.source_record_id, license=excluded.license
                    """,
                    (
                        vehicle.id,
                        vehicle.make,
                        vehicle.model,
                        vehicle.year,
                        vehicle.price,
                        vehicle.mileage,
                        vehicle.body_style,
                        vehicle.transmission,
                        vehicle.drivetrain,
                        vehicle.horsepower,
                        vehicle.description,
                        json.dumps(vehicle.tags),
                        provenance.source_url,
                        provenance.source_type,
                        provenance.retrieved_at,
                        provenance.source_record_id,
                        provenance.license,
                    ),
                )
                count += 1
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return count

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0])

    def all(self) -> list[Vehicle]:
        rows = self.connection.execute("SELECT * FROM inventory ORDER BY id").fetchall()
        return [_vehicle_from_row(row) for row in rows]

    def get(self, vehicle_id: str) -> Vehicle | None:
        row = self.connection.execute("SELECT * FROM inventory WHERE id = ?", (vehicle_id,)).fetchone()
        if row is None:
            return None
        return _vehicle_from_row(row)

    def close(self) -> None:
        self.connection.close()


def _vehicle_from_row(row: sqlite3.Row) -> Vehicle:
    return Vehicle(
        id=row["id"],
        make=row["make"],
        model=row["model"],
        year=row["year"],
        price=row["price"],
        mileage=row["mileage"],
        body_style=row["body_style"],
        transmission=row["transmission"],
        drivetrain=row["drivetrain"],
        horsepower=row["horsepower"],
        description=row["description"],
        tags=tuple(json.loads(row["tags_json"])),
        provenance=Provenance(
            source_url=row["source_url"],
            source_type=row["source_type"],
            retrieved_at=row["retrieved_at"],
            source_record_id=row["source_record_id"],
            license=row["license"],
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
