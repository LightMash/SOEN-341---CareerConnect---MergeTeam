"""
Owner: AI Resume Feedback

Two kinds of shapes live here:

1. What GEMINI must return (AISuggestion, AIFeedback). These are sent to
   Gemini as a JSON Schema (see services/ai_client.py), so the Field
   descriptions are instructions the model actually reads. Change them
   carefully: they affect the AI's answers.

2. What OUR API sends and receives (FeedbackRequest, SuggestionOut,
   ResumeFeedbackOut), like every other file in this folder.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Kept short on purpose: every extra enum value makes the schema bigger, and
# the frontend shows one label/colour per category.
SuggestionCategory = Literal["impact", "clarity", "skills", "grammar", "formatting", "content"]
Priority = Literal["high", "medium", "low"]


# -----------------------------------------------------------------------------
# 1. Shapes Gemini must answer with
# -----------------------------------------------------------------------------
class AISuggestion(BaseModel):
    section: str = Field(description="Resume section this applies to, e.g. 'Experience' or 'Skills'.")
    category: SuggestionCategory = Field(description="The kind of improvement.")
    priority: Priority = Field(description="How much this change would improve the resume.")
    original: str = Field(
        description=(
            "One COMPLETE bullet or line copied EXACTLY, character for character, from the resume. "
            "Use an empty string only when suggesting something new to add."
        )
    )
    suggested: str = Field(description="The improved text that would replace `original`.")
    reason: str = Field(description="One or two sentences explaining why this is better.")


class AIFeedback(BaseModel):
    overall_score: int = Field(ge=0, le=100, description="Overall resume quality from 0 to 100.")
    summary: str = Field(description="Two or three sentences summarising the resume's quality.")
    strengths: list[str] = Field(description="Two to four things the resume already does well.")
    suggestions: list[AISuggestion] = Field(
        description="Three to eight concrete improvements, most impactful first."
    )


# -----------------------------------------------------------------------------
# 2. Our API's request / response shapes
# -----------------------------------------------------------------------------
class FeedbackRequest(BaseModel):
    """Optional body of POST /api/resume/{id}/feedback."""

    model_config = ConfigDict(extra="forbid")

    # When given, the feedback is tailored to this job posting.
    job_id: int | None = None


class SuggestionOut(AISuggestion):
    # Position in the list. Lets the frontend say "accept suggestion 2"
    # without the suggestions needing their own database table.
    id: int
    # True when `original` really appears in the resume text, so the change
    # can be applied automatically later. False for additions, or when the
    # AI paraphrased instead of copying the text exactly.
    can_apply: bool


class ResumeFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resume_id: int
    job_id: int | None
    overall_score: int
    summary: str
    strengths: list[str]
    suggestions: list[SuggestionOut]
    model: str
    created_at: datetime.datetime
    # True when the resume file was replaced after this feedback was made,
    # so the UI can suggest asking for a new review.
    is_outdated: bool
