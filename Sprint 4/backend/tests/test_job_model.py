"""
Database schema for job postings.

These tests talk to the database directly, without going through the API,
and check the rules the schema itself must enforce:
  - a new posting is open, Full-time, with empty optional text fields
  - only the 4 known job types can be stored
  - salary_min can never be greater than salary_max
"""

import pytest
from sqlalchemy.exc import DBAPIError

from database import SessionLocal
from models import Job


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
def recruiter_id(make_user) -> int:
    return make_user(role="recruiter").id


def test_new_job_defaults(db, recruiter_id):
    job = Job(recruiter_id=recruiter_id, title="Junior Developer", company="Acme")
    db.add(job)
    db.commit()
    db.refresh(job)

    assert job.is_open is True
    assert job.job_type == "Full-time"
    assert job.location == ""
    assert job.category == ""
    assert job.description == ""
    assert job.salary_min is None and job.salary_max is None
    assert job.created_at is not None and job.updated_at is not None
    assert job.recruiter.id == recruiter_id


@pytest.mark.parametrize("job_type", ["Full-time", "Part-time", "Internship", "Contract"])
def test_every_valid_job_type_is_accepted(db, recruiter_id, job_type):
    db.add(Job(recruiter_id=recruiter_id, title="T", company="C", job_type=job_type))
    db.commit()  # no error expected


def test_unknown_job_type_is_rejected(db, recruiter_id):
    db.add(Job(recruiter_id=recruiter_id, title="T", company="C", job_type="Freelance"))
    # pg8000 reports CHECK violations as ProgrammingError (not IntegrityError),
    # so catch their common parent and check it was OUR constraint that fired.
    with pytest.raises(DBAPIError, match="ck_job_type"):
        db.commit()


def test_inverted_salary_range_is_rejected(db, recruiter_id):
    db.add(Job(recruiter_id=recruiter_id, title="T", company="C", salary_min=90000, salary_max=50000))
    with pytest.raises(DBAPIError, match="ck_job_salary_range"):
        db.commit()


def test_partial_salary_is_allowed(db, recruiter_id):
    db.add(Job(recruiter_id=recruiter_id, title="T", company="C", salary_min=50000))
    db.commit()  # no error expected
