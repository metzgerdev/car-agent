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
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "inventory.json"
TARGET_COUNT = 50

CURATED_IDS = (
    "mazda-rx7-1992",
    "honda-s2000-2004",
    "bmw-z4-m-2008",
    "porsche-911-1999",
    "nissan-gt-r-2012",
    "porsche-718-2018",
)

IMAGE_METADATA: dict[str, dict[str, str]] = {
    "mazda-rx7-1992": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/MAZDA_RX-7_FC.jpg?width=1200",
        "image_source_url": "https://commons.wikimedia.org/wiki/File:MAZDA_RX-7_FC.jpg",
        "image_attribution": "宮本すぐる / Wikimedia Commons",
        "image_license": "CC BY-SA 3.0",
    },
    "honda-s2000-2004": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Honda_S2000_%2827311372048%29.jpg?width=1200",
        "image_source_url": "https://commons.wikimedia.org/wiki/File:Honda_S2000_(27311372048).jpg",
        "image_attribution": "Dennis Elzinga / Wikimedia Commons",
        "image_license": "CC BY 2.0",
    },
    "bmw-z4-m-2008": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/BMW_Z4_M_Coupe.jpg?width=1200",
        "image_source_url": "https://commons.wikimedia.org/wiki/File:BMW_Z4_M_Coupe.jpg",
        "image_attribution": "Ian Muttoo / Wikimedia Commons",
        "image_license": "CC BY-SA 2.0",
    },
    "porsche-911-1999": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Porsche_911_996.jpg?width=1200",
        "image_source_url": "https://commons.wikimedia.org/wiki/File:Porsche_911_996.jpg",
        "image_attribution": "IFCAR / Wikimedia Commons",
        "image_license": "Public domain",
    },
    "nissan-gt-r-2012": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Nissan_GT-R_R35_%2815923829179%29.jpg?width=1200",
        "image_source_url": "https://commons.wikimedia.org/wiki/File:Nissan_GT-R_R35_(15923829179).jpg",
        "image_attribution": "Jeremy / Wikimedia Commons",
        "image_license": "CC BY 2.0",
    },
    "porsche-718-2018": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/2018_Porsche_718_Cayman.jpg?width=1200",
        "image_source_url": "https://commons.wikimedia.org/wiki/File:2018_Porsche_718_Cayman.jpg",
        "image_attribution": "多多123 / Wikimedia Commons",
        "image_license": "CC BY 4.0",
    },
}

