"""Local inventory, review, and scheduling repositories."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_pipeline import load_inventory_fixture
from .models import (
    ScheduledTestDrive,
    ShopperPreferences,
    TestDriveFailure,
    TestDriveRequest,
    TestDriveSuccess,
    Vehicle,
    VehicleFact,
)
from .review_models import MagazineReview


_FIXTURE_NAMES = ("inventory.json", "knowledge.json", "reviews.json")
_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _has_fixtures(path: Path) -> bool:
    return all((path / name).is_file() for name in _FIXTURE_NAMES)


def _resolve_project_root() -> Path:
    configured_root = os.getenv("CAR_AGENT_PROJECT_ROOT")
    candidates = [Path(configured_root)] if configured_root else []
    candidates.extend((_SOURCE_ROOT, Path.cwd()))
    for candidate in candidates:
        if (candidate / "data").is_dir() or (candidate / ".env").is_file():
            return candidate
    return Path.cwd()


def _resolve_data_root(project_root: Path) -> Path:
    configured_data = os.getenv("CAR_AGENT_DATA_DIR")
    candidates = [Path(configured_data)] if configured_data else []
    candidates.extend(
        (
            project_root / "data",
            _SOURCE_ROOT / "data",
            Path.cwd() / "data",
            Path(sys.prefix) / "share" / "classic-car-agent" / "data",
        )
    )
    for candidate in candidates:
        if _has_fixtures(candidate):
            return candidate
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Car-agent data fixtures were not found. Searched: {searched}")


PROJECT_ROOT = _resolve_project_root()
DATA_ROOT = _resolve_data_root(PROJECT_ROOT)


@dataclass(frozen=True)
class InventoryReferenceResolution:
    """Inventory-backed candidates for a shopper's vehicle reference."""

    candidates: tuple[Vehicle, ...]
    source: str

    @property
    def vehicle_id(self) -> str | None:
        return self.candidates[0].id if len(self.candidates) == 1 else None


class InventoryReferenceIndex:
    """Resolve vehicle references exclusively against the loaded inventory."""

    def __init__(self, vehicles: list[Vehicle]) -> None:
        self._vehicles = tuple(vehicles)
        self._by_id = {vehicle.id: vehicle for vehicle in vehicles}
        self._inventory_ids: dict[str, set[str]] = {}
        self._exact_identities: dict[str, set[str]] = {}
        self._make_models: dict[str, set[str]] = {}
        self._make_families: dict[str, set[str]] = {}
        self._models: dict[str, set[str]] = {}
        self._model_families: dict[str, set[str]] = {}

        for vehicle in vehicles:
            family = vehicle.model.split(maxsplit=1)[0]
            self._add(self._inventory_ids, vehicle.id, vehicle.id)
            self._add(self._exact_identities, vehicle.name, vehicle.id)
            self._add(self._make_models, f"{vehicle.make} {vehicle.model}", vehicle.id)
            self._add(self._make_families, f"{vehicle.make} {family}", vehicle.id)
            self._add(self._models, vehicle.model, vehicle.id)
            if self._is_distinct_family_alias(family):
                self._add(self._model_families, family, vehicle.id)

    @staticmethod
    def _add(index: dict[str, set[str]], alias: str, vehicle_id: str) -> None:
        index.setdefault(alias.casefold(), set()).add(vehicle_id)

    @staticmethod
    def _is_distinct_family_alias(alias: str) -> bool:
        """Avoid treating common short prose tokens as vehicle model references."""

        normalized = re.sub(r"[^a-z0-9]", "", alias.casefold())
        return any(character.isdigit() for character in normalized) or len(normalized) >= 3

    def resolve(
        self,
        text: str,
        *,
        scope_vehicle_ids: list[str] | tuple[str, ...] | None = None,
    ) -> InventoryReferenceResolution:
        """Return canonical candidates, preferring an exact identity over context."""

        for source, aliases, exact_identity in (
            ("inventory_id", self._inventory_ids, True),
            ("exact_identity", self._exact_identities, True),
            ("make_model", self._make_models, False),
            ("make_family", self._make_families, False),
            ("model", self._models, False),
            ("model_family", self._model_families, False),
        ):
            matched_ids = self._matching_ids(text, aliases)
            if not matched_ids:
                continue
            candidates = self._ordered_candidates(matched_ids)
            if not exact_identity:
                scoped_candidates = self._scoped_candidates(matched_ids, scope_vehicle_ids)
                if scoped_candidates:
                    return InventoryReferenceResolution(tuple(scoped_candidates), "recent_results")
            return InventoryReferenceResolution(tuple(candidates), source)
        return InventoryReferenceResolution((), "none")

    @staticmethod
    def _matching_ids(text: str, aliases: dict[str, set[str]]) -> set[str]:
        normalized = text.casefold()
        matched: set[str] = set()
        for alias, vehicle_ids in aliases.items():
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
                matched.update(vehicle_ids)
        return matched

    def _ordered_candidates(self, vehicle_ids: set[str]) -> list[Vehicle]:
        return [vehicle for vehicle in self._vehicles if vehicle.id in vehicle_ids]

    def _scoped_candidates(
        self,
        vehicle_ids: set[str],
        scope_vehicle_ids: list[str] | tuple[str, ...] | None,
    ) -> list[Vehicle]:
        if not scope_vehicle_ids:
            return []
        return [
            self._by_id[vehicle_id]
            for vehicle_id in scope_vehicle_ids
            if vehicle_id in vehicle_ids and vehicle_id in self._by_id
        ]


class InventoryRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        inventory_path = Path(path) if path else DATA_ROOT / "inventory.json"
        self._vehicles = load_inventory_fixture(inventory_path)
        self._reference_index = InventoryReferenceIndex(self._vehicles)

    def all(self) -> list[Vehicle]:
        return list(self._vehicles)

    def get(self, vehicle_id: str) -> Vehicle | None:
        return next((vehicle for vehicle in self._vehicles if vehicle.id == vehicle_id), None)

    def resolve_reference(
        self,
        text: str,
        *,
        scope_vehicle_ids: list[str] | tuple[str, ...] | None = None,
    ) -> InventoryReferenceResolution:
        return self._reference_index.resolve(text, scope_vehicle_ids=scope_vehicle_ids)

    def find_in_text(self, text: str) -> list[Vehicle]:
        return list(self.resolve_reference(text).candidates)

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
            query_matches = sum(1 for term in query_terms if term in searchable)
            # Award lexical relevance only for complete identity queries.
            if query_matches == len(query_terms):
                score += query_matches
            scored.append((score, vehicle))

        scored.sort(key=lambda item: (-item[0], item[1].price, -item[1].year))
        return [vehicle for _, vehicle in scored[:5]]

    @staticmethod
    def _terms(query: str | None) -> list[str]:
        if not query:
            return []
        return [
            term
            for term in query.lower().split()
            if len(term) > 2 or any(character.isdigit() for character in term)
        ]

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
        knowledge_path = Path(path) if path else DATA_ROOT / "knowledge.json"
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


class ReviewRepository:
    """Curated editorial links matched to inventory make/model pairs."""

    def __init__(self, path: str | Path | None = None) -> None:
        review_path = Path(path) if path else DATA_ROOT / "reviews.json"
        records = json.loads(review_path.read_text())
        self._reviews = [MagazineReview.model_validate(record) for record in records]

    def retrieve(self, vehicle: Vehicle) -> list[MagazineReview]:
        return [review for review in self._reviews if review.applies_to(vehicle)]


class TestDriveScheduler:
    """In-memory test-drive scheduler."""

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
        try:
            request_input = TestDriveRequest(
                vehicle_id=vehicle_id,
                name=name,
                email=email,
                preferred_time=preferred_time,
            )
        except ValueError as exc:
            return TestDriveFailure(ok=False, error=_test_drive_validation_message(exc)).model_dump()
        if not self.inventory.get(request_input.vehicle_id):
            return TestDriveFailure(
                ok=False,
                error="That vehicle is not in the current inventory.",
            ).model_dump()

        request_key = (
            request_input.vehicle_id,
            request_input.name.casefold(),
            request_input.email.casefold(),
            request_input.preferred_time.casefold(),
        )
        existing = self._request_index.get(request_key)
        if existing:
            return TestDriveSuccess(
                ok=True,
                duplicate=True,
                request=ScheduledTestDrive.model_validate(existing),
            ).model_dump()

        request_id = f"td-{len(self.requests) + 1:04d}"
        request = ScheduledTestDrive(
            request_id=request_id,
            vehicle_id=request_input.vehicle_id,
            name=request_input.name,
            email=request_input.email,
            preferred_time=request_input.preferred_time,
            status="requested",
        )
        request_payload = request.model_dump()
        self.requests.append(request_payload)
        self._request_index[request_key] = request_payload
        return TestDriveSuccess(ok=True, duplicate=False, request=request).model_dump()


def _test_drive_validation_message(error: ValueError) -> str:
    """Keep validation failures actionable without exposing Pydantic internals."""

    errors = getattr(error, "errors", lambda: [])()
    fields = {entry["loc"][0] for entry in errors if entry.get("loc")}
    if "email" in fields:
        return "Please provide a valid email address."
    if "name" in fields:
        return "A name is required."
    if "preferred_time" in fields:
        return "A preferred day and time are required."
    return "The test-drive request has invalid details."
