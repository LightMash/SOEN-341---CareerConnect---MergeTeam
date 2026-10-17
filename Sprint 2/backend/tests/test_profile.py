"""
Automated tests for the User Profile feature (part of Profile & Resume Management).
Covers: GET/PUT /api/profile/me and the profile photo endpoints /api/profile/photo.

Note: /api/profile (no "/me") belongs to login and is tested in test_auth.py.
"""

# The first bytes of a real PNG file. The API checks these "magic numbers"
# rather than trusting the filename, so this is enough to count as a PNG.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake image body"

# A complete, valid profile form (what the frontend sends on "Save").
VALID_PROFILE = {
    "headline": "Junior Developer",
    "location": "Montreal, QC",
    "phone": "+1 (514) 555-0100",
    "summary": "Software engineering student.",
    "skills": ["Python", "React"],
    "education": [{"school": "Concordia University", "degree": "BEng", "start_year": 2023, "end_year": 2027}],
    "experience": [{"company": "Acme", "title": "Intern", "description": "Built things", "start_year": 2025}],
    "linkedin_url": "https://linkedin.com/in/example",
    "github_url": "https://github.com/example",
    "portfolio_url": "",
}


# ----------------------------------------------------------------------------
# Reading and editing the profile
# ----------------------------------------------------------------------------
def test_new_profile_is_empty_and_zero_percent_complete(client, user):
    response = client.get("/api/profile/me", headers=user.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == user.id
    assert body["headline"] == ""
    assert body["skills"] == []
    assert body["completeness"] == 0
    assert body["missing"] == ["Headline", "Location", "Skills", "Education", "Resume"]


def test_update_profile_saves_and_returns_values(client, user):
    response = client.put("/api/profile/me", json=VALID_PROFILE, headers=user.headers)

    assert response.status_code == 200
    saved = response.json()
    assert saved["headline"] == "Junior Developer"
    assert saved["skills"] == ["Python", "React"]
    assert saved["education"][0]["school"] == "Concordia University"
    # And it really persisted: a fresh GET sees the same data.
    again = client.get("/api/profile/me", headers=user.headers).json()
    assert again["headline"] == "Junior Developer"


def test_completeness_rises_as_sections_are_filled(client, user):
    # Headline, location, skills and education filled = 4 of 5 sections (80%).
    saved = client.put("/api/profile/me", json=VALID_PROFILE, headers=user.headers).json()
    assert saved["completeness"] == 80
    assert saved["missing"] == ["Resume"]

    # Uploading a resume completes the last section.
    client.post(
        "/api/resume/upload",
        files={"file": ("cv.pdf", b"%PDF-1.4 x", "application/pdf")},
        headers=user.headers,
    )
    assert client.get("/api/profile/me", headers=user.headers).json()["completeness"] == 100


def test_skills_are_trimmed_and_deduplicated(client, user):
    payload = {**VALID_PROFILE, "skills": ["  Python ", "python", "", "React"]}

    response = client.put("/api/profile/me", json=payload, headers=user.headers)

    assert response.json()["skills"] == ["Python", "React"]


def test_profile_can_be_cleared_by_sending_empty_values(client, user):
    client.put("/api/profile/me", json=VALID_PROFILE, headers=user.headers)

    response = client.put("/api/profile/me", json={"headline": ""}, headers=user.headers)

    assert response.json()["headline"] == ""
    assert response.json()["skills"] == []


# Each case is one invalid form; every one must be rejected with 422 and
# must NOT change the saved profile.
def test_invalid_profile_input_is_rejected(client, user):
    bad_inputs = [
        {"phone": "call me maybe"},                                  # letters in phone
        {"github_url": "javascript:alert(1)"},                       # unsafe link
        {"linkedin_url": "ftp://example.com"},                       # only http(s) allowed
        {"education": [{"school": "   "}]},                          # blank school name
        {"experience": [{"company": "Acme"}]},                       # missing job title
        {"education": [{"school": "X", "start_year": 1800}]},        # year out of range
    ]
    client.put("/api/profile/me", json=VALID_PROFILE, headers=user.headers)

    for bad in bad_inputs:
        response = client.put("/api/profile/me", json={**VALID_PROFILE, **bad}, headers=user.headers)
        assert response.status_code == 422, f"should have rejected {bad}"

    assert client.get("/api/profile/me", headers=user.headers).json()["headline"] == "Junior Developer"


def test_profile_requires_login(client):
    assert client.get("/api/profile/me").status_code == 401
    assert client.put("/api/profile/me", json=VALID_PROFILE).status_code == 401


def test_recruiters_have_no_job_seeker_profile(client, make_user):
    recruiter = make_user(role="recruiter")

    assert client.get("/api/profile/me", headers=recruiter.headers).status_code == 403
    assert client.put("/api/profile/me", json=VALID_PROFILE, headers=recruiter.headers).status_code == 403


def test_each_user_has_their_own_profile(client, user, make_user):
    other = make_user()
    client.put("/api/profile/me", json=VALID_PROFILE, headers=user.headers)

    assert client.get("/api/profile/me", headers=other.headers).json()["headline"] == ""


# ----------------------------------------------------------------------------
# Profile photo
# ----------------------------------------------------------------------------
def test_no_photo_returns_204(client, user):
    assert client.get("/api/profile/photo", headers=user.headers).status_code == 204


def test_upload_then_fetch_photo(client, user):
    upload = client.put("/api/profile/photo", files={"file": ("me.png", PNG_BYTES, "image/png")}, headers=user.headers)
    assert upload.status_code == 200

    fetched = client.get("/api/profile/photo", headers=user.headers)

    assert fetched.status_code == 200
    assert fetched.content == PNG_BYTES
    assert fetched.headers["content-type"] == "image/png"


def test_photo_must_really_be_an_image(client, user):
    # Named .png and labelled image/png, but the bytes are plain text -> rejected.
    fake = client.put("/api/profile/photo", files={"file": ("me.png", b"just text", "image/png")}, headers=user.headers)

    assert fake.status_code == 400


def test_photo_over_2mb_is_rejected(client, user):
    big = PNG_BYTES + b"0" * (2 * 1024 * 1024)

    response = client.put("/api/profile/photo", files={"file": ("big.png", big, "image/png")}, headers=user.headers)

    assert response.status_code == 400


def test_delete_photo(client, user):
    client.put("/api/profile/photo", files={"file": ("me.png", PNG_BYTES, "image/png")}, headers=user.headers)

    assert client.delete("/api/profile/photo", headers=user.headers).status_code == 200
    assert client.get("/api/profile/photo", headers=user.headers).status_code == 204


def test_recruiters_can_have_a_photo(client, make_user):
    recruiter = make_user(role="recruiter")

    response = client.put("/api/profile/photo", files={"file": ("me.png", PNG_BYTES, "image/png")}, headers=recruiter.headers)

    assert response.status_code == 200
