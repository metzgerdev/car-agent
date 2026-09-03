"""Domain models shared by the agent, tools, and API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Provenance:
    source_url: str
    source_type: str
    retrieved_at: str
    source_record_id: str | None = None
    license: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class Vehicle:
    id: str
    make: str
    model: str
    year: int
    price: int
    mileage: int
    body_style: str
    transmission: str
    drivetrain: str
    horsepower: int
    description: str
    tags: tuple[str, ...] = ()
    provenance: Provenance | None = None

    @property
    def name(self) -> str:
        return f"{self.year} {self.make} {self.model}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["tags"] = list(self.tags)
        result["name"] = self.name
        return result


@dataclass(frozen=True)
class VehicleFact:
    vehicle_id: str
    topic: str
    fact: str
    source: str
    source_url: str | None = None
    retrieved_at: str | None = None

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class ShopperPreferences:
    budget_max: int | None = None
    intended_use: str | None = None
    body_style: str | None = None
    driving_style: str | None = None
    timeline: str | None = None
    selected_vehicle_id: str | None = None
    name: str | None = None
    email: str | None = None
    preferred_time: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationState:
    conversation_id: str
    preferences: ShopperPreferences = field(default_factory=ShopperPreferences)
    stage: str = "qualifying"
    last_vehicle_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "preferences": self.preferences.to_dict(),
            "stage": self.stage,
            "last_vehicle_ids": self.last_vehicle_ids,
        }


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentResponse:
    message: str
    state: ConversationState
    trace: list[ToolCall]

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "state": self.state.to_dict(),
            "trace": [call.to_dict() for call in self.trace],
        }
