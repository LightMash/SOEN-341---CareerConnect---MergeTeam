"""
The `user` fixture is a logged-in job seeker; `make_user()` creates extra users.
Jobs are inserted straight into the database (no "create job" endpoint exists
yet - that belongs to the recruiter dashboard feature).
"""

import pytest

from database import SessionLocal
from models import Job

PDF_BYTES = b"%PDF-1.4 fake resume content"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@pytest.fixture
def make_job(make_user):
    """Factory that inserts a job posting owned by a fresh recruiter."""

    def _make(title="Junior Developer", company="Acme", is_open=True) -> int:
        recruiter = make_user(role="recruiter")
        db = SessionLocal()
        try:
            job = Job(recruiter_id=recruiter.id, title=title, company=company, is_open=is_open)
            db.add(job)
            db.commit()
            return job.id
        finally:
            db.close()

    return _make


@pytest.fixture
def job_id(make_job) -> int:
    """One open job, for tests that only need a single posting."""
    return make_job()


def _upload_resume(client, user, name="cv.pdf") -> dict:
    response = client.post(
        "/api/resume/upload",
        files={"file": (name, PDF_BYTES, "application/pdf")},
        headers=user.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["resume"]


def _apply(client, user, job_id, resume_id=None):
    body = {"job_id": job_id}
    if resume_id is not None:
        body["resume_id"] = resume_id
    return client.post("/api/applications", json=body, headers=user.headers)


# ----------------------------------------------------------------------------
# Successful submission
# ----------------------------------------------------------------------------
def test_apply_with_primary_resume(client, user, job_id):
    resume = _upload_resume(client, user)  # first upload becomes primary

    response = _apply(client, user, job_id)

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Application submitted successfully."
    application = body["application"]
    assert application["job_id"] == job_id
    assert application["job_title"] == "Junior Developer"
    assert application["company"] == "Acme"
    assert application["resume_id"] == resume["id"]
    assert application["status"] == "Applied"


def test_apply_with_selected_resume(client, user, job_id):
    _upload_resume(client, user, name="primary.pdf")
    other = _upload_resume(client, user, name="tailored.pdf")  # not primary

    response = _apply(client, user, job_id, resume_id=other["id"])

    assert response.status_code == 201
    assert response.json()["application"]["resume_filename"] == "tailored.pdf"


def test_client_cannot_choose_status(client, user, job_id):
    _upload_resume(client, user)
    response = client.post(
        "/api/applications",
        json={"job_id": job_id, "status": "Offered"},
        headers=user.headers,
    )
    assert response.status_code == 422  # unknown field rejected


# ----------------------------------------------------------------------------
# Duplicate prevention
# ----------------------------------------------------------------------------
def test_cannot_apply_twice_to_same_job(client, user, job_id):
    _upload_resume(client, user)
    assert _apply(client, user, job_id).status_code == 201

    response = _apply(client, user, job_id)

    assert response.status_code == 409
    assert response.json()["detail"] == "You have already applied to this job."
    assert len(client.get("/api/applications/mine", headers=user.headers).json()) == 1


def test_can_apply_to_different_jobs(client, user, make_job):
    _upload_resume(client, user)
    assert _apply(client, user, make_job()).status_code == 201
    assert _apply(client, user, make_job()).status_code == 201


def test_two_users_can_apply_to_same_job(client, make_user, job_id):
    for _ in range(2):
        seeker = make_user()
        _upload_resume(client, seeker)
        assert _apply(client, seeker, job_id).status_code == 201


# ----------------------------------------------------------------------------
# Rejected submissions
# ----------------------------------------------------------------------------
def test_must_be_logged_in(client, job_id):
    response = client.post("/api/applications", json={"job_id": job_id})
    assert response.status_code == 401


def test_recruiter_cannot_apply(client, make_user, job_id):
    recruiter = make_user(role="recruiter")
    assert _apply(client, recruiter, job_id).status_code == 403


def test_job_must_exist(client, user):
    _upload_resume(client, user)
    assert _apply(client, user, 999_999_999).status_code == 404


def test_closed_job_rejects_applications(client, user, make_job):
    _upload_resume(client, user)
    response = _apply(client, user, make_job(is_open=False))
    assert response.status_code == 400


def test_needs_a_resume(client, user, job_id):
    response = _apply(client, user, job_id)
    assert response.status_code == 400
    assert response.json()["detail"] == "Upload a resume before applying to jobs."


def test_cannot_apply_with_someone_elses_resume(client, user, make_user, job_id):
    _upload_resume(client, user)
    stranger = make_user()
    stranger_resume = _upload_resume(client, stranger)

    response = _apply(client, user, job_id, resume_id=stranger_resume["id"])

    assert response.status_code == 403


def test_selected_resume_must_exist(client, user, job_id):
    _upload_resume(client, user)
    assert _apply(client, user, job_id, resume_id=999_999_999).status_code == 404


# ----------------------------------------------------------------------------
# GET /api/applications/mine
# ----------------------------------------------------------------------------
def test_list_my_applications_newest_first(client, user, make_job):
    _upload_resume(client, user)
    _apply(client, user, make_job(title="First"))
    _apply(client, user, make_job(title="Second"))

    response = client.get("/api/applications/mine", headers=user.headers)

    assert response.status_code == 200
    assert [a["job_title"] for a in response.json()] == ["Second", "First"]


def test_list_only_shows_my_applications(client, user, make_user, job_id):
    other = make_user()
    _upload_resume(client, other)
    _apply(client, other, job_id)

    response = client.get("/api/applications/mine", headers=user.headers)

    assert response.status_code == 200
    assert response.json() == []


def test_application_survives_resume_deletion(client, user, job_id):
    resume = _upload_resume(client, user)
    _apply(client, user, job_id)

    delete = client.delete(f"/api/resume/{resume['id']}", headers=user.headers)
    assert delete.status_code == 200

    [application] = client.get("/api/applications/mine", headers=user.headers).json()
    assert application["resume_id"] is None
    assert application["resume_filename"] is None


def test_recruiter_cannot_list_mine(client, make_user):
    recruiter = make_user(role="recruiter")
    response = client.get("/api/applications/mine", headers=recruiter.headers)
    assert response.status_code == 403
