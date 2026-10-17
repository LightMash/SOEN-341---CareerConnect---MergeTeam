"""
Shared test setup ("fixtures") used by every test file in this folder.

pytest automatically loads this file first. Anything defined here with
@pytest.fixture can be used in a test simply by naming it as a function
argument, e.g.  def test_something(client, make_user): ...

HOW TO ADD TESTS FOR A NEW FEATURE (jobs, applications, ...):
  1. Create  tests/test_<feature>.py
  2. Write functions named  test_<what_it_checks>
  3. Ask for the fixtures you need as arguments (client, make_user, ...)
That's it - pytest finds the file on its own and CI runs it with no changes.
"""

import os
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import pytest

# -----------------------------------------------------------------------------
# 1. SAFETY GUARD - never run tests against the shared Supabase database
# -----------------------------------------------------------------------------
# The tests create many fake users. They must only ever run against a database
# on THIS machine (a local Postgres, or the throwaway one GitHub starts in CI).
# We check BEFORE importing the app, because importing the app loads backend/.env
# (which may contain the real Supabase URL) and connects to the database.
_url = os.environ.get("DATABASE_URL", "")
if urlparse(_url).hostname not in ("localhost", "127.0.0.1", "::1"):
    pytest.exit(
        "\nRefusing to run tests: DATABASE_URL must point to a LOCAL Postgres "
        "(localhost / 127.0.0.1), never the shared Supabase database.\n"
        "Start one with Docker, for example:\n"
        "  docker run -d --name cc-test-db -p 5432:5432 -e POSTGRES_PASSWORD=postgres "
        "-e POSTGRES_DB=careerconnect_test postgres:16\n"
        "then run:\n"
        "  DATABASE_URL=postgresql+pg8000://postgres:postgres@localhost:5432/careerconnect_test "
        "pytest -v\n",
        returncode=2,
    )

# A fixed dummy key so tokens signed during tests are predictable.
os.environ.setdefault("SECRET_KEY", "test-secret-key")

# These imports MUST come after the guard and the env setup above, because
# database.py and security.py read the environment as soon as they are imported.
from fastapi.testclient import TestClient  # noqa: E402

import routers.profile as profile_router  # noqa: E402
import routers.resume as resume_router  # noqa: E402
from app import app  # noqa: E402  (importing the app also creates the DB tables)

# A password that satisfies the rules (8-72 characters). Reused everywhere.
DEFAULT_PASSWORD = "Password123"


# -----------------------------------------------------------------------------
# 2. The test client - a fake browser that calls our API without a real server
# -----------------------------------------------------------------------------
@pytest.fixture(scope="session")
def client():
    """One TestClient for the whole run. Use it like:  client.get("/api/health")"""
    with TestClient(app) as test_client:
        yield test_client


# -----------------------------------------------------------------------------
# 3. Keep uploaded files out of the real backend/uploads/ folder
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """
    Runs automatically before EVERY test (autouse). Points the resume and
    profile-photo folders at a fresh temporary directory that pytest deletes
    afterwards, so tests never leave files behind. Returns the resume folder
    in case a test wants to inspect it.
    """
    resumes = tmp_path / "resumes"
    avatars = tmp_path / "avatars"
    monkeypatch.setattr(resume_router, "UPLOAD_DIR", str(resumes))
    monkeypatch.setattr(profile_router, "AVATAR_DIR", str(avatars))
    return resumes


# -----------------------------------------------------------------------------
# 4. Creating users and logging them in
# -----------------------------------------------------------------------------
@dataclass
class Account:
    """Everything a test might need to know about a freshly registered user."""

    id: int
    email: str
    password: str
    role: str
    token: str

    @property
    def headers(self) -> dict:
        """Ready-made header to pass as  client.get(url, headers=user.headers)"""
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def make_user(client):
    """
    Factory that registers a brand-new user through the real /api/register
    endpoint. Each call uses a unique email, so tests can't collide with each
    other or with leftovers from a previous run.

        job_seeker = make_user()
        recruiter  = make_user(role="recruiter")
        other      = make_user()          # a second, different user
    """

    def _make(role: str = "job_seeker", full_name: str = "Test User") -> Account:
        email = f"user-{uuid.uuid4().hex[:12]}@example.com"
        response = client.post(
            "/api/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": DEFAULT_PASSWORD,
                "role": role,
            },
        )
        assert response.status_code == 201, f"could not create test user: {response.text}"
        body = response.json()
        return Account(
            id=body["user"]["id"],
            email=email,
            password=DEFAULT_PASSWORD,
            role=role,
            token=body["token"],
        )

    return _make


@pytest.fixture
def user(make_user) -> Account:
    """A ready-to-use job seeker (shortcut for make_user())."""
    return make_user()
