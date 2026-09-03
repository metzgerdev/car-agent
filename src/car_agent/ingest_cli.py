"""Command-line ingestion for normalized inventory fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from .data_pipeline import InventoryValidationError, SQLiteInventoryStore, load_inventory_fixture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize and ingest a car inventory fixture")
    parser.add_argument("--input", required=True, help="JSON inventory fixture to validate")
    parser.add_argument("--output", required=True, help="SQLite database path")
    args = parser.parse_args(argv)

    try:
        vehicles = load_inventory_fixture(args.input)
    except (OSError, ValueError, InventoryValidationError) as exc:
        parser.error(str(exc))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteInventoryStore(output_path)
    try:
        count = store.ingest(vehicles)
        print(f"Ingested {count} normalized vehicle(s); database now contains {store.count()} vehicle(s).")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
