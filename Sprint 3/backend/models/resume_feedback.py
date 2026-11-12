"""
Owner: AI Resume Feedback (US-16, Task 16.2)

One row per AI review of a resume. Saving results means:
  - reopening the feedback panel costs no API call (and no free-tier quota);
  - the user keeps a history of past reviews;
  - the "apply suggestions" step (Task 16.3 / Sprint 4) works from a stable
    copy of the suggestions instead of asking the AI again.

This is a NEW table, so Base.metadata.create_all() in app.py creates it on
the next startup. No manual ALTER TABLE is needed (unlike adding a column).
"""

import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class ResumeFeedback(Base):
    __tablename__ = "resume_feedback"

    id = Column(Integer, primary_key=True, index=True)

    # Deleting a resume deletes its feedback too (the database does it).
    resume_id = Column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Optional: the job posting the feedback was tailored to. If the posting
    # is deleted later, the feedback stays and simply loses that link.
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)

    overall_score = Column(Integer, nullable=False)  # 0-100
    summary = Column(Text, nullable=False, default="")

    # Lists live in JSON columns, same approach as models/profile.py.
    strengths = Column(JSON, nullable=False, default=list)  # list[str]
    suggestions = Column(JSON, nullable=False, default=list)  # list[dict], see SuggestionOut

    # Which Gemini model wrote this, useful when comparing results or debugging.
    model = Column(String(80), nullable=False, default="")

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    # One-way relationships, so resume.py and job.py (owned by other
    # features) don't need to change.
    resume = relationship("Resume")
    job = relationship("Job")
