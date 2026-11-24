"""
Owner: AI Job Study Partner

A job seeker's conversation with the AI study partner about one job posting.
One chat per (job seeker, job posting); its messages are stored in order.

Stored on the server (not only in the browser) so that:
  - the conversation is still there after a refresh or on another device;
  - the server decides what history is sent to the AI, so a user can't
    slip in fake "AI" messages;
  - only the latest messages are sent to the AI, keeping requests small.

New tables, so Base.metadata.create_all() in app.py creates them on startup.
"""

import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class StudyChat(Base):
    __tablename__ = "study_chats"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_study_chat_user_job"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # The chat is about this posting, so it goes away with it.
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    # Oldest first. Deleting a chat deletes its messages (in Python and in
    # the database), which is how "start over" works.
    messages = relationship(
        "StudyChatMessage",
        order_by="StudyChatMessage.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class StudyChatMessage(Base):
    __tablename__ = "study_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("study_chats.id", ondelete="CASCADE"), nullable=False, index=True)

    role = Column(String(20), nullable=False)  # "user" or "assistant"
    text = Column(Text, nullable=False)

    # Only on the AI's messages: clickable follow-ups, and the Gemini model
    # that wrote it. Empty / "" on the user's messages.
    suggested_questions = Column(JSON, nullable=False, default=list)
    model = Column(String(80), nullable=False, default="")

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
