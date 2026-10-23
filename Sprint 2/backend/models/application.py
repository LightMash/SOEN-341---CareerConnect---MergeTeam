"""
Owner: Job Application feature

One row per (job seeker, job) pair: the job seeker applied to that job with
one of their resumes, and the application is currently at `status`.
"""

import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base

# Every status an application can be in, in pipeline order. Single source of
# truth: the DB constraint below, the Pydantic schemas and the frontend
# dropdown should all use this same list.
APPLICATION_STATUSES = ("Applied", "Under Review", "Interview", "Offered", "Rejected")
DEFAULT_STATUS = "Applied"


class Application(Base):
    __tablename__ = "applications"

    __table_args__ = (
        # Task 6.2: the database itself refuses a second application from the
        # same job seeker to the same job, even if two requests arrive at once.
        UniqueConstraint("job_id", "applicant_id", name="uq_application_job_applicant"),
        # A plain string column + CHECK instead of a Postgres ENUM type: adding
        # a status later is a one-line change instead of an ALTER TYPE migration.
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in APPLICATION_STATUSES) + ")",
            name="ck_application_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # If a job posting is deleted, its applications go with it.
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    applicant_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # The resume the job seeker selected when applying. Nullable with
    # SET NULL so a job seeker can still delete a resume they applied with:
    # the application survives, it just no longer has a file attached.
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)

    status = Column(String(20), nullable=False, default=DEFAULT_STATUS)

    applied_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    # One-way relationships: application.job / .applicant / .resume work,
    # without editing the Job, User or Resume files owned by other features.
    job = relationship("Job")
    applicant = relationship("User")
    resume = relationship("Resume")
