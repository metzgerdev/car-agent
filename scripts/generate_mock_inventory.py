#!/usr/bin/env python3
"""Generate the deterministic, synthetic inventory fixture used by the demo.

The fixture is intentionally shaped like an enthusiast-auction inventory: each
record has mileage, a condition-oriented description, a modification summary,
synthetic service records, and local provenance.  No live listing data is
copied into the repository.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "inventory.json"
TARGET_COUNT = 1_000

CURATED_IDS = (
    "mazda-rx7-1992",
    "honda-s2000-2004",
    "bmw-z4-m-2008",
    "porsche-911-1999",
    "nissan-gt-r-2012",
    "porsche-718-2018",
)

# These are model families, not source listings.  They provide enough variety
# for a useful demo while keeping the generated data reproducible.
CATALOG: tuple[dict[str, Any], ...] = (
    {"make": "Acura", "model": "Integra Type R", "body_style": "hatchback", "drivetrain": "FWD", "horsepower": 195, "price": 58_000, "tags": ["analog", "documented"]},
    {"make": "Alfa Romeo", "model": "GTV6", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 160, "price": 54_000, "tags": ["collector", "period-correct"]},
    {"make": "Aston Martin", "model": "V8 Vantage", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 380, "price": 92_000, "tags": ["grand-tourer", "luxury"]},
    {"make": "Audi", "model": "RS 4", "body_style": "wagon", "drivetrain": "AWD", "horsepower": 420, "price": 62_000, "tags": ["practical", "performance"]},
    {"make": "BMW", "model": "2002", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 130, "price": 66_000, "tags": ["collector", "period-correct"]},
    {"make": "BMW", "model": "E36 328is", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 193, "price": 57_000, "tags": ["analog", "manual"]},
    {"make": "BMW", "model": "Z3 M Roadster", "body_style": "convertible", "drivetrain": "RWD", "horsepower": 240, "price": 72_000, "tags": ["roadster", "manual"]},
    {"make": "Chevrolet", "model": "Corvette Z06", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 385, "price": 61_000, "tags": ["track", "documented"]},
    {"make": "Datsun", "model": "240Z", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 150, "price": 76_000, "tags": ["collector", "restored"]},
    {"make": "Dodge", "model": "Viper GTS", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 450, "price": 118_000, "tags": ["collector", "analog"]},
    {"make": "Ford", "model": "Mustang Boss 302", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 444, "price": 69_000, "tags": ["track", "documented"]},
    {"make": "Ford", "model": "GT", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 550, "price": 220_000, "tags": ["collector", "rare"]},
    {"make": "Honda", "model": "Integra Type S", "body_style": "hatchback", "drivetrain": "FWD", "horsepower": 320, "price": 52_000, "tags": ["manual", "performance"]},
    {"make": "Honda", "model": "NSX", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 290, "price": 128_000, "tags": ["collector", "analog"]},
    {"make": "Jaguar", "model": "E-Type", "body_style": "convertible", "drivetrain": "RWD", "horsepower": 265, "price": 146_000, "tags": ["collector", "restored"]},
    {"make": "Lexus", "model": "IS F", "body_style": "sedan", "drivetrain": "RWD", "horsepower": 416, "price": 58_000, "tags": ["daily", "performance"]},
    {"make": "Lotus", "model": "Elise", "body_style": "convertible", "drivetrain": "RWD", "horsepower": 190, "price": 74_000, "tags": ["lightweight", "track"]},
    {"make": "Maserati", "model": "GranTurismo", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 433, "price": 64_000, "tags": ["grand-tourer", "luxury"]},
    {"make": "Mazda", "model": "RX-8 R3", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 232, "price": 53_000, "tags": ["analog", "documented"]},
    {"make": "McLaren", "model": "570S", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 562, "price": 148_000, "tags": ["performance", "rare"]},
    {"make": "Mercedes-Benz", "model": "190E 2.3-16", "body_style": "sedan", "drivetrain": "RWD", "horsepower": 185, "price": 71_000, "tags": ["collector", "period-correct"]},
    {"make": "Mitsubishi", "model": "Lancer Evolution VIII", "body_style": "sedan", "drivetrain": "AWD", "horsepower": 271, "price": 64_000, "tags": ["rally", "documented"]},
    {"make": "Nissan", "model": "300ZX Twin Turbo", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 300, "price": 59_000, "tags": ["analog", "documented"]},
    {"make": "Nissan", "model": "350Z NISMO", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 350, "price": 55_000, "tags": ["track", "manual"]},
    {"make": "Pontiac", "model": "GTO", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 400, "price": 56_000, "tags": ["muscle", "documented"]},
    {"make": "Renault", "model": "Clio V6", "body_style": "hatchback", "drivetrain": "RWD", "horsepower": 255, "price": 93_000, "tags": ["rare", "collector"]},
    {"make": "Subaru", "model": "Impreza WRX STI", "body_style": "sedan", "drivetrain": "AWD", "horsepower": 305, "price": 62_000, "tags": ["rally", "manual"]},
    {"make": "Toyota", "model": "MR2 Turbo", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 200, "price": 58_000, "tags": ["analog", "lightweight"]},
    {"make": "Toyota", "model": "Supra Turbo", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 320, "price": 106_000, "tags": ["collector", "documented"]},
    {"make": "Triumph", "model": "TR6", "body_style": "convertible", "drivetrain": "RWD", "horsepower": 104, "price": 57_000, "tags": ["collector", "restored"]},
    {"make": "Volkswagen", "model": "Golf R32", "body_style": "hatchback", "drivetrain": "AWD", "horsepower": 240, "price": 55_000, "tags": ["practical", "documented"]},
    {"make": "Volvo", "model": "P1800", "body_style": "coupe", "drivetrain": "RWD", "horsepower": 115, "price": 73_000, "tags": ["collector", "period-correct"]},
)


def generate_record(index: int) -> dict[str, Any]:
    """Return one reproducible synthetic auction-style inventory record."""

    spec = CATALOG[index % len(CATALOG)]
    year = 1990 + ((index * 11 + 3) % 31)
    mileage = 18_000 + ((index * 7_919 + 4_321) % 102_000)
    # Keep generated auction-style records above the curated demo cars' budget
    # band so the existing <$50k qualification examples remain stable.
    price = max(52_000, spec["price"] + ((index * 3_173) % 38_000) - 12_000)
    horsepower = max(80, spec["horsepower"] + ((index * 13) % 31) - 15)
    transmission = "6-speed manual" if index % 5 != 0 else "5-speed manual"
    trim_note = ("largely stock" if index % 4 == 0 else "period-correct upgrades")
    condition_note = ("cosmetic wear is called out for inspection" if index % 3 == 0 else "presented with a clean, driver-focused condition profile")

    return {
        "id": f"mock-{index + 1:04d}",
        "make": spec["make"],
        "model": spec["model"],
        "year": year,
        "price": price,
        "mileage": mileage,
        "body_style": spec["body_style"],
        "transmission": transmission,
        "drivetrain": spec["drivetrain"],
        "horsepower": horsepower,
        "description": (
            f"Synthetic auction-style listing for an enthusiast-owned {year} "
            f"{spec['make']} {spec['model']} with {mileage:,} miles. "
            f"Modification summary: {trim_note}. Condition note: {condition_note}. "
            "Seller documentation and an independent inspection are recommended."
        ),
        "service_history": _service_history(index, mileage, year),
        "provenance": {
            "source_url": f"local://generated/mock-inventory/mock-{index + 1:04d}",
            "source_type": "illustrative_fixture",
            "retrieved_at": "2026-09-07T00:00:00Z",
            "source_record_id": f"mock-{index + 1:04d}",
            "license": "internal-demo",
        },
        "tags": ["synthetic", "auction-style", *spec["tags"]],
    }


def _service_history(index: int, mileage: int, vehicle_year: int) -> list[dict[str, Any]]:
    first_year = max(vehicle_year + 1, 2016 + (index % 4))
    first_year = min(first_year, 2022)
    second_year = min(first_year + 3, 2025)
    third_year = min(second_year + 2, 2026)
    return [
        {
            "date": f"{first_year:04d}-04-{(index % 20) + 1:02d}",
            "mileage": max(1_000, int(mileage * 0.58)),
            "service_type": "Inspection and fluid service",
            "details": "Synthetic demo record: fluids, filters, and belts inspected.",
            "source": "synthetic_demo",
        },
        {
            "date": f"{second_year:04d}-08-{(index % 20) + 1:02d}",
            "mileage": max(1_000, int(mileage * 0.79)),
            "service_type": "Brake and suspension inspection",
            "details": "Synthetic demo record: brakes, tires, and suspension inspected.",
            "source": "synthetic_demo",
        },
        {
            "date": f"{third_year:04d}-11-{(index % 20) + 1:02d}",
            "mileage": mileage,
            "service_type": "Pre-sale service",
            "details": "Synthetic demo record: annual service and pre-sale inspection completed.",
            "source": "synthetic_demo",
        },
    ]


def generate_inventory(output: Path = DEFAULT_OUTPUT, target_count: int = TARGET_COUNT) -> list[dict[str, Any]]:
    """Preserve curated seed records and regenerate the synthetic remainder."""

    if target_count < len(CURATED_IDS):
        raise ValueError(f"target_count must be at least {len(CURATED_IDS)}")

    current_records = json.loads(output.read_text()) if output.exists() else []
    by_id = {record.get("id"): record for record in current_records if isinstance(record, dict)}
    curated = []
    for vehicle_id in CURATED_IDS:
        if vehicle_id not in by_id:
            raise ValueError(f"curated vehicle {vehicle_id!r} is missing from {output}")
        curated.append(by_id[vehicle_id])

    generated = [generate_record(index) for index in range(target_count - len(curated))]
    records = curated + generated
    output.write_text(json.dumps(records, indent=2) + "\n")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=TARGET_COUNT)
    args = parser.parse_args()
    records = generate_inventory(args.output, args.count)
    print(f"Wrote {len(records):,} synthetic inventory records to {args.output}")


if __name__ == "__main__":
    main()
