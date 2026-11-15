"""
Tests for the AI Job Study Partner's output format: schemas/study_partner.py.
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


# =============================================================================
# The chat endpoints: GET / POST / DELETE /api/jobs/{job_id}/study-chat
# Gemini is never called: `fake_ai` replaces it and records what it was sent.
# =============================================================================
from models import StudyChat, StudyChatMessage  # noqa: E402
from services import study_partner as study_service  # noqa: E402
from services.ai_client import AIServiceError  # noqa: E402

FAKE_MODEL = "fake-gemini-model"


@pytest.fixture
def fake_ai(monkeypatch):
    """
    Replaces Gemini. `fake_ai.calls` holds what each request sent (the
    conversation and the instructions); set `fake_ai.error` to make it fail.
    Each answer says which message number it is: "Answer 1", "Answer 2"...
    """

    class FakeAI:
        def __init__(self):
            self.calls = []
            self.error = None
            self.suggestions = ["Quiz me on SQL", "Explain REST"]

        def __call__(self, messages, schema, system_instruction=None):
            self.calls.append({"messages": messages, "system_instruction": system_instruction})
            if self.error:
                raise self.error
            reply = schema(reply=f"  Answer {len(self.calls)}  ", suggested_questions=list(self.suggestions))
            return reply, FAKE_MODEL

    fake = FakeAI()
    # Patched where it is USED: the service did `from ... import generate_chat_with_model`.
    monkeypatch.setattr(study_service, "generate_chat_with_model", fake)
    return fake


@pytest.fixture
def job(client, make_user) -> dict:
    recruiter = make_user(role="recruiter")
    response = client.post(
        "/api/jobs",
        json={"title": "Backend Intern", "company": "Globex", "description": "FastAPI and PostgreSQL."},
        headers=recruiter.headers,
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def _url(job_id: int) -> str:
    return f"/api/jobs/{job_id}/study-chat"


def _send(client, account, job_id, text):
    return client.post(f"{_url(job_id)}/messages", json={"text": text}, headers=account.headers)


# -----------------------------------------------------------------------------
# GET
# -----------------------------------------------------------------------------
def test_new_chat_is_empty_with_starter_questions(client, user, job):
    response = client.get(_url(job["id"]), headers=user.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["messages"] == []
    assert body["starter_questions"] == study_service.STARTER_QUESTIONS


def test_get_never_calls_the_ai(client, user, job, fake_ai):
    _send(client, user, job["id"], "Hi")
    calls = len(fake_ai.calls)

    client.get(_url(job["id"]), headers=user.headers)

    assert len(fake_ai.calls) == calls


# -----------------------------------------------------------------------------
# POST: sending a message
# -----------------------------------------------------------------------------
def test_message_and_reply_are_returned_and_saved(client, user, job, fake_ai):
    response = _send(client, user, job["id"], "  What should I study?  ")

    assert response.status_code == 201, response.text
    messages = response.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["text"] == "What should I study?"  # trimmed
    assert messages[1]["text"] == "Answer 1"  # trimmed
    assert messages[1]["suggested_questions"] == ["Quiz me on SQL", "Explain REST"]
    assert response.json()["starter_questions"] == []

    reloaded = client.get(_url(job["id"]), headers=user.headers).json()
    assert reloaded["messages"] == messages


def test_ai_receives_the_job_posting_in_its_instructions(client, user, job, fake_ai):
    _send(client, user, job["id"], "Hi")

    instructions = fake_ai.calls[0]["system_instruction"]
    assert "Backend Intern" in instructions
    assert "FastAPI and PostgreSQL." in instructions
    assert "<<<JOB POSTING>>>" in instructions


def test_ai_receives_the_whole_conversation(client, user, job, fake_ai):
    _send(client, user, job["id"], "First question")
    _send(client, user, job["id"], "Second question")

    sent = fake_ai.calls[1]["messages"]
    assert [(m.role, m.text) for m in sent] == [
        ("user", "First question"),
        ("model", "Answer 1"),
        ("user", "Second question"),
    ]


def test_only_recent_history_is_sent(client, user, job, fake_ai, monkeypatch):
    monkeypatch.setattr(study_service, "MAX_HISTORY_MESSAGES", 2)
    for text in ["one", "two", "three"]:
        _send(client, user, job["id"], text)

    sent = fake_ai.calls[2]["messages"]
    assert [m.text for m in sent] == ["two", "Answer 2", "three"]
    # ...but everything stays saved and visible to the user.
    assert len(client.get(_url(job["id"]), headers=user.headers).json()["messages"]) == 6


def test_ai_failure_gives_503_and_saves_nothing(client, user, job, fake_ai):
    fake_ai.error = AIServiceError("The AI service is busy right now. Please try again in a minute.")

    response = _send(client, user, job["id"], "Hi")

    assert response.status_code == 503
    assert "busy" in response.json()["detail"]
    assert client.get(_url(job["id"]), headers=user.headers).json()["messages"] == []


def test_suggested_questions_are_cleaned_up(client, user, job, fake_ai):
    fake_ai.suggestions = ["  Quiz me  ", "", "quiz me", "Mock interview", "Study plan", "One too many"]

    reply = _send(client, user, job["id"], "Hi").json()["messages"][1]

    assert reply["suggested_questions"] == ["Quiz me", "Mock interview", "Study plan"]


def test_each_job_seeker_has_their_own_chat(client, user, make_user, job, fake_ai):
    other = make_user()
    _send(client, user, job["id"], "Mine")

    response = client.get(_url(job["id"]), headers=other.headers)

    assert response.json()["messages"] == []


def test_each_job_posting_has_its_own_chat(client, user, make_user, job, fake_ai):
    recruiter = make_user(role="recruiter")
    other_job = client.post(
        "/api/jobs", json={"title": "Data Intern", "company": "Initech"}, headers=recruiter.headers
    ).json()
    _send(client, user, job["id"], "About the backend job")

    assert client.get(_url(other_job["id"]), headers=user.headers).json()["messages"] == []


# -----------------------------------------------------------------------------
# POST: requests rejected before calling the AI
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["", "     ", "x" * 1001])
def test_empty_or_too_long_message_is_rejected(client, user, job, fake_ai, text):
    response = _send(client, user, job["id"], text)

    assert response.status_code == 422
    assert fake_ai.calls == []


def test_unknown_job_gives_404(client, user, fake_ai):
    assert _send(client, user, 999_999, "Hi").status_code == 404
    assert fake_ai.calls == []


def test_recruiters_cannot_use_the_study_partner(client, make_user, job, fake_ai):
    recruiter = make_user(role="recruiter")

    assert _send(client, recruiter, job["id"], "Hi").status_code == 403
    assert client.get(_url(job["id"]), headers=recruiter.headers).status_code == 403
    assert fake_ai.calls == []


def test_requires_login(client, job, fake_ai):
    assert client.post(f"{_url(job['id'])}/messages", json={"text": "Hi"}).status_code == 401
    assert client.get(_url(job["id"])).status_code == 401


# -----------------------------------------------------------------------------
# DELETE: start over
# -----------------------------------------------------------------------------
def test_delete_starts_over(client, user, job, fake_ai):
    _send(client, user, job["id"], "Hi")

    assert client.delete(_url(job["id"]), headers=user.headers).status_code == 204
    body = client.get(_url(job["id"]), headers=user.headers).json()
    assert body["messages"] == []
    assert body["starter_questions"] == study_service.STARTER_QUESTIONS


def test_delete_without_a_chat_is_fine(client, user, job):
    assert client.delete(_url(job["id"]), headers=user.headers).status_code == 204


def test_deleted_chat_leaves_no_messages_behind(client, user, job, fake_ai):
    from database import SessionLocal

    _send(client, user, job["id"], "Hi")
    db = SessionLocal()
    try:
        # The test database isn't emptied between tests, so look only at this chat.
        chat_id = db.query(StudyChat.id).filter(StudyChat.job_id == job["id"]).scalar()

        client.delete(_url(job["id"]), headers=user.headers)

        assert db.query(StudyChat).filter(StudyChat.id == chat_id).count() == 0
        assert db.query(StudyChatMessage).filter(StudyChatMessage.chat_id == chat_id).count() == 0
    finally:
        db.close()


def test_deleting_the_job_deletes_its_chats(client, user, make_user, fake_ai):
    from database import SessionLocal

    recruiter = make_user(role="recruiter")
    job = client.post("/api/jobs", json={"title": "Temp", "company": "X"}, headers=recruiter.headers).json()
    _send(client, user, job["id"], "Hi")

    assert client.delete(f"/api/jobs/{job['id']}", headers=recruiter.headers).status_code in (200, 204)

    db = SessionLocal()
    try:
        assert db.query(StudyChat).filter(StudyChat.job_id == job["id"]).count() == 0
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Pure helpers (no HTTP)
# -----------------------------------------------------------------------------
def test_history_maps_assistant_to_gemini_model_role():
    previous = [StudyChatMessage(role="user", text="Q"), StudyChatMessage(role="assistant", text="A")]

    history = study_service.build_history(previous, "Next")

    assert [(m.role, m.text) for m in history] == [("user", "Q"), ("model", "A"), ("user", "Next")]


def test_max_history_is_even_so_history_starts_with_the_user():
    assert study_service.MAX_HISTORY_MESSAGES % 2 == 0


# =============================================================================
# Useful certifications: GET /api/jobs/{job_id}/certifications (no AI involved)
# =============================================================================
from services import certifications as certification_service  # noqa: E402


def _post_job(client, recruiter, title, description, category="Software"):
    response = client.post(
        "/api/jobs",
        json={"title": title, "company": "Globex", "description": description, "category": category},
        headers=recruiter.headers,
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def _cert_url(job_id: int) -> str:
    return f"/api/jobs/{job_id}/certifications"


def test_certifications_match_the_posting(client, user, make_user):
    recruiter = make_user(role="recruiter")
    posting = _post_job(client, recruiter, "Backend Dev", "Python, FastAPI, Docker and AWS experience.")

    response = client.get(_cert_url(posting["id"]), headers=user.headers)

    assert response.status_code == 200, response.text
    ids = [c["id"] for c in response.json()["certifications"]]
    assert {"pcep", "aws-cloud-practitioner", "ckad"} <= set(ids)
    assert "azure-fundamentals" not in ids


def test_certification_with_most_keyword_hits_comes_first(client, user, make_user):
    recruiter = make_user(role="recruiter")
    posting = _post_job(client, recruiter, "Platform Dev", "Kubernetes, Docker and containers. Some Python.")

    ids = [c["id"] for c in client.get(_cert_url(posting["id"]), headers=user.headers).json()["certifications"]]

    assert ids[0] == "ckad"


def test_no_certifications_when_nothing_fits(client, user, make_user):
    recruiter = make_user(role="recruiter")
    posting = _post_job(client, recruiter, "Barista", "Make coffee and greet customers.", category="Food")

    body = client.get(_cert_url(posting["id"]), headers=user.headers).json()

    assert body["certifications"] == []


def test_keywords_match_whole_words_only(client, user, make_user):
    recruiter = make_user(role="recruiter")
    posting = _post_job(client, recruiter, "Digital Marketer", "Digital campaigns and gitless paperwork.", category="Marketing")

    assert client.get(_cert_url(posting["id"]), headers=user.headers).json()["certifications"] == []


def test_every_catalog_link_is_an_official_https_page():
    assert certification_service.CATALOG
    for cert in certification_service.CATALOG:
        assert cert.url.startswith("https://"), cert.id
        assert cert.keywords and all(k == k.lower() for k in cert.keywords), cert.id
    assert len({c.id for c in certification_service.CATALOG}) == len(certification_service.CATALOG)


def test_certifications_never_call_the_ai(client, user, make_user, fake_ai):
    recruiter = make_user(role="recruiter")
    posting = _post_job(client, recruiter, "Dev", "Python")

    client.get(_cert_url(posting["id"]), headers=user.headers)

    assert fake_ai.calls == []


def test_certifications_unknown_job_is_404(client, user):
    assert client.get(_cert_url(999999), headers=user.headers).status_code == 404


def test_certifications_forbidden_for_recruiters(client, make_user):
    recruiter = make_user(role="recruiter")
    posting = _post_job(client, recruiter, "Dev", "Python")

    assert client.get(_cert_url(posting["id"]), headers=recruiter.headers).status_code == 403


def test_certifications_require_login(client, make_user):
    recruiter = make_user(role="recruiter")
    posting = _post_job(client, recruiter, "Dev", "Python")

    assert client.get(_cert_url(posting["id"])).status_code in (401, 403)
