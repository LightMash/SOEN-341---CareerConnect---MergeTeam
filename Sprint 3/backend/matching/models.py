"""
Tables for the matching feature. None of the existing tables change: these
only point AT users and jobs with foreign keys.

The same tables are written out as plain SQL in
migrations/001_matching_tables.sql, for applying to a database by hand.
Keep the two in sync.
"""

import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)

from database import Base

from .rules import CATEGORIES

SOURCES = ("manual", "resume_scan", "reviewer_suggestion")


def _in_list(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class CustomQualification(Base):
    """A qualification someone added because it wasn't in the standard list.
    Its key is "custom.<id>" and it always counts as unverified."""

    __tablename__ = "custom_qualifications"
    __table_args__ = (
        # NULLS NOT DISTINCT: two rows with field = NULL still count as duplicates.
        UniqueConstraint(
            "category", "normalized_name", "field",
            name="uq_custom_qualification", postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(_in_list("category", CATEGORIES), name="ck_custom_qualification_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(20), nullable=False)
    name = Column(String(120), nullable=False)
    normalized_name = Column(String(120), nullable=False)
    field = Column(String(60), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    @property
    def key(self) -> str:
        return f"custom.{self.id}"


class SeekerQualification(Base):
    __tablename__ = "seeker_qualifications"
    __table_args__ = (
        PrimaryKeyConstraint("seeker_id", "qualification_key", name="pk_seeker_qualifications"),
        CheckConstraint(_in_list("source", SOURCES), name="ck_seeker_qualification_source"),
    )

    seeker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    qualification_key = Column(String(120), nullable=False)
    source = Column(String(30), nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)


class ListingRequirement(Base):
    __tablename__ = "listing_requirements"
    __table_args__ = (
        PrimaryKeyConstraint("listing_id", "qualification_key", name="pk_listing_requirements"),
        CheckConstraint("weight BETWEEN 1 AND 3", name="ck_listing_requirement_weight"),
    )

    listing_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    qualification_key = Column(String(120), nullable=False)
    is_required = Column(Boolean, nullable=False, default=True)
    # Only meaningful for bonus items (is_required = false).
    weight = Column(Integer, nullable=False, default=1)
