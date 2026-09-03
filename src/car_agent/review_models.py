"""Typed editorial review metadata shown alongside inventory matches."""

from __future__ import annotations

import re

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from .models import Vehicle


class MagazineReview(BaseModel):
    """A short, paraphrased pointer to an established automotive publication."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    outlet: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: AnyHttpUrl
    summary: str = Field(min_length=1, max_length=500)

    def applies_to(self, vehicle: Vehicle) -> bool:
        return _slug(self.make) == _slug(vehicle.make) and _slug(self.model) == _slug(vehicle.model)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())
