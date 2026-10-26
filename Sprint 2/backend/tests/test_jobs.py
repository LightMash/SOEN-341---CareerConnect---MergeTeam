"""
Job posting API.
Endpoints: POST /api/jobs, GET /api/jobs/mine, GET/PUT/DELETE /api/jobs/{id},
           POST /api/jobs/{id}/close, POST /api/jobs/{id}/reopen

The `user` fixture is a logged-in job seeker; `make_user(role="recruiter")`
creates recruiters.
"""

import pytest

VALID_JOB = {
    "title": "Junior Developer",
    "company": "Acme",
    "location": "Montreal, QC",
    "job_type": "Internship",
    "category": "Software",
    "description": "Build things with React and FastAPI.",
    "salary_min": 45000,
    "salary_max": 60000,
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter")


def _create(client, account, **overrides):
    return client.post("/api/jobs", json={**VALID_JOB, **overrides}, headers=account.headers)


def _create_ok(client, account, **overrides) -> dict:
    response = _create(client, account, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


# ----------------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------------
def test_recruiter_creates_job(client, recruiter):
    response = _create(client, recruiter)

    assert response.status_code == 201
    job = response.json()
    for field, value in VALID_JOB.items():
        assert job[field] == value
    assert job["recruiter_id"] == recruiter.id
    assert job["is_open"] is True


def test_only_title_and_company_are_required(client, recruiter):
    response = client.post(
        "/api/jobs", json={"title": "Dev", "company": "Acme"}, headers=recruiter.headers
    )
    assert response.status_code == 201
    assert response.json()["job_type"] == "Full-time"


def test_job_seeker_cannot_create_job(client, user):
    assert _create(client, user).status_code == 403


def test_create_requires_login(client):
    assert client.post("/api/jobs", json=VALID_JOB).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},                              # blank after trimming
        {"company": ""},
        {"job_type": "Freelance"},                     # not one of the 4 types
        {"salary_min": -1},
        {"salary_min": 90000, "salary_max": 50000},    # inverted range
        {"title": "x" * 121},                          # too long
    ],
)
def test_invalid_job_is_rejected(client, recruiter, overrides):
    assert _create(client, recruiter, **overrides).status_code == 422


def test_client_cannot_set_owner_or_open_flag(client, recruiter):
    response = _create(client, recruiter, recruiter_id=1, is_open=False)
    assert response.status_code == 422


# ----------------------------------------------------------------------------
# Read
# ----------------------------------------------------------------------------
def test_list_my_jobs_newest_first_including_closed(client, recruiter):
    first = _create_ok(client, recruiter, title="First")
    second = _create_ok(client, recruiter, title="Second")
    client.post(f"/api/jobs/{first['id']}/close", headers=recruiter.headers)

    response = client.get("/api/jobs/mine", headers=recruiter.headers)

    assert response.status_code == 200
    jobs = response.json()
    assert [j["id"] for j in jobs] == [second["id"], first["id"]]
    assert jobs[1]["is_open"] is False


def test_list_mine_only_shows_my_jobs(client, recruiter, make_user):
    _create_ok(client, make_user(role="recruiter"))
    response = client.get("/api/jobs/mine", headers=recruiter.headers)
    assert response.json() == []


def test_job_seeker_cannot_list_mine(client, user):
    assert client.get("/api/jobs/mine", headers=user.headers).status_code == 403


