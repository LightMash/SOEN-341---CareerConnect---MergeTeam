"""
Owner: Resume upload feature.
"""

import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)

    # Must match an existing row in "users" — DB rejects bad user_ids.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Original uploaded name, for display only — never used to find the file.
    filename = Column(String(255), nullable=False)

    # Actual unique location on disk — this is what we use to read/delete it.
    filepath = Column(Text, nullable=False)

    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Sprint 2: marks the resume that future features (job applications) send
    # by default. At most ONE resume per user is primary at a time; that rule
    # is enforced in routers/resume.py (set_primary_resume / delete_resume),
    # not by a DB constraint.
    #
    # NOTE: Base.metadata.create_all() never adds columns to an existing
    # table, so on a database that already has a `resumes` table this column
    # must be added once by hand:
    #   ALTER TABLE resumes ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT FALSE;
    is_primary = Column(Boolean, nullable=False, default=False)

    # Lets us write resume.owner to get the linked User object.
    owner = relationship("User", back_populates="resumes")
