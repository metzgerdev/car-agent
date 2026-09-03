"""Pydantic contracts for external vehicle data sources.

The source models intentionally preserve the shape of each provider at the
boundary.  Adapters then map those validated payloads into the small domain
models used by the sales agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceProvenanceModel(BaseModel):
    """Provenance carried by normalized inventory and knowledge records."""

    model_config = ConfigDict(extra="forbid")

    source_url: str
    source_type: str
    retrieved_at: datetime
    source_record_id: str | None = None
    license: str | None = None


class CraigslistVehicleRow(BaseModel):
    """Typed representation of one row from Austin Reese's dataset.

    The source contains nullable marketplace fields, so optionality is kept in
    this model.  The adapter is responsible for deciding whether a row has
    enough information to become a canonical inventory record.
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    id: int | str
    url: str | None = None
    region: str | None = None
    region_url: str | None = None
    price: int | float | None = None
    year: int | float | None = None
    manufacturer: str | None = None
    model: str | None = None
    condition: str | None = None
    cylinders: str | None = None
    fuel: str | None = None
    odometer: int | float | None = None
    title_status: str | None = None
    transmission: str | None = None
    vin: str | None = Field(default=None, alias="VIN")
    drive: str | None = None
    size: str | None = None
    type: str | None = None
    paint_color: str | None = None
    image_url: str | None = None
    description: str | None = None
    county: str | None = None
    state: str | None = None
    lat: float | None = None
    long: float | None = None
    posting_date: datetime | None = None


class CraigslistInventoryCandidate(BaseModel):
    """A Craigslist row mapped toward the canonical inventory shape.

    Horsepower is optional here because the marketplace dataset does not
    reliably provide it.  Calling ``to_inventory_record`` without an explicit
    horsepower enrichment fails rather than guessing.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    price: int | None = None
    mileage: int | None = None
    body_style: str | None = None
    transmission: str | None = None
    drivetrain: str | None = None
    horsepower: int | None = Field(default=None, gt=0)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    provenance: SourceProvenanceModel

    def to_inventory_record(self, *, horsepower: int | None = None) -> dict[str, Any]:
        resolved_horsepower = horsepower if horsepower is not None else self.horsepower
        if resolved_horsepower is None:
            raise ValueError(
                "horsepower enrichment is required before this source row can become inventory"
            )
        record = self.model_dump(mode="json", exclude={"horsepower"})
        record["horsepower"] = resolved_horsepower
        return record


class NHTSAVPICResult(BaseModel):
    """One variable/value item returned by the NHTSA vPIC decoder."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    variable: str = Field(alias="Variable")
    value: str | None = Field(default=None, alias="Value")
    value_id: str | None = Field(default=None, alias="ValueId")
    variable_id: int | None = Field(default=None, alias="VariableId")


class NHTSAVPICResponse(BaseModel):
    """Typed NHTSA vPIC decoder response."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message: str | None = Field(default=None, alias="Message")
    search_criteria: str | None = Field(default=None, alias="SearchCriteria")
    results: list[NHTSAVPICResult] = Field(default_factory=list, alias="Results")


class NHTSARecallRecord(BaseModel):
    """A recall record returned by the NHTSA recalls endpoint."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    manufacturer: str | None = Field(default=None, alias="Manufacturer")
    campaign_number: str | None = Field(default=None, alias="NHTSACampaignNumber")
    component: str | None = Field(default=None, alias="Component")
    summary: str | None = Field(default=None, alias="Summary")
    consequence: str | None = Field(default=None, alias="Consequence")
    remedy: str | None = Field(default=None, alias="Remedy")
    report_received_date: str | None = Field(default=None, alias="ReportReceivedDate")
    recall_link: str | None = Field(default=None, alias="RecallLink")


class NHTSARecallResponse(BaseModel):
    """Typed NHTSA recall response."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    count: int = Field(default=0, alias="Count")
    message: str | None = Field(default=None, alias="Message")
    results: list[NHTSARecallRecord] = Field(default_factory=list)


class EPAFuelEconomyVehicle(BaseModel):
    """Relevant fields from one FuelEconomy.gov vehicle record."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int | None = None
    year: int | None = None
    make: str | None = None
    model: str | None = None
    city_mpg: int | None = Field(default=None, alias="city08")
    highway_mpg: int | None = Field(default=None, alias="highway08")
    combined_mpg: int | None = Field(default=None, alias="comb08")
    fuel_type: str | None = Field(default=None, alias="fuelType")
    annual_fuel_cost: int | None = Field(default=None, alias="fuelCost08")
    co2_grams_per_mile: int | None = Field(default=None, alias="co2")
    drive: str | None = None
    transmission: str | None = Field(default=None, alias="trany")
    vehicle_class: str | None = Field(default=None, alias="VClass")
    range_miles: int | None = Field(default=None, alias="rangeA")
