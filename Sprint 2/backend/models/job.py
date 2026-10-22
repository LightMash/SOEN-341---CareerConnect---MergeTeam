"""
Owner: Job Posting Management

One row per job posting, created and managed by a recruiter. Other features
build on this table:
  - Job Search reads the open postings and filters them
  - Applications point at a posting with applications.job_id
"""

import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base

# Every job type a posting can have. Single source of truth: the DB
# constraint below, the Pydantic schemas and the frontend dropdown/filter
# should all use this same list.
JOB_TYPES = ("Full-time", "Part-time", "Internship", "Contract")
DEFAULT_JOB_TYPE = "Full-time"


class Job(Base):
    __tablename__ = "jobs"

    __table_args__ = (
        # Plain string + CHECK instead of a Postgres ENUM: adding a type later
        # is a one-line change instead of an ALTER TYPE migration.
        CheckConstraint(
            "job_type IN (" + ", ".join(f"'{t}'" for t in JOB_TYPES) + ")",
            name="ck_job_type",
        ),
        # Salaries are optional but when both are given the range must make sense.
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="ck_job_salary_range",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # The recruiter who posted the job. Only they can edit, close or delete it,
    # and only they can see / manage its applicants.
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(120), nullable=False)
    company = Column(String(120), nullable=False)
    location = Column(String(120), nullable=False, default="")
    job_type = Column(String(20), nullable=False, default=DEFAULT_JOB_TYPE)
    category = Column(String(60), nullable=False, default="")  # e.g. "Software", used by search filters
    description = Column(Text, nullable=False, default="")

    # Yearly salary range in CAD; both optional ("not disclosed").
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)

    # Closing a posting keeps it (and its applications) in the database but
    # hides it from job search and refuses new applications. Deleting removes it.
    is_open = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    # One-way: job.recruiter gives the User who posted it without editing user.py.
    recruiter = relationship("User")