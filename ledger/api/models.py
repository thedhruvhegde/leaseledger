"""Request/response wrappers for the HTTP API. Domain models come from ledger.schemas (the shared contract)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ledger.schemas import (Breakeven, Fee, GroupRequest, Listing, ParseScheduleResult, Profile, Utility)

ListingIds = Optional[list[str]]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluateRequest(_Strict):
    profile: Profile
    listing_ids: ListingIds = Field(default=None, max_length=200,
                                    description="Listings to evaluate. Default: demo set if present, else all.")


class RobustnessRequest(EvaluateRequest):
    samples: int = Field(default=2000, ge=50, le=10000)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)


class PairRequest(_Strict):
    profile: Profile
    a: str = Field(min_length=1, max_length=120)
    b: str = Field(min_length=1, max_length=120)
    listing_ids: ListingIds = Field(default=None, max_length=200,
                                    description="Context set (for normalization). a and b are always included.")

    @model_validator(mode="after")
    def _distinct(self):
        if self.a == self.b:
            raise ValueError("a and b must be different listings")
        return self


class DiffRequest(_Strict):
    before: Profile
    after: Profile
    listing_ids: ListingIds = Field(default=None, max_length=200)


class GroupApiRequest(GroupRequest):
    """GroupRequest (members, listing_ids) — listing_ids resolved like /evaluate."""


class ParseScheduleRequest(_Strict):
    text: str = Field(min_length=1, max_length=2000)
    use_ai: bool = Field(default=True, description="false forces the deterministic rule parser")


class ParseScheduleResponse(ParseScheduleResult):
    model: Optional[str] = None
    latency_ms: Optional[float] = None
    llm_error: Optional[str] = None
    pii_removed: list[str] = []
    notice: str = ("Free text may be sent to an AI provider (Groq) for parsing after emails, phone numbers and street "
                   "addresses are removed. Confirm the weekly grid before scoring.")


class ExtractListingRequest(_Strict):
    text: str = Field(min_length=1, max_length=6000)
    base: Optional[dict] = Field(default=None, description="Partial Listing; e.g. its rent is used to compute a "
                                                           "deposit stated as a multiple of rent")
    use_ai: bool = True


class CustomListingIn(BaseModel):
    """A listing entered by the student. id is assigned by the server."""
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    address: Optional[str] = Field(default=None, max_length=200)
    lat: float = Field(ge=42.0, le=42.6)
    lon: float = Field(ge=-84.2, le=-83.4)
    neighborhood: Optional[str] = None
    provenance: Literal["observed", "synthetic", "user"] = "user"
    source_url: Optional[str] = Field(default=None, max_length=500)
    observed_on: Optional[str] = None
    rent: float = Field(ge=0, le=20000)
    rent_basis: Literal["unit", "bed"]
    rent_is_range: bool = False
    rent_low: Optional[float] = None
    rent_high: Optional[float] = None
    bedrooms: int = Field(ge=0, le=12)
    baths: Optional[float] = None
    sqft: Optional[float] = None
    rooms: list[dict] = []
    fees: list[Fee] = Field(default=[], max_length=30)
    utilities_included: list[Utility] = []
    building_type: Literal["tower", "house", "duplex", "apartment", "coop", "other"] = "other"
    year_built: Optional[int] = None
    heating: Optional[Literal["gas", "electric_resistance", "heat_pump", "steam", "unknown"]] = "unknown"
    furnished: Optional[bool] = None
    in_unit_laundry: Optional[bool] = None
    parking_monthly: Optional[float] = None
    pets_allowed: Optional[bool] = None
    lease_term_months: Optional[int] = 12
    lease_start: Optional[str] = None
    amenities: list[str] = []
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _url(self):
        if self.source_url and not self.source_url.startswith(("http://", "https://")):
            raise ValueError("source_url must be an http(s) URL")
        return self


class CustomListingRequest(_Strict):
    listing: CustomListingIn


class CustomListingResponse(BaseModel):
    id: str
    listing: Listing
    stored: Literal["memory"] = "memory"
    expires_in_s: int
    notes: list[str] = []


class CompareResponse(BaseModel):
    """Engine compare(): see ledger/engine. Loosely typed so engine additions pass through."""
    model_config = ConfigDict(extra="allow")
    a: Any = None
    b: Any = None
    line_diffs: list[Any] = []
    trip_diffs: list[Any] = []
    breakevens: list[Breakeven | dict] = []
    facts: list[str] = []


class DiffResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    rank_changes: Any = None
    deltas: Any = None
    causes: list[Any] = []
    top_changed: Any = None


class ErrorBody(BaseModel):
    detail: str
    code: str
    errors: list[dict] = []
    request_id: Optional[str] = None
