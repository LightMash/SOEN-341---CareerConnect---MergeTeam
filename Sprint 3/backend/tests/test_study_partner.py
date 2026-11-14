"""
Tests for the AI Job Study Partner's output format:
schemas/study_partner.py
"""

import pytest
from pydantic import ValidationError

from schemas.study_partner import StudyPartnerReply


def test_valid_reply_is_parsed():
    reply = StudyPartnerReply.model_validate_json(
        '{"reply": "A JOIN combines rows from two tables.", '
        '"suggested_questions": ["Quiz me on joins", "What is an index?"]}'
    )

    assert reply.reply.startswith("A JOIN")
    assert len(reply.suggested_questions) == 2


def test_reply_without_suggested_questions_is_rejected():
    with pytest.raises(ValidationError):
        StudyPartnerReply.model_validate_json('{"reply": "Hello"}')


def test_schema_sent_to_gemini_describes_both_fields():
    # These descriptions are what Gemini reads, so they must not go missing.
    properties = StudyPartnerReply.model_json_schema()["properties"]

    assert set(properties) == {"reply", "suggested_questions"}
    assert "plain text" in properties["reply"]["description"]
    assert "follow-up" in properties["suggested_questions"]["description"]
