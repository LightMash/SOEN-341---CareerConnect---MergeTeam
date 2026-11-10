"""
Application status updates and history.
Endpoints:
  GET   /api/jobs/{job_id}/applications
  PATCH /api/applications/{id}/status
  GET   /api/applications/{id}/history
"""

import pytest

from database import SessionLocal
from models import Job

PDF_BYTES = b"%PDF-1.4 fake resume content"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter", full_name="Rita Recruiter")


@pytest.fixture
def job_id(recruiter) -> int:
    """An open job posted by `recruiter`."""
    db = SessionLocal()
    try:
        job = Job(recruiter_id=recruiter.id, title="Junior Developer", company="Acme")
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


@pytest.fixture
def application_id(client, user, job_id) -> int:
    """`user` (a job seeker) has applied to `job_id` with their primary resume."""
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")},
        headers=user.headers,
    )
    assert upload.status_code == 200, upload.text
    response = client.post("/api/applications", json={"job_id": job_id}, headers=user.headers)
    assert response.status_code == 201, response.text
    return response.json()["application"]["id"]


def _set_status(client, account, application_id, status):
    return client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": status},
        headers=account.headers,
    )


def _history(client, account, application_id):
    return client.get(f"/api/applications/{application_id}/history", headers=account.headers)


# ----------------------------------------------------------------------------
# Updating the status
# ----------------------------------------------------------------------------
def test_recruiter_updates_status(client, recruiter, user, application_id):
    response = _set_status(client, recruiter, application_id, "Interview")

    assert response.status_code == 200
    assert response.json()["status"] == "Interview"

    # The job seeker sees the new status in their own list.
    [mine] = client.get("/api/applications/mine", headers=user.headers).json()
    assert mine["status"] == "Interview"


@pytest.mark.parametrize("status", ["Under Review", "Interview", "Offered", "Rejected"])
def test_every_status_can_be_set(client, recruiter, application_id, status):
    assert _set_status(client, recruiter, application_id, status).status_code == 200


def test_unknown_status_rejected(client, recruiter, application_id):
    assert _set_status(client, recruiter, application_id, "Hired").status_code == 422


def test_same_status_rejected(client, recruiter, application_id):
    response = _set_status(client, recruiter, application_id, "Applied")
    assert response.status_code == 400


def test_applicant_cannot_change_own_status(client, user, application_id):
    response = _set_status(client, user, application_id, "Offered")
    assert response.status_code == 403


def test_other_recruiter_cannot_change_status(client, make_user, application_id):
    other_recruiter = make_user(role="recruiter")
    response = _set_status(client, other_recruiter, application_id, "Rejected")
    assert response.status_code == 403


def test_status_update_requires_login(client, application_id):
    response = client.patch(f"/api/applications/{application_id}/status", json={"status": "Interview"})
    assert response.status_code == 401


def test_status_update_unknown_application(client, recruiter):
    assert _set_status(client, recruiter, 999_999_999, "Interview").status_code == 404


# ----------------------------------------------------------------------------
# Status history
# ----------------------------------------------------------------------------
def test_new_application_has_one_history_entry(client, user, application_id):
    response = _history(client, user, application_id)

    assert response.status_code == 200
    [entry] = response.json()
    assert entry["old_status"] is None
    assert entry["new_status"] == "Applied"
    assert entry["changed_by"] == user.id
    assert entry["changed_at"]


def test_each_change_is_recorded_in_order(client, recruiter, user, application_id):
    _set_status(client, recruiter, application_id, "Under Review")
    _set_status(client, recruiter, application_id, "Interview")

    history = _history(client, user, application_id).json()

    assert [(h["old_status"], h["new_status"]) for h in history] == [
        (None, "Applied"),
        ("Applied", "Under Review"),
        ("Under Review", "Interview"),
    ]
    assert history[1]["changed_by"] == recruiter.id
    # Timestamps never go backwards.
    times = [h["changed_at"] for h in history]
    assert times == sorted(times)


def test_rejected_update_adds_no_history(client, recruiter, user, application_id):
    _set_status(client, user, application_id, "Offered")  # 403
    _set_status(client, recruiter, application_id, "Applied")  # 400 (same status)

    assert len(_history(client, user, application_id).json()) == 1


def test_recruiter_can_view_history(client, recruiter, application_id):
    assert _history(client, recruiter, application_id).status_code == 200


def test_strangers_cannot_view_history(client, make_user, application_id):
    assert _history(client, make_user(), application_id).status_code == 403
    assert _history(client, make_user(role="recruiter"), application_id).status_code == 403


# ----------------------------------------------------------------------------
# Applicants for one posting
# ----------------------------------------------------------------------------
def test_recruiter_lists_applicants(client, recruiter, user, job_id, application_id):
    response = client.get(f"/api/jobs/{job_id}/applications", headers=recruiter.headers)

    assert response.status_code == 200
    [applicant] = response.json()
    assert applicant["id"] == application_id
    assert applicant["applicant_id"] == user.id
    assert applicant["applicant_name"] == "Test User"
    assert applicant["applicant_email"] == user.email
    assert applicant["status"] == "Applied"
    assert applicant["resume_filename"] == "cv.pdf"


def test_applicant_list_empty_for_new_job(client, recruiter, job_id):
    response = client.get(f"/api/jobs/{job_id}/applications", headers=recruiter.headers)
    assert response.status_code == 200
    assert response.json() == []


def test_other_recruiter_cannot_list_applicants(client, make_user, job_id):
    other_recruiter = make_user(role="recruiter")
    response = client.get(f"/api/jobs/{job_id}/applications", headers=other_recruiter.headers)
    assert response.status_code == 403


def test_job_seeker_cannot_list_applicants(client, user, job_id):
    response = client.get(f"/api/jobs/{job_id}/applications", headers=user.headers)
    assert response.status_code == 403


def test_applicants_for_unknown_job(client, recruiter):
    response = client.get("/api/jobs/999999999/applications", headers=recruiter.headers)
    assert response.status_code == 404
