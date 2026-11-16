"""
Owner: AI Job Study Partner

The shape of every answer the study partner gives. It is sent to Gemini as
a JSON Schema (see generate_chat_with_model in services/ai_client.py), so the
Field descriptions are instructions the model actually reads. Change them
carefully: they affect the AI's answers.

The chat endpoint's own request and response shapes are at the bottom.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudyPartnerReply(BaseModel):
    reply: str = Field(
        description=(
            "Your answer to the job seeker's latest message, in plain text. Short paragraphs; "
            "use lines starting with '- ' for lists. No Markdown headings, bold or tables."
        )
    )
    suggested_questions: list[str] = Field(
        description=(
            "Two or three short follow-up messages the job seeker could send next, written in "
            "their voice (e.g. 'Quiz me on SQL joins'), each about this job posting. "
            "Each under 60 characters."
        )
    )


# -----------------------------------------------------------------------------
# The chat endpoint's request and response shapes
# -----------------------------------------------------------------------------
# Longest message a user can send. Enough for a detailed question or a quiz
# answer, short enough to keep requests (and free-tier quota) reasonable.
MAX_MESSAGE_LENGTH = 1000


class StudyMessageIn(BaseModel):
    """Body of POST /api/jobs/{job_id}/study-chat/messages."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message can't be empty.")
        return value


class StudyMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    text: str
    suggested_questions: list[str]  # empty on the user's messages
    created_at: datetime.datetime


class StudyChatOut(BaseModel):
    job_id: int
    messages: list[StudyMessageOut]  # oldest first; empty for a new chat
    # Questions to show before the first message, so the user knows what
    # to ask. Empty once the conversation has started.
    starter_questions: list[str]


class CertificationOut(BaseModel):
    """One certification suggested for a job (see services/certifications.py)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    issuer: str
    level: str
    topic: str
    summary: str
    url: str


class CertificationsOut(BaseModel):
    job_id: int
    certifications: list[CertificationOut]  # empty when nothing in the catalog fits
