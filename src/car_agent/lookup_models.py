"""Typed input and output models for exact inventory availability checks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class ExactVehicleQuery(BaseModel):
    """The year/make/model identity used for an authoritative lookup."""

    model_config = ConfigDict(extra="forbid", strict=True)

    year: int = Field(ge=1886, le=2100, description="Vehicle model year")
    make: str = Field(min_length=1, description="Vehicle manufacturer")
    model: str = Field(min_length=1, description="Complete vehicle model name")

    @field_validator("make", "model")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class ExactVehicleLookupResult(BaseModel):
    """Inspectable result that distinguishes exact and family-level matches."""

    model_config = ConfigDict(extra="forbid", strict=True)

    exact_match: bool
    status: Literal["matched", "family_match", "not_found", "ambiguous"]
    query: ExactVehicleQuery
    vehicle_id: str | None = None
    vehicle: dict[str, JsonValue] | None = None
    matches: list[dict[str, JsonValue]] = Field(default_factory=list)
    family_matches: list[dict[str, JsonValue]] = Field(default_factory=list)
