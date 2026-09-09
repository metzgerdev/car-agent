"""Pydantic models for external vehicle data sources."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceProvenanceModel(BaseModel):
    """Provenance carried by normalized inventory and knowledge records."""

    model_config = ConfigDict(extra="forbid")

    source_url: str
    source_type: str
    retrieved_at: datetime
    source_record_id: str | None = None
    license: str | None = None


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
