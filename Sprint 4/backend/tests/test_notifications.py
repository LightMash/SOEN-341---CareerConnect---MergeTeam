"""
US-09: In-app notifications.

Endpoints covered:
  GET    /api/notifications            GET  /api/notifications/unread-count
  POST   /api/notifications/read-all   POST /api/notifications/{id}/read
  DELETE /api/notifications/{id}
plus the events raised by POST /api/applications and
PATCH /api/applications/{id}/status.

Test groups (the "Acceptance" ones are written as Given / When / Then):
  1. Acceptance: recruiter / job seeker are notified
  2. Reading and managing notifications (+ privacy between users)
  3. Model constraint
"""

import pytest
from sqlalchemy.exc import DBAPIError

from database import SessionLocal
from models import Job, Notification

PDF_BYTES = b"%PDF-1.4 fake resume content"


# ----------------------------------------------------------------------------
# Helpers and fixtures
# ----------------------------------------------------------------------------
@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter", full_name="Rita Recruiter")


@pytest.fixture
def seeker(client, make_user):
    """A job seeker who already has a (primary) resume, so they can apply."""
    account = make_user(full_name="Sam Seeker")
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")},
        headers=account.headers,
    )
    assert upload.status_code == 200, upload.text
    return account


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
def application_id(client, seeker, job_id) -> int:
    """`seeker` has applied to `job_id`."""
    return _apply(client, seeker, job_id)


def _apply(client, account, job_id) -> int:
    response = client.post("/api/applications", json={"job_id": job_id}, headers=account.headers)
    assert response.status_code == 201, response.text
    return response.json()["application"]["id"]


def _set_status(client, account, application_id, status):
    return client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": status},
        headers=account.headers,
    )


def _notifications(client, account, **params) -> list[dict]:
    response = client.get("/api/notifications", params=params, headers=account.headers)
    assert response.status_code == 200, response.text
    return response.json()


# ============================================================================
# 1. ACCEPTANCE: who gets notified, and when
# ============================================================================
def test_recruiter_notified_when_job_seeker_applies(client, recruiter, seeker, job_id):
    """
    Given a recruiter with an open posting
    When a job seeker applies to it
    Then the recruiter gets a "new_application" notification naming the
         applicant and the job, and it is unread.
    """
    application_id = _apply(client, seeker, job_id)

    [note] = _notifications(client, recruiter)
    assert note["type"] == "new_application"
    assert note["is_read"] is False
    assert note["application_id"] == application_id
    assert "Sam Seeker" in note["message"]
    assert "Junior Developer" in note["message"]


def test_applicant_is_not_notified_about_their_own_application(client, seeker, application_id):
    assert _notifications(client, seeker) == []


def test_duplicate_application_does_not_notify_twice(client, recruiter, seeker, job_id):
    _apply(client, seeker, job_id)
    duplicate = client.post("/api/applications", json={"job_id": job_id}, headers=seeker.headers)

    assert duplicate.status_code == 409
    assert len(_notifications(client, recruiter)) == 1


def test_job_seeker_notified_of_interview_invitation(client, recruiter, seeker, application_id):
    """
    Given a job seeker with a submitted application
    When the recruiter moves it to "Interview"
    Then the job seeker gets an "interview_invitation" notification.
    """
    assert _set_status(client, recruiter, application_id, "Interview").status_code == 200

    [note] = _notifications(client, seeker)
    assert note["type"] == "interview_invitation"
    assert note["application_id"] == application_id
    assert "Junior Developer" in note["message"]


@pytest.mark.parametrize("new_status", ["Under Review", "Offered", "Rejected"])
def test_job_seeker_notified_of_other_status_changes(client, recruiter, seeker, application_id, new_status):
    _set_status(client, recruiter, application_id, new_status)

    [note] = _notifications(client, seeker)
    assert note["type"] == "status_changed"
    assert new_status in note["message"]


def test_failed_status_update_creates_no_notification(client, recruiter, seeker, application_id):
    """Rejected requests (same status, invalid status, wrong user) must stay silent."""
    assert _set_status(client, recruiter, application_id, "Applied").status_code == 400
    assert _set_status(client, recruiter, application_id, "Hired").status_code == 422
    assert _set_status(client, seeker, application_id, "Offered").status_code == 403

    assert _notifications(client, seeker) == []


