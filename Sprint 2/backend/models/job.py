"""
Owner: Job postings (shared by Job Search, Applications and Recruiter Dashboard).
"""

import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)

    # The recruiter who posted the job. Used later to check that only the
    # owner of a posting can see its applicants or change their status.
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(120), nullable=False)
    company = Column(String(120), nullable=False)
    location = Column(String(120), nullable=False, default="")
    category = Column(String(60), nullable=False, default="")  # used by search filters
    description = Column(Text, nullable=False, default="")

    # A closed posting stays in the database (its applications still need it)
    # but no longer accepts new applications.
    is_open = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Lets us write job.recruiter to get the User who posted it.
    recruiter = relationship("User")