# These are model-reference photographs, not claimed photographs of the
# individual mock listings. Each generated family has a real source image so
# the gallery never needs to present a synthetic visual for this fixture.
MODEL_IMAGE_SOURCES: dict[tuple[str, str], tuple[str, str, str]] = {
    ("Acura", "Integra Type R"): ("Acura Integra Type R white.jpg", "Jacob Frey 4A", "CC BY 2.0"),
    ("Alfa Romeo", "GTV6"): ("Alfa Romeo GTV6 2.5 (1981) 01.jpg", "Huhu Uet", "CC BY-SA 3.0"),
    ("Aston Martin", "V8 Vantage"): ("Aston Martin V8 Vantage.jpg", "Zölle", "CC BY-SA 2.0 BE"),
    ("Audi", "RS 4"): ("Audi RS4 Avant grey Free Car Picture - Give Credit Via Link (cropped).jpg", "Wikimedia Commons", "See source page"),
    ("BMW", "2002"): ("BMW 2002 Turbo (2008-06-28) ret.jpg", "Lothar Spurzem", "CC BY-SA 2.0 de"),
    ("BMW", "E36 328is"): ("1996 BMW 328is (E36) Coupé (28-12-2017) 05.jpg", "Jirapat Chroenkeskij", "CC0"),
    ("BMW", "Z3 M Roadster"): ("BMW Z3 M Roadster (43756108240).jpg", "FotoSleuth", "CC BY 2.0"),
    ("Chevrolet", "Corvette Z06"): ("Corvette Z06, BAS 24, Brussels (P1170397-RR).jpg", "Matti Blume", "CC BY-SA 4.0"),
    ("Datsun", "240Z"): ("Yellow Datsun 240Z dllu.jpg", "Dllu", "CC BY-SA 4.0"),
    ("Dodge", "Viper GTS"): ("Dodge Viper GTS (Bahrain).jpg", "Mohammed Hamad", "CC BY-SA 4.0"),
    ("Ford", "Mustang Boss 302"): ("1970 Ford Mustang Boss 302 (15863840731).jpg", "Wikimedia Commons", "See source page"),
    ("Ford", "GT"): ("Ford GT.jpg", "Stefan-Xp", "CC BY-SA 3.0"),
    ("Honda", "Integra Type S"): ("Acura Integra Type S (DE5) (front three-quarter view) at Osaka Auto Messe 2026.jpg", "Aos.1905", "See source page"),
    ("Honda", "NSX"): ("Honda NSX b.jpg", "crash71100", "CC0"),
    ("Jaguar", "E-Type"): ("Jaguar E-Type Series 1 3.8 Litre 1961.jpg", "Wikimedia Commons", "See source page"),
    ("Lexus", "IS F"): ("Lexus IS F 1002.JPG", "春夏秋冬奏慈", "Public domain"),
    ("Lotus", "Elise"): ("Lotus-Elise-1.jpg", "Matthias v.d. Elbe", "CC BY-SA 3.0"),
    ("Maserati", "GranTurismo"): ("Maserati GranTurismo.jpg", "IFCAR", "Public domain"),
    ("Mazda", "RX-8 R3"): ("Mazda RX-8.JPG", "Thomas doerfer", "CC BY-SA 3.0"),
    ("McLaren", "570S"): ("McLaren 570S 1.jpg", "MPW57", "CC BY 3.0"),
    ("Mercedes-Benz", "190E 2.3-16"): ("Mercedes-Benz 190 E (16400031903).jpg", "Dennis Elzinga", "CC BY 2.0"),
    ("Mitsubishi", "Lancer Evolution VIII"): ("Mitsubishi Lancer Evolution VIII.jpg", "IFCAR", "Public domain"),
    ("Nissan", "300ZX Twin Turbo"): ("Nissan 300ZX 2960cc registered August 1993.jpg", "Charles01", "See source page"),
    ("Nissan", "350Z NISMO"): ("Nissan 350Z (49760598682).jpg", "crash71100", "CC0"),
    ("Pontiac", "GTO"): ("2006-Pontiac-GTO.jpg", "IFCAR", "Public domain"),
    ("Renault", "Clio V6"): ("RenaultClioV6.jpg", "Brian Snelson", "CC BY 2.0"),
    ("Subaru", "Impreza WRX STI"): ("Subaru Impreza WRX STi (8159289146).jpg", "Davi Sanchez", "CC BY 2.0"),
    ("Toyota", "MR2 Turbo"): ("Toyota mr2 sw20 left.jpg", "Wikimedia Commons", "See source page"),
    ("Toyota", "Supra Turbo"): ("1992 Toyota Supra.jpg", "Calreyn88", "CC BY-SA 4.0"),
    ("Triumph", "TR6"): ("'76 Triumph TR6 (Hudson).JPG", "Bull-Doser", "See source page"),
    ("Volkswagen", "Golf R32"): ("Volkswagen Golf R32 - Caramulo (50584382056).jpg", "Freggs", "CC BY-SA 2.0"),
    ("Volvo", "P1800"): ("Volvo P1800.jpg", "Lars-Göran Lindgren", "CC BY-SA 3.0"),
}


def _commons_image_metadata(filename: str, attribution: str, license_name: str) -> dict[str, str]:
    encoded_filename = quote(filename, safe="")
    return {
        "image_url": f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded_filename}?width=1200",
        "image_source_url": f"https://commons.wikimedia.org/wiki/File:{encoded_filename}",
        "image_attribution": f"{attribution} / Wikimedia Commons",
        "image_license": license_name,
    }

