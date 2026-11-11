"""
Tests for AI Resume Feedback
Endpoints: POST/GET /api/resume/{id}/feedback
Plus the pure helpers in services/resume_feedback.py.

Gemini is never called: the `fake_ai` fixture replaces generate_json() with
a function that records what it was asked and returns a canned answer (or
raises), so these tests are free, fast and work in CI without an API key.
"""

import io

import pytest
from docx import Document

from schemas.resume_feedback import AIFeedback
from services import resume_feedback as feedback_service
from services.ai_client import AIServiceError

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

RESUME_LINES = [
    "Jane Doe",
    "Software Developer Intern at Acme",
    "Worked on the backend",
    "Skills: Python, SQL",
]

# What the fake Gemini answers with. The first suggestion quotes the resume
# exactly; the second one paraphrases it, so it should NOT be applicable.
CANNED_ANSWER = {
    "overall_score": 64,
    "summary": "A clear start that needs measurable impact.",
    "strengths": ["Relevant internship", "Concise"],
    "suggestions": [
        {
            "section": "Experience",
            "category": "impact",
            "priority": "high",
            "original": "Worked on the backend",
            "suggested": "Built 5 REST endpoints in FastAPI serving [N users]",
            "reason": "Action verb plus a measurable result.",
        },
        {
            "section": "Skills",
            "category": "skills",
            "priority": "medium",
            "original": "Skills: Python and SQL",  # not the resume's exact wording
            "suggested": "Skills: Python, SQL, FastAPI, Git",
            "reason": "Lists the tools used in the internship.",
        },
    ],
}


