"""
Owner: Job Posting Management
Pydantic request/response shapes for /api/jobs/*.

Validation lives here so an invalid posting is rejected with a 422 BEFORE
the route runs, and a failed save can never leave a posting half-updated.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.job import DEFAULT_JOB_TYPE, JOB_TYPES, DEFAULT_WORK_FROM, WORK_FROM

# "Full-time" | "Part-time" | "Internship" | "Contract", built from the same
# list the database constraint uses.
JobType = Literal[JOB_TYPES]
# "On-site" | "Remote" | "Hybrid", built from the same list the database 
# constraint uses.
WorkFrom = Literal[WORK_FROM]


class JobIn(BaseModel):
    """
    Body of POST /api/jobs and PUT /api/jobs/{id}: the full set of editable
    fields. PUT (not PATCH) like the profile feature: the form always sends
    everything, so clearing a field is just sending "".
    """

    # Trim spaces first, so a title of "   " is rejected by min_length=1.
    # extra="forbid" stops clients from setting recruiter_id / is_open here.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=120)
    job_type: JobType = DEFAULT_JOB_TYPE
    work_from: WorkFrom = DEFAULT_WORK_FROM
    category: str = Field(default="", max_length=60)
    description: str = Field(default="", max_length=5000)
    salary_min: int | None = Field(default=None, ge=0, le=10_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=10_000_000)

    @model_validator(mode="after")
    def salary_range(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min cannot be greater than salary_max")
        return self


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recruiter_id: int
    title: str
    company: str
    location: str
    job_type: str
    work_from: str
    category: str
    description: str
    salary_min: int | None
    salary_max: int | None
    is_open: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
