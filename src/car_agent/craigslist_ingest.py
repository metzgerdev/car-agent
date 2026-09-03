"""Stream a Craigslist CSV into the canonical SQLite inventory store."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data_pipeline import SQLiteInventoryStore, normalize_inventory_record
from .models import Vehicle
from .source_adapters import iter_craigslist_rows, normalize_craigslist_row


def iter_craigslist_vehicles(
    csv_path: str | Path,
    horsepower_by_source_id: Mapping[str, int],
    *,
    retrieved_at: datetime | str,
) -> Iterator[Vehicle]:
    """Yield canonical vehicles after validating and explicitly enriching rows.

    Horsepower is deliberately supplied as a keyed enrichment rather than
    guessed from listing text.  This keeps the raw Craigslist observations
    separate from fields required by the canonical inventory schema.
    """

    for row in iter_craigslist_rows(csv_path):
        source_id = str(row.id)
        horsepower = horsepower_by_source_id.get(source_id)
        if horsepower is None:
            raise ValueError(f"missing horsepower enrichment for Craigslist row '{source_id}'")
        candidate = normalize_craigslist_row(row, retrieved_at=retrieved_at)
        yield normalize_inventory_record(candidate.to_inventory_record(horsepower=horsepower))


def ingest_craigslist_csv(
    csv_path: str | Path,
    output_path: str | Path,
    horsepower_by_source_id: Mapping[str, int],
    *,
    retrieved_at: datetime | str,
) -> tuple[int, int]:
    """Ingest a Craigslist CSV and return ``(accepted, database_total)``."""

    store = SQLiteInventoryStore(output_path)
    try:
        accepted = store.ingest(
            iter_craigslist_vehicles(
                csv_path,
                horsepower_by_source_id,
                retrieved_at=retrieved_at,
            )
        )
        return accepted, store.count()
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stream a Craigslist CSV into canonical SQLite inventory"
    )
    parser.add_argument("--input", required=True, help="Craigslist CSV export")
    parser.add_argument("--output", required=True, help="SQLite database path")
    parser.add_argument(
        "--horsepower-map",
        required=True,
        help="JSON object mapping Craigslist row IDs to explicit horsepower values",
    )
    parser.add_argument(
        "--retrieved-at",
        default=datetime.now(timezone.utc).isoformat(),
        help="ISO-8601 timestamp recorded on each normalized row",
    )
    args = parser.parse_args(argv)

    try:
        horsepower_map = _load_horsepower_map(args.horsepower_map)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        accepted, total = ingest_craigslist_csv(
            args.input,
            output_path,
            horsepower_map,
            retrieved_at=args.retrieved_at,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Ingested {accepted} Craigslist vehicle(s); database now contains {total} vehicle(s).")
    return 0


def _load_horsepower_map(path: str | Path) -> dict[str, int]:
    payload: Any = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError("horsepower map must be a JSON object")

    result: dict[str, int] = {}
    for source_id, horsepower in payload.items():
        if isinstance(horsepower, bool) or not isinstance(horsepower, int) or horsepower <= 0:
            raise ValueError(f"horsepower for Craigslist row '{source_id}' must be a positive integer")
        result[str(source_id)] = horsepower
    return result


if __name__ == "__main__":
    raise SystemExit(main())
