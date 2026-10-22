"""
Owner: Job Application feature
Pydantic request/response shapes for /api/applications/*.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    resume_id: int | None  # None if the resume was deleted after applying
    resume_filename: str | None
    status: str
    applied_at: datetime.datetime
    updated_at: datetime.datetime


class ApplicationSubmitResponse(BaseModel):
    message: str
    application: ApplicationOut
