"""
Owner: Notifications feature (US-09)

One NEW table. No existing table is altered on purpose: `create_all()` only
creates missing tables, it never adds columns to existing ones, so keeping
this feature in its own tables means teammates (and the shared Supabase
database) need no manual migration.

  notifications   one row per in-app message shown in the Notifications tab
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
)

from database import Base

# Single source of truth for the kinds of notification. The DB constraint, the
# service helpers and the frontend labels should all use this list.
NOTIFICATION_TYPES = (
    "new_application",       # -> recruiter: a job seeker applied to their posting
    "status_changed",        # -> job seeker: recruiter moved the application
    "interview_invitation",  # -> job seeker: status became "Interview"
)


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        # Plain string + CHECK instead of a Postgres ENUM (same choice as
        # jobs.job_type / applications.status): adding a type later is a
        # one-line change, not an ALTER TYPE migration.
        CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in NOTIFICATION_TYPES) + ")",
            name="ck_notification_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # The RECIPIENT. Deleting a user removes their notifications.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    type = Column(String(30), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(String(500), nullable=False, default="")

    # Optional deep link ("open this application"). SET NULL so deleting a
    # posting (which cascades to its applications) keeps the notification text.
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)

    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, index=True)