def test_notifications_are_newest_first(client, recruiter, seeker, application_id):
    _set_status(client, recruiter, application_id, "Under Review")
    _set_status(client, recruiter, application_id, "Interview")

    types = [n["type"] for n in _notifications(client, seeker)]
    assert types == ["interview_invitation", "status_changed"]


# ============================================================================
# 2. Reading and managing notifications
# ============================================================================
def test_notifications_require_login(client):
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401


def test_new_user_has_no_notifications(client, user):
    assert _notifications(client, user) == []
    assert client.get("/api/notifications/unread-count", headers=user.headers).json() == {"unread": 0}


def test_unread_count_mark_one_and_mark_all_read(client, recruiter, seeker, application_id):
    _set_status(client, recruiter, application_id, "Under Review")
    _set_status(client, recruiter, application_id, "Interview")
    count = lambda: client.get("/api/notifications/unread-count", headers=seeker.headers).json()["unread"]  # noqa: E731
    assert count() == 2

    newest = _notifications(client, seeker)[0]
    read = client.post(f"/api/notifications/{newest['id']}/read", headers=seeker.headers)
    assert read.status_code == 200
    assert read.json()["is_read"] is True
    assert count() == 1
    assert len(_notifications(client, seeker, unread_only="true")) == 1

    result = client.post("/api/notifications/read-all", headers=seeker.headers)
    assert result.json() == {"updated": 1}
    assert count() == 0
    assert len(_notifications(client, seeker)) == 2  # still listed, just read


def test_limit_parameter_is_validated(client, user):
    assert client.get("/api/notifications?limit=0", headers=user.headers).status_code == 422
    assert client.get("/api/notifications?limit=101", headers=user.headers).status_code == 422


def test_users_only_see_their_own_notifications(client, recruiter, seeker, make_user, application_id):
    stranger = make_user(role="recruiter")
    assert _notifications(client, stranger) == []


def test_cannot_read_or_delete_someone_elses_notification(client, recruiter, seeker, make_user, application_id):
    [note] = _notifications(client, recruiter)
    stranger = make_user()

    assert client.post(f"/api/notifications/{note['id']}/read", headers=stranger.headers).status_code == 404
    assert client.delete(f"/api/notifications/{note['id']}", headers=stranger.headers).status_code == 404

    # ...and it is untouched for the real owner.
    [still] = _notifications(client, recruiter)
    assert still["is_read"] is False


def test_read_all_does_not_touch_other_users(client, recruiter, seeker, make_user, application_id):
    stranger = make_user()
    client.post("/api/notifications/read-all", headers=stranger.headers)

    assert _notifications(client, recruiter)[0]["is_read"] is False


def test_delete_notification(client, recruiter, seeker, application_id):
    [note] = _notifications(client, recruiter)

    assert client.delete(f"/api/notifications/{note['id']}", headers=recruiter.headers).status_code == 204
    assert _notifications(client, recruiter) == []
    assert client.delete(f"/api/notifications/{note['id']}", headers=recruiter.headers).status_code == 404


def test_notification_survives_deleted_posting(client, recruiter, seeker, job_id, application_id):
    """Deleting a posting removes its applications; the recruiter's history
    message must remain (application_id just becomes null)."""
    assert client.delete(f"/api/jobs/{job_id}", headers=recruiter.headers).status_code == 200

    [note] = _notifications(client, recruiter)
    assert note["application_id"] is None
    assert "Sam Seeker" in note["message"]


# ============================================================================
# 3. Model constraint
# ============================================================================
def test_database_rejects_unknown_notification_type(user):
    db = SessionLocal()
    try:
        db.add(Notification(user_id=user.id, type="bogus", title="x", message="y"))
        # DBAPIError is the parent of IntegrityError / ProgrammingError: the
        # pg8000 driver reports a CHECK violation as ProgrammingError.
        with pytest.raises(DBAPIError):
            db.commit()
    finally:
        db.rollback()
        db.close()
