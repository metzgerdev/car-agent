"""Domain models shared by the agent, tools, and API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TracePhase = Literal["retrieve", "evaluate", "act"]
_EMAIL_ADDRESS_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def normalize_email_address(value: str) -> str:
    """Remove a mail client URI prefix before storing an email address."""

    return re.sub(r"^(?:mailto:)+", "", value.strip(), flags=re.IGNORECASE)


def is_valid_email_address(value: str | None) -> bool:
    """Accept a plain email address, never a URI or a partial match."""

    return bool(value and _EMAIL_ADDRESS_PATTERN.fullmatch(value.strip()))


class StrictContractModel(BaseModel):
    """Base model for trusted application contracts that reject unknown fields."""

    model_config = ConfigDict(extra="forbid", strict=True)


class TestDriveRequest(StrictContractModel):
    """Validated data required before a test-drive request can be created."""

    vehicle_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    preferred_time: str = Field(min_length=1, max_length=200)

    @field_validator("vehicle_id", "name", "preferred_time")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("email")
    @classmethod
    def require_valid_email(cls, value: str) -> str:
        cleaned = normalize_email_address(value)
        if not is_valid_email_address(cleaned):
            raise ValueError("email must be valid")
        return cleaned


class ScheduledTestDrive(StrictContractModel):
    """The durable, non-sensitive shape of a created test-drive request."""

    request_id: str = Field(min_length=1)
    vehicle_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    preferred_time: str = Field(min_length=1)
    status: Literal["requested"]


class TestDriveSuccess(StrictContractModel):
    ok: Literal[True]
    duplicate: bool
    request: ScheduledTestDrive


class TestDriveFailure(StrictContractModel):
    ok: Literal[False]
    error: str = Field(min_length=1)


_TRACE_DESCRIPTORS: dict[str, tuple[TracePhase, str]] = {
    "parse_intent": (
        "evaluate",
        "Classify an ambiguous shopper request before selecting a read-only route.",
    ),
    "list_inventory": (
        "retrieve",
        "Find inventory listings that match the shopper's stated preferences.",
    ),
    "lookup_vehicle_exact": (
        "retrieve",
        "Verify whether the requested year, make, and model is an exact inventory match.",
    ),
    "get_vehicle": (
        "retrieve",
        "Load the complete grounded listing for one specific vehicle.",
    ),
    "get_vehicle_facts": (
        "retrieve",
        "Retrieve sourced ownership and vehicle facts for the selected vehicle.",
    ),
    "get_service_history": (
        "retrieve",
        "Retrieve listing-level service records and their provenance.",
    ),
    "get_magazine_reviews": (
        "retrieve",
        "Retrieve curated magazine reviews and links for the selected vehicle.",
    ),
    "get_vehicle_comparison": (
        "evaluate",
        "Compare the grounded vehicle options requested by the shopper.",
    ),
    "create_test_drive": (
        "act",
        "Validate and create the requested test-drive appointment.",
    ),
}


def trace_descriptor(name: str) -> tuple[TracePhase, str]:
    """Return stable, deterministic metadata for a named tool."""

    return _TRACE_DESCRIPTORS.get(
        name,
        ("evaluate", f"Run the {name} operation and use its result to answer the shopper."),
    )


def trace_outcome(name: str, result: dict[str, Any]) -> str:
    """Summarize a tool result for the human-facing trace."""

    if name == "parse_intent":
        intent = result.get("intent", "unknown")
        confidence = result.get("confidence")
        if isinstance(confidence, (int, float)):
            return f"Classified as {intent} ({confidence:.0%} confidence)."
        return f"Classified as {intent}."
    if name == "list_inventory":
        return f"Found {result.get('count', 0)} matching listing(s)."
    if name == "lookup_vehicle_exact":
        status = result.get("status", "completed")
        return {
            "matched": "Found an exact inventory match.",
            "family_match": "Found a same-year inventory listing in the requested model family.",
            "not_found": "No exact inventory match found.",
            "ambiguous": "Found multiple inventory matches for the requested identity.",
        }.get(status, f"Exact lookup completed with status: {status}.")
    if name == "get_vehicle":
        return "Loaded the vehicle listing." if result.get("found") else "Vehicle listing was not found."
    if name == "get_vehicle_facts":
        return f"Retrieved {len(result.get('facts', []))} sourced fact(s)."
    if name == "get_service_history":
        count = result.get("record_count", 0)
        provenance = " synthetic demo record(s)" if result.get("synthetic") else " service record(s)"
        return f"Retrieved {count}{provenance}."
    if name == "get_magazine_reviews":
        return f"Retrieved {len(result.get('reviews', []))} magazine review(s)."
    if name == "get_vehicle_comparison":
        return f"Compared {len(result.get('vehicles', []))} vehicle option(s)."
    if name == "create_test_drive":
        if result.get("ok"):
            return "Test-drive request scheduled successfully."
        return str(result.get("error", "Test-drive request was not scheduled."))
    if result.get("error"):
        return str(result["error"])
    return "Operation completed."


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
class ServiceRecord:
    """A listing-level service event."""

    date: str
    mileage: int
    service_type: str
    details: str
    source: str = "synthetic_demo"

    def to_dict(self) -> dict[str, Any]:
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
    service_history: tuple[ServiceRecord, ...] = ()
    provenance: Provenance | None = None
    image_url: str | None = None
    image_source_url: str | None = None

    @property
    def name(self) -> str:
        return f"{self.year} {self.make} {self.model}"

    def to_dict(self, *, include_service_history: bool = True) -> dict[str, Any]:
        result = asdict(self)
        result["tags"] = list(self.tags)
        if include_service_history:
            result["service_history"] = [record.to_dict() for record in self.service_history]
        else:
            result.pop("service_history", None)
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
    shown_vehicle_ids: list[str] = field(default_factory=list)
    focused_vehicle_id: str | None = None
    pending_followup: Literal["service_history"] | None = None

    def to_dict(self, *, redact_sensitive: bool = False) -> dict[str, Any]:
        preferences = self.preferences.to_dict()
        if redact_sensitive:
            for field_name in ("name", "email"):
                if preferences.get(field_name) is not None:
                    preferences[field_name] = "[REDACTED]"
        return {
            "conversation_id": self.conversation_id,
            "preferences": preferences,
            "stage": self.stage,
            "last_vehicle_ids": self.last_vehicle_ids,
            "shown_vehicle_ids": self.shown_vehicle_ids,
            "focused_vehicle_id": self.focused_vehicle_id,
            "pending_followup": self.pending_followup,
        }


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    phase: TracePhase | None = None
    purpose: str | None = None
    outcome: str | None = None
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        phase, purpose = trace_descriptor(self.name)
        if self.phase is None:
            object.__setattr__(self, "phase", phase)
        if self.purpose is None:
            object.__setattr__(self, "purpose", purpose)
        if self.outcome is None:
            object.__setattr__(self, "outcome", trace_outcome(self.name, self.result))
        object.__setattr__(self, "duration_ms", round(max(0.0, self.duration_ms), 2))

    def to_dict(self, *, redact_sensitive: bool = False) -> dict[str, Any]:
        result = asdict(self)
        if redact_sensitive and self.name == "create_test_drive":
            result["arguments"] = _redact_contact_values(result["arguments"])
            result["result"] = _redact_contact_values(result["result"])
        return result


@dataclass(frozen=True)
class LLMUsage:
    """Provider-reported LLM usage accumulated for one shopper conversation."""

    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class AgentResponse:
    message: str
    state: ConversationState
    trace: list[ToolCall]
    metrics: LLMUsage = field(default_factory=LLMUsage)

    def to_dict(self, *, redact_sensitive: bool = True) -> dict[str, Any]:
        return {
            "message": self.message,
            "state": self.state.to_dict(redact_sensitive=redact_sensitive),
            "trace": [call.to_dict(redact_sensitive=redact_sensitive) for call in self.trace],
            "metrics": self.metrics.to_dict(),
        }


def _redact_contact_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key in {"name", "email", "phone"} else _redact_contact_values(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_contact_values(item) for item in value]
    return value
