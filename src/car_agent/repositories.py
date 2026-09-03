"""Small local repositories used by the first vertical slice."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .data_pipeline import SQLiteInventoryStore, load_inventory_fixture
from .models import ShopperPreferences, Vehicle, VehicleFact


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class InventoryRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        configured_path = path or os.getenv("CAR_AGENT_INVENTORY_PATH")
        inventory_path = Path(configured_path) if configured_path else PROJECT_ROOT / "data" / "inventory.json"
        if inventory_path.suffix.lower() in {".sqlite", ".db"}:
            store = SQLiteInventoryStore(inventory_path)
            try:
                self._vehicles = store.all()
            finally:
                store.close()
        else:
            self._vehicles = load_inventory_fixture(inventory_path)

    def all(self) -> list[Vehicle]:
        return list(self._vehicles)

    def get(self, vehicle_id: str) -> Vehicle | None:
        return next((vehicle for vehicle in self._vehicles if vehicle.id == vehicle_id), None)

    def find_in_text(self, text: str) -> list[Vehicle]:
        normalized = text.lower()
        matches = []
        for vehicle in self._vehicles:
            identifiers = (vehicle.id, vehicle.model, vehicle.name, f"{vehicle.make} {vehicle.model}")
            if any(identifier.lower() in normalized for identifier in identifiers):
                matches.append(vehicle)
        return matches

    def search(self, preferences: ShopperPreferences, query: str | None = None) -> list[Vehicle]:
        candidates = self._vehicles
        if preferences.budget_max is not None:
            candidates = [vehicle for vehicle in candidates if vehicle.price <= preferences.budget_max]

        query_terms = self._terms(query)
        scored: list[tuple[int, Vehicle]] = []
        for vehicle in candidates:
            score = 0
            score += self._preference_score(vehicle, preferences.body_style, vehicle.body_style, 4)
            score += self._tag_score(vehicle, preferences.intended_use, 3)
            score += self._tag_score(vehicle, preferences.driving_style, 3)
            searchable = " ".join(
                [vehicle.make, vehicle.model, vehicle.body_style, vehicle.description, *vehicle.tags]
            ).lower()
            score += sum(1 for term in query_terms if term in searchable)
            scored.append((score, vehicle))

        scored.sort(key=lambda item: (-item[0], item[1].price, -item[1].year))
        return [vehicle for _, vehicle in scored[:5]]

    @staticmethod
    def _terms(query: str | None) -> list[str]:
        if not query:
            return []
        return [term for term in query.lower().split() if len(term) > 2]

    @staticmethod
    def _preference_score(vehicle: Vehicle, preference: str | None, value: str, points: int) -> int:
        return points if preference and preference.lower() == value.lower() else 0

    @staticmethod
    def _tag_score(vehicle: Vehicle, preference: str | None, points: int) -> int:
        if not preference:
            return 0
        normalized_preference = preference.lower().replace("-", " ")
        normalized_tags = {tag.lower().replace("-", " ") for tag in vehicle.tags}
        return points if normalized_preference in normalized_tags else 0


class KnowledgeRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        knowledge_path = Path(path) if path else PROJECT_ROOT / "data" / "knowledge.json"
        records = json.loads(knowledge_path.read_text())
        self._facts = [VehicleFact(**record) for record in records]

    def retrieve(self, vehicle_id: str, topic: str | None = None) -> list[VehicleFact]:
        facts = [fact for fact in self._facts if fact.vehicle_id == vehicle_id]
        if topic:
            topic_lower = topic.lower()
            topic_facts = [fact for fact in facts if fact.topic.lower() == topic_lower]
            if topic_facts:
                return topic_facts
        return facts


class TestDriveScheduler:
    """In-memory scheduler used to make the conversion workflow demonstrable."""

    def __init__(self, inventory: InventoryRepository) -> None:
        self.inventory = inventory
        self.requests: list[dict[str, str]] = []
        self._request_index: dict[tuple[str, str, str, str], dict[str, str]] = {}

    def schedule(
        self,
        *,
        vehicle_id: str,
        name: str,
        email: str,
        preferred_time: str,
    ) -> dict[str, Any]:
        if not self.inventory.get(vehicle_id):
            return {"ok": False, "error": "That vehicle is not in the current inventory."}
        if not name.strip():
            return {"ok": False, "error": "A name is required."}
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            return {"ok": False, "error": "Please provide a valid email address."}
        if not preferred_time.strip():
            return {"ok": False, "error": "A preferred day and time are required."}

        request_key = (
            vehicle_id,
            name.strip().casefold(),
            email.strip().casefold(),
            preferred_time.strip().casefold(),
        )
        existing = self._request_index.get(request_key)
        if existing:
            return {"ok": True, "duplicate": True, "request": dict(existing)}

        request_id = f"td-{len(self.requests) + 1:04d}"
        request = {
            "request_id": request_id,
            "vehicle_id": vehicle_id,
            "name": name.strip(),
            "email": email.strip(),
            "preferred_time": preferred_time.strip(),
            "status": "requested",
        }
        self.requests.append(request)
        self._request_index[request_key] = request
        return {"ok": True, "duplicate": False, "request": request}
