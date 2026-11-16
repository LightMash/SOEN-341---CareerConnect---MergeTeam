"""
Task 4.4: recruiter applicant filters.
GET /api/jobs/{job_id}/applications?status=...&applied_from=...&applied_to=...

Uses the shared conftest.py fixtures and a LOCAL test database only.
"""

from datetime import datetime

import pytest

from database import SessionLocal
from models import Application, Job

PDF_BYTES = b"%PDF-1.4 fake resume content"


# ----------------------------------------------------------------------------
# Helpers and fixtures (same API-driven style as test_application_status.py)
# ----------------------------------------------------------------------------
@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter", full_name="Rita Recruiter")


@pytest.fixture
def job_id(recruiter) -> int:
    db = SessionLocal()
    try:
        job = Job(recruiter_id=recruiter.id, title="Junior Developer", company="Acme")
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


@pytest.fixture
def seeded_applications(client, make_user, recruiter, job_id):
    """Five applications with distinct statuses and deterministic timestamps.

    Two applications occur on Feb 3, including one at the very end of the day.
    Times are set directly in the test database so date-boundary tests are stable.
    """
    cases = [
        ("Applied", datetime(2026, 2, 1, 8, 0)),
        ("Under Review", datetime(2026, 2, 2, 12, 0)),
        ("Interview", datetime(2026, 2, 3, 0, 0)),
        ("Offered", datetime(2026, 2, 3, 23, 59, 59, 999999)),
        ("Rejected", datetime(2026, 2, 4, 9, 0)),
    ]
    result = {}
    for applicant_status, applied_at in cases:
        applicant = make_user(role="job_seeker")
        upload = client.post(
            "/api/resume/upload",
            files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")},
            headers=applicant.headers,
        )
        assert upload.status_code == 200, upload.text

        response = client.post(
            "/api/applications", json={"job_id": job_id}, headers=applicant.headers
        )
        assert response.status_code == 201, response.text
        application_id = response.json()["application"]["id"]

        if applicant_status != "Applied":
            updated = client.patch(
                f"/api/applications/{application_id}/status",
                json={"status": applicant_status},
                headers=recruiter.headers,
            )
            assert updated.status_code == 200, updated.text

        db = SessionLocal()
        try:
            application = db.query(Application).filter(Application.id == application_id).one()
            application.applied_at = applied_at
            db.commit()
        finally:
            db.close()

        result[applicant_status] = application_id

    return result


def _list(client, recruiter, job_id, **params):
    return client.get(
        f"/api/jobs/{job_id}/applications",
        params=params,
        headers=recruiter.headers,
    )


def _ids(response):
    return [entry["id"] for entry in response.json()]


# ----------------------------------------------------------------------------
# No filters and individual filters
# ----------------------------------------------------------------------------
def test_no_filters_returns_all_in_original_order(client, recruiter, job_id, seeded_applications):
    response = _list(client, recruiter, job_id)
    assert response.status_code == 200, response.text
    assert _ids(response) == list(seeded_applications.values())
    assert all("applicant_name" in item and "applied_at" in item for item in response.json())


@pytest.mark.parametrize(
    "status", ["Applied", "Under Review", "Interview", "Offered", "Rejected"]
)
def test_status_filter_alone(client, recruiter, job_id, seeded_applications, status):
    response = _list(client, recruiter, job_id, status=status)
    assert response.status_code == 200, response.text
    assert _ids(response) == [seeded_applications[status]]
    assert response.json()[0]["status"] == status


def test_applied_from_filter_alone(client, recruiter, job_id, seeded_applications):
    response = _list(client, recruiter, job_id, applied_from="2026-02-03")
    assert response.status_code == 200, response.text
    assert _ids(response) == [
        seeded_applications["Interview"],
        seeded_applications["Offered"],
        seeded_applications["Rejected"],
    ]


def test_applied_to_filter_alone_includes_whole_day(client, recruiter, job_id, seeded_applications):
    response = _list(client, recruiter, job_id, applied_to="2026-02-03")
    assert response.status_code == 200, response.text
    assert _ids(response) == [
        seeded_applications["Applied"],
        seeded_applications["Under Review"],
        seeded_applications["Interview"],
        seeded_applications["Offered"],  # 23:59:59.999999 must be included
    ]


def test_date_range_same_day_includes_both_boundaries(client, recruiter, job_id, seeded_applications):
    response = _list(
        client, recruiter, job_id, applied_from="2026-02-03", applied_to="2026-02-03"
    )
    assert response.status_code == 200, response.text
    assert _ids(response) == [
        seeded_applications["Interview"],
        seeded_applications["Offered"],
    ]


# ----------------------------------------------------------------------------
# Combined filters, invalid filters and ownership
# ----------------------------------------------------------------------------
def test_status_and_date_filters_combined(client, recruiter, job_id, seeded_applications):
    response = _list(
        client,
        recruiter,
        job_id,
        status="Offered",
        applied_from="2026-02-02",
        applied_to="2026-02-03",
    )
    assert response.status_code == 200, response.text
    assert _ids(response) == [seeded_applications["Offered"]]


def test_combined_filters_with_no_matches_returns_empty(client, recruiter, job_id, seeded_applications):
    response = _list(
        client, recruiter, job_id, status="Rejected", applied_to="2026-02-03"
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.parametrize("invalid", ["Hired", "applied", "", "Under review"])
def test_invalid_status_returns_422(client, recruiter, job_id, invalid):
    response = _list(client, recruiter, job_id, status=invalid)
    assert response.status_code == 422


def test_applied_from_after_applied_to_returns_400(client, recruiter, job_id):
    response = _list(
        client, recruiter, job_id, applied_from="2026-02-04", applied_to="2026-02-03"
    )
    assert response.status_code == 400
    assert "applied_from" in response.json()["detail"]


@pytest.mark.parametrize("field", ["applied_from", "applied_to"])
def test_invalid_date_returns_422(client, recruiter, job_id, field):
    response = _list(client, recruiter, job_id, **{field: "2026-02-30"})
    assert response.status_code == 422


def test_other_recruiter_still_gets_403(client, make_user, job_id):
    other_recruiter = make_user(role="recruiter")
    response = _list(
        client,
        other_recruiter,
        job_id,
        status="Applied",
        applied_from="2026-02-01",
        applied_to="2026-02-04",
    )
    assert response.status_code == 403


def test_job_seeker_still_gets_403(client, make_user, job_id):
    seeker = make_user(role="job_seeker")
    response = _list(client, seeker, job_id, status="Applied")
    assert response.status_code == 403