def test_anyone_logged_in_can_view_open_job(client, recruiter, user):
    job = _create_ok(client, recruiter)
    response = client.get(f"/api/jobs/{job['id']}", headers=user.headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Junior Developer"


def test_closed_job_hidden_from_others_but_visible_to_owner(client, recruiter, user):
    job = _create_ok(client, recruiter)
    client.post(f"/api/jobs/{job['id']}/close", headers=recruiter.headers)

    assert client.get(f"/api/jobs/{job['id']}", headers=user.headers).status_code == 404
    assert client.get(f"/api/jobs/{job['id']}", headers=recruiter.headers).status_code == 200


def test_unknown_job_is_404(client, user):
    assert client.get("/api/jobs/999999999", headers=user.headers).status_code == 404


# ----------------------------------------------------------------------------
# Update
# ----------------------------------------------------------------------------
def test_owner_updates_job(client, recruiter):
    job = _create_ok(client, recruiter)
    changed = {**VALID_JOB, "title": "Senior Developer", "salary_min": None, "salary_max": None}

    response = client.put(f"/api/jobs/{job['id']}", json=changed, headers=recruiter.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Senior Developer"
    assert body["salary_min"] is None
    assert body["updated_at"] >= job["updated_at"]


def test_other_recruiter_cannot_update(client, recruiter, make_user):
    job = _create_ok(client, recruiter)
    other = make_user(role="recruiter")
    response = client.put(f"/api/jobs/{job['id']}", json=VALID_JOB, headers=other.headers)
    assert response.status_code == 403


def test_invalid_update_changes_nothing(client, recruiter):
    job = _create_ok(client, recruiter)
    bad = {**VALID_JOB, "title": ""}

    assert client.put(f"/api/jobs/{job['id']}", json=bad, headers=recruiter.headers).status_code == 422
    assert client.get(f"/api/jobs/{job['id']}", headers=recruiter.headers).json()["title"] == "Junior Developer"


def test_update_unknown_job_is_404(client, recruiter):
    assert client.put("/api/jobs/999999999", json=VALID_JOB, headers=recruiter.headers).status_code == 404


# ----------------------------------------------------------------------------
# Close / reopen
# ----------------------------------------------------------------------------
def test_close_and_reopen(client, recruiter):
    job = _create_ok(client, recruiter)

    closed = client.post(f"/api/jobs/{job['id']}/close", headers=recruiter.headers)
    assert closed.status_code == 200
    assert closed.json()["is_open"] is False

    reopened = client.post(f"/api/jobs/{job['id']}/reopen", headers=recruiter.headers)
    assert reopened.status_code == 200
    assert reopened.json()["is_open"] is True


def test_closing_twice_is_400(client, recruiter):
    job = _create_ok(client, recruiter)
    client.post(f"/api/jobs/{job['id']}/close", headers=recruiter.headers)
    assert client.post(f"/api/jobs/{job['id']}/close", headers=recruiter.headers).status_code == 400


def test_reopening_open_job_is_400(client, recruiter):
    job = _create_ok(client, recruiter)
    assert client.post(f"/api/jobs/{job['id']}/reopen", headers=recruiter.headers).status_code == 400


def test_other_users_cannot_close(client, recruiter, user, make_user):
    job = _create_ok(client, recruiter)
    assert client.post(f"/api/jobs/{job['id']}/close", headers=user.headers).status_code == 403
    other = make_user(role="recruiter")
    assert client.post(f"/api/jobs/{job['id']}/close", headers=other.headers).status_code == 403


# ----------------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------------
def test_owner_deletes_job(client, recruiter):
    job = _create_ok(client, recruiter)

    response = client.delete(f"/api/jobs/{job['id']}", headers=recruiter.headers)

    assert response.status_code == 200
    assert client.get(f"/api/jobs/{job['id']}", headers=recruiter.headers).status_code == 404
    assert client.get("/api/jobs/mine", headers=recruiter.headers).json() == []


def test_other_users_cannot_delete(client, recruiter, user, make_user):
    job = _create_ok(client, recruiter)
    assert client.delete(f"/api/jobs/{job['id']}", headers=user.headers).status_code == 403
    other = make_user(role="recruiter")
    assert client.delete(f"/api/jobs/{job['id']}", headers=other.headers).status_code == 403
    # still there
    assert client.get(f"/api/jobs/{job['id']}", headers=recruiter.headers).status_code == 200


def test_delete_unknown_job_is_404(client, recruiter):
    assert client.delete("/api/jobs/999999999", headers=recruiter.headers).status_code == 404
