"""
Automated tests for Registration, Login and token-protected access.
Covers: POST /api/register, POST /api/login, GET /api/profile

Pattern used in every test:  Arrange (set up) -> Act (call the API) -> Assert (check).
"""

import datetime
import uuid

import pytest
from jose import jwt

from conftest import DEFAULT_PASSWORD
from security import ALGORITHM, SECRET_KEY


def _new_email() -> str:
    """A unique email so each test registers a different person."""
    return f"auth-{uuid.uuid4().hex[:12]}@example.com"


def _register(client, **overrides):
    """Register with sensible defaults; override any field you want to test."""
    payload = {
        "full_name": "Jane Doe",
        "email": _new_email(),
        "password": DEFAULT_PASSWORD,
        **overrides,
    }
    return client.post("/api/register", json=payload)


# ----------------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------------
def test_register_success_returns_token_and_user(client):
    response = _register(client, full_name="Jane Doe")

    assert response.status_code == 201
    body = response.json()
    assert body["token"]                              # a login token is issued right away
    assert body["user"]["full_name"] == "Jane Doe"
    assert body["user"]["role"] == "job_seeker"       # default role
    assert "password" not in body["user"]             # never send passwords back
    assert "password_hash" not in body["user"]


def test_register_recruiter_role(client):
    response = _register(client, role="recruiter")

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "recruiter"


def test_register_stores_email_in_lowercase(client):
    response = _register(client, email=f"MiXeD-{uuid.uuid4().hex[:8]}@Example.COM")

    assert response.status_code == 201
    email = response.json()["user"]["email"]
    assert email == email.lower()


def test_register_duplicate_email_is_rejected(client):
    email = _new_email()
    assert _register(client, email=email).status_code == 201

    second = _register(client, email=email)

    assert second.status_code == 409


def test_register_duplicate_email_ignores_letter_case(client):
    email = _new_email()
    assert _register(client, email=email).status_code == 201

    # Same address typed with capital letters must still count as a duplicate.
    second = _register(client, email=email.upper())

    assert second.status_code == 409


# Each tuple is (what we change, the bad value). One test function runs once
# per tuple - an easy way to cover many invalid inputs without copy/paste.
@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("password", "short"),            # fewer than 8 characters
        ("password", "x" * 73),           # more than 72 (bcrypt's limit)
        ("email", "not-an-email"),        # not a valid email address
        ("role", "admin"),                # only job_seeker / recruiter are allowed
        ("full_name", ""),                # name is required
    ],
)
def test_register_rejects_invalid_input(client, field, bad_value):
    response = _register(client, **{field: bad_value})

    assert response.status_code == 422                # 422 = validation error


def test_register_requires_all_fields(client):
    response = client.post("/api/register", json={"email": _new_email()})

    assert response.status_code == 422


# ----------------------------------------------------------------------------
# Login
# ----------------------------------------------------------------------------
def test_login_success(client, user):
    response = client.post("/api/login", json={"email": user.email, "password": user.password})

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["id"] == user.id


def test_login_email_is_case_insensitive(client, user):
    response = client.post("/api/login", json={"email": user.email.upper(), "password": user.password})

    assert response.status_code == 200


def test_login_wrong_password(client, user):
    response = client.post("/api/login", json={"email": user.email, "password": "WrongPassword1"})

    assert response.status_code == 401


def test_login_unknown_email_gives_same_error_as_wrong_password(client, user):
    # Security: the API must not reveal whether an email is registered, so an
    # unknown email and a wrong password must look identical to the caller.
    unknown = client.post("/api/login", json={"email": _new_email(), "password": DEFAULT_PASSWORD})
    wrong_pw = client.post("/api/login", json={"email": user.email, "password": "WrongPassword1"})

    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.json()["detail"] == wrong_pw.json()["detail"]


# ----------------------------------------------------------------------------
# Token-protected access (GET /api/profile returns the logged-in user)
# ----------------------------------------------------------------------------
def test_profile_with_valid_token(client, user):
    response = client.get("/api/profile", headers=user.headers)

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_profile_without_token_is_unauthorized(client):
    response = client.get("/api/profile")

    assert response.status_code == 401


def test_profile_with_garbage_token_is_unauthorized(client):
    response = client.get("/api/profile", headers={"Authorization": "Bearer not.a.real.token"})

    assert response.status_code == 401


def test_profile_with_expired_token_is_unauthorized(client, user):
    # Build a token that is correctly signed but expired an hour ago.
    expired = jwt.encode(
        {"user_id": user.id, "exp": datetime.datetime.utcnow() - datetime.timedelta(hours=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.get("/api/profile", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_profile_with_token_signed_by_wrong_key_is_unauthorized(client, user):
    # A forged token (signed with a different secret) must be rejected.
    forged = jwt.encode({"user_id": user.id}, "some-other-secret", algorithm=ALGORITHM)

    response = client.get("/api/profile", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
