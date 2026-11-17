"""Task 4.5: recruiter-only access to a resume attached to an application.

Uses the shared conftest.py fixtures and the LOCAL test database only.
"""

import os

import pytest

from database import SessionLocal
from models import Application, Job

PDF_BYTES = b"%PDF-1.4 test resume contents\n%%EOF\n"
FILENAME = "candidate-resume.pdf"
MISSING_MESSAGE = "This applicant’s resume is no longer available"


@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter", full_name="Rita Recruiter")


@pytest.fixture
def job_id(recruiter):
    db = SessionLocal()
    try:
        job = Job(recruiter_id=recruiter.id, title="Junior Developer", company="Acme")
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


@pytest.fixture
def application_with_resume(client, user, job_id):
    upload = client.post(
        "/api/resume/upload",
        files={"file": (FILENAME, PDF_BYTES, "application/pdf")},
        headers=user.headers,
    )
    assert upload.status_code == 200, upload.text
    resume_id = upload.json()["resume"]["id"]

    response = client.post(
        "/api/applications", json={"job_id": job_id}, headers=user.headers
    )
    assert response.status_code == 201, response.text
    application_id = response.json()["application"]["id"]
    return application_id, resume_id


def _download(client, application_id, headers=None):
    return client.get(f"/api/applications/{application_id}/resume", headers=headers)


def test_owner_recruiter_downloads_resume_with_original_name_and_bytes(
    client, recruiter, application_with_resume
):
    application_id, _ = application_with_resume
    response = _download(client, application_id, recruiter.headers)

    assert response.status_code == 200, response.text
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert f'filename="{FILENAME}"' in response.headers["content-disposition"]
    assert "attachment" in response.headers["content-disposition"]


def test_other_recruiter_gets_403(client, make_user, application_with_resume):
    other = make_user(role="recruiter")
    application_id, _ = application_with_resume
    assert _download(client, application_id, other.headers).status_code == 403


def test_job_seeker_gets_403(client, user, application_with_resume):
    application_id, _ = application_with_resume
    assert _download(client, application_id, user.headers).status_code == 403


def test_no_token_gets_401(client, application_with_resume):
    application_id, _ = application_with_resume
    assert _download(client, application_id).status_code == 401


def test_missing_application_gets_404(client, recruiter):
    response = _download(client, 999_999_999, recruiter.headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found."


def test_deleted_resume_gets_404(client, recruiter, user, application_with_resume):
    application_id, resume_id = application_with_resume
    deleted = client.delete(f"/api/resume/{resume_id}", headers=user.headers)
    assert deleted.status_code == 200, deleted.text

    response = _download(client, application_id, recruiter.headers)
    assert response.status_code == 404
    assert response.json()["detail"] == MISSING_MESSAGE


def test_missing_file_on_disk_gets_404(
    client, recruiter, application_with_resume
):
    application_id, _ = application_with_resume
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == application_id).one()
        path = application.resume.filepath
    finally:
        db.close()

    # Only the test's temporary uploaded file is removed.
    os.remove(path)
    response = _download(client, application_id, recruiter.headers)
    assert response.status_code == 404
    assert response.json()["detail"] == MISSING_MESSAGE