"""
Owner: AI Job Study Partner

The shape of every answer the study partner gives. It is sent to Gemini as
a JSON Schema (see generate_chat_with_model in services/ai_client.py), so the
Field descriptions are instructions the model actually reads. Change them
carefully: they affect the AI's answers.
"""

from pydantic import BaseModel, Field


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
