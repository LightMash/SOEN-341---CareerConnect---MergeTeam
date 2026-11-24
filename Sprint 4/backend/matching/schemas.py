"""Request and response shapes for the /api/matching routes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["degree", "license", "certification", "language", "skill"]
Source = Literal["manual", "resume_scan", "reviewer_suggestion"]

MAX_SEEKER_QUALIFICATIONS = 300
MAX_REQUIREMENTS = 50
MAX_MATCH_LISTINGS = 100


class QualificationOut(BaseModel):
    key: str
    name: str
    category: str
    field: str | None = None
    rank: int | None = None
    custom: bool = False


class SearchResultOut(QualificationOut):
    matched_alias: str


class CustomQualificationIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category: Category
    name: str = Field(min_length=2, max_length=120)
    field: str | None = Field(default=None, max_length=60)


class CustomQualificationOut(QualificationOut):
    # True when an existing entry was returned instead of creating a new one.
    existing: bool


class SeekerQualificationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    source: Source = "manual"


class SeekerQualificationsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualifications: list[SeekerQualificationIn] = Field(max_length=MAX_SEEKER_QUALIFICATIONS)


class SeekerQualificationOut(QualificationOut):
    source: str


class RequirementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    is_required: bool = True
    # 1-3, only meaningful for bonus items.
    weight: int = Field(default=1, ge=1, le=3)


class RequirementsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: list[RequirementIn] = Field(max_length=MAX_REQUIREMENTS)


class RequirementOut(QualificationOut):
    is_required: bool
    weight: int


class ItemResultOut(BaseModel):
    key: str
    name: str
    category: str
    is_required: bool
    weight: int
    status: Literal["met", "missing", "bonus_missing", "possible"]
    exceeds: bool
    possible_name: str | None = None


class MatchOut(BaseModel):
    listing_id: int
    qualified: bool
    requirements: list[ItemResultOut]


class CandidateOut(BaseModel):
    key: str
    name: str
    category: str
    source: Literal["scan", "reviewer"]
    state: Literal["found", "in_progress", "questionable", "suggested"]
    reason: str | None = None
    snippet: str = ""
    already_added: bool = False


class UnresolvedOut(BaseModel):
    category: str | None = None
    name: str
    field: str | None = None


class ExtractOut(BaseModel):
    candidates: list[CandidateOut]
    unresolved: list[UnresolvedOut]
    message: str | None = None
    reviewer_enabled: bool


class ReviewerStatusOut(BaseModel):
    enabled: bool


class BreakdownRow(BaseModel):
    key: str
    name: str
    weight: int
    has: bool
    share: float | None = None
    highlight: str | None = None


class SuggestionOut(BaseModel):
    key: str
    name: str
    current: float
    new: float
    improvement: float


class MissingOut(BaseModel):
    key: str
    name: str
    status: str
    possible_name: str | None = None


class StandingOut(BaseModel):
    status: Literal["percentile", "fraction", "equal_on_paper", "not_qualified"]
    label: str | None
    percentile: int | None
    fraction: float | None
    score: int | None
    max_score: int | None
    pool_size: int
    other_applicants: int
    as_of: str
    message: str | None
    breakdown: list[BreakdownRow]
    suggestions: list[SuggestionOut]
    missing: list[MissingOut]
    profile_nudge: str | None
    note: str