# These are model families, not source listings. They provide enough variety
# for a useful demo while keeping the generated data reproducible. The year
# ranges are model-year ranges for the named vehicle, not a generic inventory
# date range. Multiple ranges represent separate generations with the same
# enthusiast-facing model name.
CATALOG: tuple[dict[str, Any], ...] = (
    {"make": "Acura", "model": "Integra Type R", "production_year_ranges": ((1995, 2001),), "body_style": "hatchback", "drivetrain": "FWD", "horsepower": 195, "price": 58_000, "tags": ["analog", "documented"]},
    {"make": "Alfa Romeo", "model": "GTV6", "production_year_ranges": ((1981, 1986),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 160, "price": 54_000, "tags": ["collector", "period-correct"]},
    {"make": "Aston Martin", "model": "V8 Vantage", "production_year_ranges": ((2005, 2017),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 380, "price": 92_000, "tags": ["grand-tourer", "luxury"]},
    {"make": "Audi", "model": "RS 4", "production_year_ranges": ((2006, 2008), (2013, 2015), (2018, 2020)), "body_style": "wagon", "drivetrain": "AWD", "horsepower": 420, "price": 62_000, "tags": ["practical", "performance"]},
    {"make": "BMW", "model": "2002", "production_year_ranges": ((1968, 1976),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 130, "price": 66_000, "tags": ["collector", "period-correct"]},
    {"make": "BMW", "model": "E36 328is", "production_year_ranges": ((1996, 1999),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 193, "price": 57_000, "tags": ["analog", "manual"]},
    {"make": "BMW", "model": "Z3 M Roadster", "production_year_ranges": ((1998, 2002),), "body_style": "convertible", "drivetrain": "RWD", "horsepower": 240, "price": 72_000, "tags": ["roadster", "manual"]},
    {"make": "Chevrolet", "model": "Corvette Z06", "production_year_ranges": ((2001, 2004), (2006, 2013), (2015, 2019)), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 385, "price": 61_000, "tags": ["track", "documented"]},
    {"make": "Datsun", "model": "240Z", "production_year_ranges": ((1970, 1973),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 150, "price": 76_000, "tags": ["collector", "restored"]},
    {"make": "Dodge", "model": "Viper GTS", "production_year_ranges": ((1996, 2002), (2013, 2017)), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 450, "price": 118_000, "tags": ["collector", "analog"]},
    {"make": "Ford", "model": "Mustang Boss 302", "production_year_ranges": ((1969, 1970), (2012, 2013)), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 444, "price": 69_000, "tags": ["track", "documented"]},
    {"make": "Ford", "model": "GT", "production_year_ranges": ((2005, 2006), (2017, 2019)), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 550, "price": 220_000, "tags": ["collector", "rare"]},
    {"make": "Honda", "model": "Integra Type S", "production_year_ranges": ((2023, 2025),), "body_style": "hatchback", "drivetrain": "FWD", "horsepower": 320, "price": 52_000, "tags": ["manual", "performance"]},
    {"make": "Honda", "model": "NSX", "production_year_ranges": ((1991, 2005),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 290, "price": 128_000, "tags": ["collector", "analog"]},
    {"make": "Jaguar", "model": "E-Type", "production_year_ranges": ((1961, 1975),), "body_style": "convertible", "drivetrain": "RWD", "horsepower": 265, "price": 146_000, "tags": ["collector", "restored"]},
    {"make": "Lexus", "model": "IS F", "production_year_ranges": ((2008, 2014),), "body_style": "sedan", "drivetrain": "RWD", "horsepower": 416, "price": 58_000, "tags": ["daily", "performance"]},
    {"make": "Lotus", "model": "Elise", "production_year_ranges": ((1996, 2021),), "body_style": "convertible", "drivetrain": "RWD", "horsepower": 190, "price": 74_000, "tags": ["lightweight", "track"]},
    {"make": "Maserati", "model": "GranTurismo", "production_year_ranges": ((2007, 2019),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 433, "price": 64_000, "tags": ["grand-tourer", "luxury"]},
    {"make": "Mazda", "model": "RX-8 R3", "production_year_ranges": ((2009, 2011),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 232, "price": 53_000, "tags": ["analog", "documented"]},
    {"make": "McLaren", "model": "570S", "production_year_ranges": ((2015, 2021),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 562, "price": 148_000, "tags": ["performance", "rare"]},
    {"make": "Mercedes-Benz", "model": "190E 2.3-16", "production_year_ranges": ((1984, 1988),), "body_style": "sedan", "drivetrain": "RWD", "horsepower": 185, "price": 71_000, "tags": ["collector", "period-correct"]},
    {"make": "Mitsubishi", "model": "Lancer Evolution VIII", "production_year_ranges": ((2003, 2005),), "body_style": "sedan", "drivetrain": "AWD", "horsepower": 271, "price": 64_000, "tags": ["rally", "documented"]},
    {"make": "Nissan", "model": "300ZX Twin Turbo", "production_year_ranges": ((1990, 1996),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 300, "price": 59_000, "tags": ["analog", "documented"]},
    {"make": "Nissan", "model": "350Z NISMO", "production_year_ranges": ((2007, 2009),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 350, "price": 55_000, "tags": ["track", "manual"]},
    {"make": "Pontiac", "model": "GTO", "production_year_ranges": ((2004, 2006),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 400, "price": 56_000, "tags": ["muscle", "documented"]},
    {"make": "Renault", "model": "Clio V6", "production_year_ranges": ((2001, 2005),), "body_style": "hatchback", "drivetrain": "RWD", "horsepower": 255, "price": 93_000, "tags": ["rare", "collector"]},
    {"make": "Subaru", "model": "Impreza WRX STI", "production_year_ranges": ((2004, 2020),), "body_style": "sedan", "drivetrain": "AWD", "horsepower": 305, "price": 62_000, "tags": ["rally", "manual"]},
    {"make": "Toyota", "model": "MR2 Turbo", "production_year_ranges": ((1991, 1995),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 200, "price": 58_000, "tags": ["analog", "lightweight"]},
    {"make": "Toyota", "model": "Supra Turbo", "production_year_ranges": ((1993, 1998),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 320, "price": 106_000, "tags": ["collector", "documented"]},
    {"make": "Triumph", "model": "TR6", "production_year_ranges": ((1969, 1976),), "body_style": "convertible", "drivetrain": "RWD", "horsepower": 104, "price": 57_000, "tags": ["collector", "restored"]},
    {"make": "Volkswagen", "model": "Golf R32", "production_year_ranges": ((2004, 2004), (2008, 2009)), "body_style": "hatchback", "drivetrain": "AWD", "horsepower": 240, "price": 55_000, "tags": ["practical", "documented"]},
    {"make": "Volvo", "model": "P1800", "production_year_ranges": ((1961, 1973),), "body_style": "coupe", "drivetrain": "RWD", "horsepower": 115, "price": 73_000, "tags": ["collector", "period-correct"]},
)


def generate_record(index: int) -> dict[str, Any]:
    """Return one reproducible synthetic auction-style inventory record."""

    spec = CATALOG[index % len(CATALOG)]
    year = _model_year(index, spec["production_year_ranges"])
    mileage = 18_000 + ((index * 7_919 + 4_321) % 102_000)
    # Keep generated auction-style records above the curated demo cars' budget
    # band so the existing <$50k qualification examples remain stable.
    price = max(52_000, spec["price"] + ((index * 3_173) % 38_000) - 12_000)
    horsepower = max(80, spec["horsepower"] + ((index * 13) % 31) - 15)
    transmission = "6-speed manual" if index % 5 != 0 else "5-speed manual"
    trim_note = ("largely stock" if index % 4 == 0 else "period-correct upgrades")
    condition_note = ("cosmetic wear is called out for inspection" if index % 3 == 0 else "presented with a clean, driver-focused condition profile")

    record = {
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
            f"Enthusiast-owned {year} "
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
    image_source = MODEL_IMAGE_SOURCES.get((spec["make"], spec["model"]))
    if image_source is None:
        raise ValueError(f"missing model-reference photo for {spec['make']} {spec['model']}")
    record.update(_commons_image_metadata(*image_source))
    return record


def _model_year(index: int, ranges: tuple[tuple[int, int], ...]) -> int:
    """Choose a reproducible year from one or more valid model-year ranges."""

    total_years = sum(end - start + 1 for start, end in ranges)
    offset = (index * 11 + 3) % total_years
    for start, end in ranges:
        range_size = end - start + 1
        if offset < range_size:
            return start + offset
        offset -= range_size
    raise ValueError("production year ranges must contain at least one year")


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
        curated.append({**by_id[vehicle_id], **IMAGE_METADATA[vehicle_id]})

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
