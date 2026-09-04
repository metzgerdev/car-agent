"""Explicit tools the sales agent can call."""

from __future__ import annotations

import re
from typing import Any

from .lookup_models import ExactVehicleLookupResult, ExactVehicleQuery
from .models import ShopperPreferences
from .repositories import InventoryRepository, KnowledgeRepository, ReviewRepository, TestDriveScheduler


class SalesTools:
    def __init__(
        self,
        inventory: InventoryRepository | None = None,
        knowledge: KnowledgeRepository | None = None,
        scheduler: TestDriveScheduler | None = None,
        reviews: ReviewRepository | None = None,
    ) -> None:
        self.inventory = inventory or InventoryRepository()
        self.knowledge = knowledge or KnowledgeRepository()
        self.reviews = reviews or ReviewRepository()
        self.scheduler = scheduler or TestDriveScheduler(self.inventory)

    def search_inventory(self, filters: dict[str, Any]) -> dict[str, Any]:
        preferences = ShopperPreferences(
            budget_max=filters.get("budget_max"),
            intended_use=filters.get("intended_use"),
            body_style=filters.get("body_style"),
            driving_style=filters.get("driving_style"),
        )
        vehicles = self.inventory.search(preferences, filters.get("query"))
        return {"count": len(vehicles), "vehicles": [vehicle.to_dict() for vehicle in vehicles]}

    def lookup_vehicle_exact(self, query: dict[str, Any]) -> dict[str, Any]:
        """Check exact year/make/model availability without fuzzy matching."""

        parsed_query = ExactVehicleQuery.model_validate(query)
        normalized_make = _normalize_identity(parsed_query.make)
        normalized_model = _normalize_identity(parsed_query.model)
        matches = [
            vehicle
            for vehicle in self.inventory.all()
            if vehicle.year == parsed_query.year
            and _normalize_identity(vehicle.make) == normalized_make
            and _normalize_identity(vehicle.model) == normalized_model
        ]
        match_dicts = [vehicle.to_dict() for vehicle in matches]
        if len(matches) == 1:
            result = ExactVehicleLookupResult(
                exact_match=True,
                status="matched",
                query=parsed_query,
                vehicle_id=matches[0].id,
                vehicle=match_dicts[0],
            )
        elif len(matches) > 1:
            result = ExactVehicleLookupResult(
                exact_match=False,
                status="ambiguous",
                query=parsed_query,
                matches=match_dicts,
            )
        else:
            result = ExactVehicleLookupResult(
                exact_match=False,
                status="not_found",
                query=parsed_query,
            )
        return result.model_dump(mode="python")

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any]:
        vehicle = self.inventory.get(vehicle_id)
        if not vehicle:
            return {"found": False, "error": "Vehicle not found."}
        return {"found": True, "vehicle": vehicle.to_dict()}

    def retrieve_vehicle_facts(self, vehicle_id: str, topic: str | None = None) -> dict[str, Any]:
        facts = self.knowledge.retrieve(vehicle_id, topic)
        return {
            "vehicle_id": vehicle_id,
            "facts": [fact.to_dict() for fact in facts],
            "source_count": len({fact.source for fact in facts}),
        }

    def retrieve_magazine_reviews(self, vehicle_id: str) -> dict[str, Any]:
        """Return curated editorial summaries and links for one inventory vehicle."""

        vehicle = self.inventory.get(vehicle_id)
        if not vehicle:
            return {"found": False, "vehicle_id": vehicle_id, "reviews": [], "error": "Vehicle not found."}
        reviews = self.reviews.retrieve(vehicle)
        return {
            "found": True,
            "vehicle_id": vehicle.id,
            "vehicle_name": vehicle.name,
            "reviews": [review.model_dump(mode="json") for review in reviews],
        }

    def compare_vehicles(self, vehicle_ids: list[str]) -> dict[str, Any]:
        vehicles = [self.inventory.get(vehicle_id) for vehicle_id in vehicle_ids]
        found = [vehicle for vehicle in vehicles if vehicle]
        return {
            "vehicles": [vehicle.to_dict() for vehicle in found],
            "missing_ids": [vehicle_id for vehicle_id, vehicle in zip(vehicle_ids, vehicles) if not vehicle],
        }

    def schedule_test_drive(
        self,
        *,
        vehicle_id: str,
        name: str,
        email: str,
        preferred_time: str,
    ) -> dict[str, Any]:
        return self.scheduler.schedule(
            vehicle_id=vehicle_id,
            name=name,
            email=email,
            preferred_time=preferred_time,
        )

    @staticmethod
    def valid_email(email: str | None) -> bool:
        return bool(email and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def _normalize_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())
