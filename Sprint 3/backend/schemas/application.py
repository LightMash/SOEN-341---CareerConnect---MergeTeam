"""
Owner: Job Application feature
Pydantic request/response shapes for /api/applications/*.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.application import APPLICATION_STATUSES

# "Applied" | "Under Review" | "Interview" | "Offered" | "Rejected", built from
# the same list the database constraint uses, so the two can never disagree.
ApplicationStatus = Literal[APPLICATION_STATUSES]


class ApplicationCreate(BaseModel):
    """Body of POST /api/applications."""

    model_config = ConfigDict(extra="forbid")  # reject unknown fields like "status"

    job_id: int = Field(gt=0)
    # Optional: when left out, the job seeker's PRIMARY resume is sent.
    resume_id: int | None = Field(default=None, gt=0)


class ApplicationOut(BaseModel):
    """One application, with the job's title/company flattened in so the
    frontend can render a list without a second request per row."""

    id: int
    job_id: int
    job_title: str
    company: str
    location: str
    job_type: str
    work_from: str
    resume_id: int | None  # None if the resume was deleted after applying
    resume_filename: str | None
    status: str
    applied_at: datetime.datetime
    updated_at: datetime.datetime


class ApplicationSubmitResponse(BaseModel):
    message: str
    application: ApplicationOut


# ---------------------------------------------------------------------------
# Status updates and history
# ---------------------------------------------------------------------------
class StatusUpdate(BaseModel):
    """Body of PATCH /api/applications/{id}/status."""

    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus  # anything else -> 422 before the route runs


class ApplicantOut(ApplicationOut):
    """What a recruiter sees for each applicant to one of their postings:
    the application plus who applied."""

    applicant_id: int
    applicant_name: str
    applicant_email: str


class StatusChangeOut(BaseModel):
    """One entry in an application's status timeline."""

    model_config = ConfigDict(from_attributes=True)

    old_status: str | None  # None for the first entry (submission)
    new_status: str
    changed_by: int
    changed_at: datetime.datetime


# ---------------------------------------------------------------------------
# Dashboard statistics (US-08)
# ---------------------------------------------------------------------------
class PeriodCount(BaseModel):
    """Applications submitted in one week (starting Monday) or one month (starting the 1st)."""

    period_start: datetime.date
    count: int


class ApplicationStatsOut(BaseModel):
    """Body of GET /api/applications/mine/stats."""

    total: int  # all-time, not limited to the weekly/monthly windows
    # Always has all five statuses, in pipeline order, zeros included
    by_status: dict[ApplicationStatus, int]
    weekly: list[PeriodCount]   # last 10 weeks, oldest first, current week last
    monthly: list[PeriodCount]  # last 12 months, oldest first, current month last