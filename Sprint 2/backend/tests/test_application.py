"""
Database schema for job applications.

Check the rules the schema itself must enforce:
  - a new application starts as "Applied"
  - the same job seeker cannot apply twice to the same job
  - only the 5 known statuses can be stored
  - deleting a resume keeps the application (resume_id becomes NULL)
  - deleting a job deletes its applications
"""

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from database import SessionLocal
from models import Application, Job, Resume


@pytest.fixture
def db():
    """A database session for one test, always closed afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def job(db, make_user):
    """An open job posting owned by a fresh recruiter."""
    recruiter = make_user(role="recruiter")
    posting = Job(recruiter_id=recruiter.id, title="Junior Developer", company="Acme")
    db.add(posting)
    db.commit()
    db.refresh(posting)
    return posting


def _add_resume(db, user_id: int) -> Resume:
    resume = Resume(user_id=user_id, filename="cv.pdf", filepath="/tmp/does-not-matter.pdf")
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def test_new_application_defaults_to_applied(db, job, user):
    resume = _add_resume(db, user.id)
    application = Application(job_id=job.id, applicant_id=user.id, resume_id=resume.id)
    db.add(application)
    db.commit()
    db.refresh(application)

    assert application.status == "Applied"
    assert application.applied_at is not None
    assert application.job.title == "Junior Developer"
    assert application.resume.filename == "cv.pdf"


def test_same_user_cannot_apply_twice_to_same_job(db, job, user):
    db.add(Application(job_id=job.id, applicant_id=user.id))
    db.commit()

    db.add(Application(job_id=job.id, applicant_id=user.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_different_users_can_apply_to_same_job(db, job, make_user):
    db.add(Application(job_id=job.id, applicant_id=make_user().id))
    db.add(Application(job_id=job.id, applicant_id=make_user().id))
    db.commit()  # no error expected

    assert db.query(Application).filter(Application.job_id == job.id).count() == 2


def test_unknown_status_is_rejected(db, job, user):
    db.add(Application(job_id=job.id, applicant_id=user.id, status="Hired"))
    # pg8000 reports CHECK violations as ProgrammingError (not IntegrityError),
    # so catch their common parent and check it was OUR constraint that fired.
    with pytest.raises(DBAPIError, match="ck_application_status"):
        db.commit()


@pytest.mark.parametrize("status", ["Applied", "Under Review", "Interview", "Offered", "Rejected"])
def test_every_valid_status_is_accepted(db, job, make_user, status):
    db.add(Application(job_id=job.id, applicant_id=make_user().id, status=status))
    db.commit()  # no error expected


def test_deleting_resume_keeps_application(db, job, user):
    resume = _add_resume(db, user.id)
    application = Application(job_id=job.id, applicant_id=user.id, resume_id=resume.id)
    db.add(application)
    db.commit()

    db.delete(resume)
    db.commit()
    db.refresh(application)

    assert application.resume_id is None


def test_deleting_job_deletes_its_applications(db, job, user):
    application = Application(job_id=job.id, applicant_id=user.id)
    db.add(application)
    db.commit()
    application_id = application.id

    db.delete(job)
    db.commit()

    assert db.get(Application, application_id) is None