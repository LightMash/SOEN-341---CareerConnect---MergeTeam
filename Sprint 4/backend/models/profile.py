"""
Owner: User Profile feature.

One row per job seeker, holding their professional profile (headline, skills,
education, experience, links). Identity data (name, email, role) deliberately
stays in the `users` table; this table only holds the editable "resume-style"
information, so changing a profile never touches authentication data.
"""

import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)

    # unique=True turns this into a strict one-to-one relationship: the DB
    # itself guarantees a user can never end up with two profile rows.
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Plain text fields default to "" (not NULL) so the API never has to
    # distinguish "missing" from "empty" — the frontend can always render a string.
    headline = Column(String(120), nullable=False, default="")
    location = Column(String(120), nullable=False, default="")
    phone = Column(String(30), nullable=False, default="")
    summary = Column(Text, nullable=False, default="")

    # Lists live in JSON columns (list of strings / list of small objects).
    # Simpler than three child tables for a sprint-sized feature. IMPORTANT:
    # always assign a brand-new list on update — SQLAlchemy does not notice
    # in-place edits like `profile.skills.append(...)` on a plain JSON column.
    skills = Column(JSON, nullable=False, default=list)
    education = Column(JSON, nullable=False, default=list)
    experience = Column(JSON, nullable=False, default=list)

    linkedin_url = Column(String(255), nullable=False, default="")
    github_url = Column(String(255), nullable=False, default="")
    portfolio_url = Column(String(255), nullable=False, default="")

    # `onupdate` makes the DB layer refresh this automatically on every UPDATE.
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Lets us write profile.owner to get the linked User object.
    owner = relationship("User", back_populates="profile")
