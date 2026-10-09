"""
Owner: User Profile feature.
Pydantic request/response shapes for /api/profile/me.

Validation lives here (not in the router) so an invalid request is rejected
with a 422 BEFORE the route function runs — a failed save can never leave the
stored profile half-updated.
"""

import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Digits, spaces and the usual phone punctuation only.
PHONE_PATTERN = re.compile(r"^[0-9+()\-\s.]*$")


def _check_url(value: str) -> str:
    # Only http(s) links are accepted. This matters for security: the frontend
    # renders these as clickable <a href> links, and a stored "javascript:..."
    # URL would run code when clicked.
    if value and not value.lower().startswith(("http://", "https://")):
        raise ValueError("Links must start with http:// or https://")
    return value


class EducationItem(BaseModel):
    # str_strip_whitespace trims every string BEFORE the length checks run,
    # so a school name of "   " is rejected by min_length=1.
    model_config = ConfigDict(str_strip_whitespace=True)

    school: str = Field(min_length=1, max_length=120)
    degree: str = Field(default="", max_length=120)
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)  # None = still studying


class ExperienceItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)  # None = current job


class ProfileUpdate(BaseModel):
    """Body of PUT /api/profile/me — the full set of editable fields."""
    model_config = ConfigDict(str_strip_whitespace=True)

    headline: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=30)
    summary: str = Field(default="", max_length=2000)
    skills: list[str] = Field(default_factory=list, max_length=30)
    education: list[EducationItem] = Field(default_factory=list, max_length=10)
    experience: list[ExperienceItem] = Field(default_factory=list, max_length=10)
    linkedin_url: str = Field(default="", max_length=255)
    github_url: str = Field(default="", max_length=255)
    portfolio_url: str = Field(default="", max_length=255)

    @field_validator("phone")
    @classmethod
    def phone_format(cls, value: str) -> str:
        if not PHONE_PATTERN.match(value):
            raise ValueError("Phone can only contain digits, spaces and + ( ) - .")
        return value

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for skill in value:
            skill = skill.strip()
            if not skill or skill.lower() in seen:
                continue  # silently drop blanks and case-insensitive duplicates
            if len(skill) > 40:
                raise ValueError("Each skill must be 40 characters or fewer")
            seen.add(skill.lower())
            cleaned.append(skill)
        return cleaned

    @field_validator("linkedin_url", "github_url", "portfolio_url")
    @classmethod
    def url_format(cls, value: str) -> str:
        return _check_url(value)


class ProfileOut(BaseModel):
    id: int
    user_id: int
    headline: str
    location: str
    phone: str
    summary: str
    skills: list[str]
    education: list[EducationItem]
    experience: list[ExperienceItem]
    linkedin_url: str
    github_url: str
    portfolio_url: str
    # Not database columns: both are computed on every request in
    # routers/profile.py (which is why ProfileOut is built by hand there
    # instead of with from_attributes).
    #   completeness: 0-100
    #   missing: display names of the sections still empty, e.g. ["Skills", "Resume"]
    completeness: int
    missing: list[str]
    updated_at: datetime.datetime