# -----------------------------------------------------------------------------
# Helpers and fixtures
# -----------------------------------------------------------------------------
def _docx_bytes(lines) -> bytes:
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _upload_resume(client, account, lines=RESUME_LINES) -> dict:
    response = client.post(
        "/api/resume/upload",
        files={"file": ("cv.docx", _docx_bytes(lines), DOCX)},
        headers=account.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["resume"]


def _ask(client, account, resume_id, json=None):
    return client.post(f"/api/resume/{resume_id}/feedback", json=json, headers=account.headers)


@pytest.fixture
def fake_ai(monkeypatch):
    """
    Replaces Gemini. Use `fake_ai.calls` to see the prompts it received, or
    set `fake_ai.error` to make the next call fail.
    """

    class FakeAI:
        def __init__(self):
            self.calls = []
            self.error = None

        def __call__(self, prompt, schema, system_instruction=None):
            self.calls.append({"prompt": prompt, "system_instruction": system_instruction})
            if self.error:
                raise self.error
            return schema.model_validate(CANNED_ANSWER)

    fake = FakeAI()
    # Patch the name where it is USED (inside the feedback service), not
    # where it is defined, because the service did `from ... import generate_json`.
    monkeypatch.setattr(feedback_service, "generate_json", fake)
    return fake


# -----------------------------------------------------------------------------
# POST /api/resume/{id}/feedback
# -----------------------------------------------------------------------------
def test_feedback_is_generated_and_returned(client, user, fake_ai):
    resume = _upload_resume(client, user)

    response = _ask(client, user, resume["id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["resume_id"] == resume["id"]
    assert body["overall_score"] == 64
    assert body["strengths"] == ["Relevant internship", "Concise"]
    assert [s["id"] for s in body["suggestions"]] == [0, 1]
    assert body["job_id"] is None
    assert body["is_outdated"] is False


def test_resume_text_is_what_gets_sent_to_the_ai(client, user, fake_ai):
    resume = _upload_resume(client, user)

    _ask(client, user, resume["id"])

    prompt = fake_ai.calls[0]["prompt"]
    assert "Worked on the backend" in prompt
    assert "<<<RESUME>>>" in prompt
    assert fake_ai.calls[0]["system_instruction"] == feedback_service.SYSTEM_INSTRUCTION


def test_can_apply_is_true_only_for_exact_quotes(client, user, fake_ai):
    resume = _upload_resume(client, user)

    suggestions = _ask(client, user, resume["id"]).json()["suggestions"]

    assert suggestions[0]["can_apply"] is True   # quoted exactly
    assert suggestions[1]["can_apply"] is False  # paraphrased by the AI


def test_feedback_can_be_tailored_to_a_job(client, user, make_user, fake_ai):
    recruiter = make_user(role="recruiter")
    job = client.post(
        "/api/jobs",
        json={"title": "Backend Intern", "company": "Globex", "description": "Must know Docker."},
        headers=recruiter.headers,
    ).json()
    resume = _upload_resume(client, user)

    response = _ask(client, user, resume["id"], json={"job_id": job["id"]})

    assert response.status_code == 201
    assert response.json()["job_id"] == job["id"]
    prompt = fake_ai.calls[0]["prompt"]
    assert "Backend Intern" in prompt
    assert "Must know Docker." in prompt


def test_unknown_job_is_rejected_before_calling_ai(client, user, fake_ai):
    resume = _upload_resume(client, user)

    response = _ask(client, user, resume["id"], json={"job_id": 999_999})

    assert response.status_code == 404
    assert fake_ai.calls == []


def test_unreadable_resume_gives_422_without_calling_ai(client, user, fake_ai):
    resume = _upload_resume(client, user, lines=["", "   "])  # no real text

    response = _ask(client, user, resume["id"])

    assert response.status_code == 422
    assert "text" in response.json()["detail"]
    assert fake_ai.calls == []


def test_ai_failure_gives_503_and_saves_nothing(client, user, fake_ai):
    resume = _upload_resume(client, user)
    fake_ai.error = AIServiceError("The AI service is busy right now. Please try again in a minute.")

    response = _ask(client, user, resume["id"])

    assert response.status_code == 503
    assert "busy" in response.json()["detail"]
    assert client.get(f"/api/resume/{resume['id']}/feedback", headers=user.headers).status_code == 404


def test_requires_login(client, user, fake_ai):
    resume = _upload_resume(client, user)

    response = client.post(f"/api/resume/{resume['id']}/feedback")

    assert response.status_code == 401
    assert fake_ai.calls == []


def test_cannot_request_feedback_on_someone_elses_resume(client, user, make_user, fake_ai):
    resume = _upload_resume(client, user)
    stranger = make_user()

    response = _ask(client, stranger, resume["id"])

    assert response.status_code == 403
    assert fake_ai.calls == []


def test_missing_resume_gives_404(client, user, fake_ai):
    assert _ask(client, user, 999_999).status_code == 404


def test_extra_fields_in_body_are_rejected(client, user, fake_ai):
    resume = _upload_resume(client, user)

    response = _ask(client, user, resume["id"], json={"job_id": None, "score": 100})

    assert response.status_code == 422


# -----------------------------------------------------------------------------
# GET /api/resume/{id}/feedback
# -----------------------------------------------------------------------------
def test_get_returns_latest_feedback_without_calling_ai(client, user, fake_ai):
    resume = _upload_resume(client, user)
    _ask(client, user, resume["id"])
    second = _ask(client, user, resume["id"]).json()
    calls_so_far = len(fake_ai.calls)

    response = client.get(f"/api/resume/{resume['id']}/feedback", headers=user.headers)

    assert response.status_code == 200
    assert response.json()["id"] == second["id"]
    assert len(fake_ai.calls) == calls_so_far  # served from the database


def test_get_without_any_feedback_gives_404(client, user):
    resume = _upload_resume(client, user)

    response = client.get(f"/api/resume/{resume['id']}/feedback", headers=user.headers)

    assert response.status_code == 404


def test_get_someone_elses_feedback_is_forbidden(client, user, make_user, fake_ai):
    resume = _upload_resume(client, user)
    _ask(client, user, resume["id"])
    stranger = make_user()

    response = client.get(f"/api/resume/{resume['id']}/feedback", headers=stranger.headers)

    assert response.status_code == 403


def test_feedback_is_outdated_after_resume_is_replaced(client, user, fake_ai):
    resume = _upload_resume(client, user)
    _ask(client, user, resume["id"])

    client.put(
        f"/api/resume/{resume['id']}",
        files={"file": ("cv2.docx", _docx_bytes(["A brand new resume"]), DOCX)},
        headers=user.headers,
    )
    response = client.get(f"/api/resume/{resume['id']}/feedback", headers=user.headers)

    assert response.json()["is_outdated"] is True


def test_deleting_resume_deletes_its_feedback(client, user, fake_ai):
    resume = _upload_resume(client, user)
    _ask(client, user, resume["id"])

    assert client.delete(f"/api/resume/{resume['id']}", headers=user.headers).status_code == 200
    # The resume is gone, so its feedback can't be reached (the database
    # removed the rows through ON DELETE CASCADE).
    assert client.get(f"/api/resume/{resume['id']}/feedback", headers=user.headers).status_code == 404


# -----------------------------------------------------------------------------
# Pure helpers (no HTTP)
# -----------------------------------------------------------------------------
def test_prompt_without_job_has_no_job_section():
    prompt = feedback_service.build_prompt("Jane Doe\nPython")

    assert "<<<JOB POSTING>>>" not in prompt
    assert "Jane Doe\nPython" in prompt


def test_can_apply_ignores_case_and_spacing():
    feedback = AIFeedback.model_validate(
        {**CANNED_ANSWER, "suggestions": [{**CANNED_ANSWER["suggestions"][0], "original": "worked  ON the\nbackend"}]}
    )

    [suggestion] = feedback_service.mark_applicable(feedback, "Jane\nWorked on the backend\n")

    assert suggestion["can_apply"] is True


def test_additions_are_not_applicable():
    feedback = AIFeedback.model_validate(
        {**CANNED_ANSWER, "suggestions": [{**CANNED_ANSWER["suggestions"][0], "original": ""}]}
    )

    [suggestion] = feedback_service.mark_applicable(feedback, "anything")

    assert suggestion["can_apply"] is False


def test_suggestions_are_capped():
    many = [CANNED_ANSWER["suggestions"][0]] * (feedback_service.MAX_SUGGESTIONS + 5)
    feedback = AIFeedback.model_validate({**CANNED_ANSWER, "suggestions": many})

    result = feedback_service.mark_applicable(feedback, "Worked on the backend")

    assert len(result) == feedback_service.MAX_SUGGESTIONS
