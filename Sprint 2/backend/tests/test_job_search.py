"""
Job search API.
Endpoint: GET /api/jobs  (open postings only, newest first)
Filters (all optional, combined with AND):
  q          keyword, partial + case-insensitive on title / company / description
  location   partial + case-insensitive
  category   partial + case-insensitive
  job_type   exact, one of JOB_TYPES  (anything else -> 422)
  work_from  exact, one of WORK_FROM  (anything else -> 422)

The database is shared by every test in the run, so each test gets a unique
`tag` and puts it in the title of every job it creates. Every search passes
q=<tag>, and since filters combine with AND, a test only ever sees its own jobs.
"""

import uuid

import pytest

BASE_JOB = {
    "title": "Developer",
    "company": "Acme",
    "location": "Montreal, QC",
    "job_type": "Full-time",
    "work_from": "On-site",
    "category": "Software",
    "description": "Build things.",
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter")


@pytest.fixture
def tag():
    """Unique marker for this test's jobs, e.g. 'tag3f9a1c2b7d'."""
    return f"tag{uuid.uuid4().hex[:10]}"


def _create_ok(client, recruiter, tag, **overrides) -> dict:
    """Create an open job whose title contains `tag`, so searches can scope to it."""
    body = {**BASE_JOB, "title": f"{BASE_JOB['title']} {tag}", **overrides}
    response = client.post("/api/jobs", json=body, headers=recruiter.headers)
    assert response.status_code == 201, response.text
    return response.json()


def _search_ids(client, account, **params) -> list[int]:
    """GET /api/jobs with the given query params; returns the ids in response order."""
    response = client.get("/api/jobs", params=params, headers=account.headers)
    assert response.status_code == 200, response.text
    return [job["id"] for job in response.json()]


# ----------------------------------------------------------------------------
# Access + ordering
# ----------------------------------------------------------------------------
def test_search_requires_login(client):
    assert client.get("/api/jobs").status_code == 401


def test_results_are_newest_first(client, recruiter, user, tag):
    first = _create_ok(client, recruiter, tag)
    second = _create_ok(client, recruiter, tag)
    third = _create_ok(client, recruiter, tag)

    assert _search_ids(client, user, q=tag) == [third["id"], second["id"], first["id"]]


def test_closed_jobs_are_hidden(client, recruiter, user, tag):
    open_job = _create_ok(client, recruiter, tag)
    closed_job = _create_ok(client, recruiter, tag)
    client.post(f"/api/jobs/{closed_job['id']}/close", headers=recruiter.headers)

    assert _search_ids(client, user, q=tag) == [open_job["id"]]


# ----------------------------------------------------------------------------
# Keyword search
# ----------------------------------------------------------------------------
def test_keyword_matches_title_company_or_description(client, recruiter, user, tag):
    # Each job carries a second, unique word in a different field.
    word = f"kw{uuid.uuid4().hex[:8]}"
    in_title = _create_ok(client, recruiter, tag, title=f"{word} engineer {tag}")
    in_company = _create_ok(client, recruiter, tag, company=f"{word} Inc")
    in_description = _create_ok(client, recruiter, tag, description=f"Work on {word} daily")
    _create_ok(client, recruiter, tag)  # no keyword -> must not match

    # Upper-cased to also check the match is case-insensitive.
    ids = _search_ids(client, user, q=word.upper())

    assert set(ids) == {in_title["id"], in_company["id"], in_description["id"]}


# ----------------------------------------------------------------------------
# Partial-match filters
# ----------------------------------------------------------------------------
def test_location_is_partial_and_case_insensitive(client, recruiter, user, tag):
    montreal = _create_ok(client, recruiter, tag, location="Montreal, QC")
    _create_ok(client, recruiter, tag, location="Toronto, ON")

    assert _search_ids(client, user, q=tag, location="montreal") == [montreal["id"]]


def test_category_is_partial_and_case_insensitive(client, recruiter, user, tag):
    software = _create_ok(client, recruiter, tag, category="Software Engineering")
    _create_ok(client, recruiter, tag, category="Marketing")

    assert _search_ids(client, user, q=tag, category="SOFTWARE") == [software["id"]]


# ----------------------------------------------------------------------------
# Exact-match filters
# ----------------------------------------------------------------------------
def test_job_type_is_exact_match(client, recruiter, user, tag):
    internship = _create_ok(client, recruiter, tag, job_type="Internship")
    _create_ok(client, recruiter, tag, job_type="Contract")

    assert _search_ids(client, user, q=tag, job_type="Internship") == [internship["id"]]


def test_work_from_is_exact_match(client, recruiter, user, tag):
    remote = _create_ok(client, recruiter, tag, work_from="Remote")
    _create_ok(client, recruiter, tag, work_from="Hybrid")

    assert _search_ids(client, user, q=tag, work_from="Remote") == [remote["id"]]


# ----------------------------------------------------------------------------
# Combined filters
# ----------------------------------------------------------------------------
def test_filters_combine_with_and(client, recruiter, user, tag):
    match = _create_ok(
        client, recruiter, tag,
        location="Montreal, QC", category="Software", job_type="Internship", work_from="Remote",
    )
    # Each of these fails exactly one filter.
    _create_ok(client, recruiter, tag, location="Toronto, ON", category="Software", job_type="Internship", work_from="Remote")
    _create_ok(client, recruiter, tag, location="Montreal, QC", category="Finance", job_type="Internship", work_from="Remote")
    _create_ok(client, recruiter, tag, location="Montreal, QC", category="Software", job_type="Full-time", work_from="Remote")
    _create_ok(client, recruiter, tag, location="Montreal, QC", category="Software", job_type="Internship", work_from="On-site")

    ids = _search_ids(
        client, user,
        q=tag, location="montreal", category="soft", job_type="Internship", work_from="Remote",
    )

    assert ids == [match["id"]]


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "params",
    [
        {"job_type": "Freelance"},   # not one of the 4 types
        {"job_type": "internship"},  # exact match: wrong case is invalid
        {"work_from": "Mars"},       # not one of the 3 options
        {"work_from": "remote"},
    ],
)
def test_invalid_enum_filter_is_422(client, user, params):
    response = client.get("/api/jobs", params=params, headers=user.headers)
    assert response.status_code == 422