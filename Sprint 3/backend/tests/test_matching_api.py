"""
Qualification matching and standing through the real API (local test database).
Routes live under /api/matching. `make_user()` makes job seekers,
`make_user(role="recruiter")` makes recruiters.
"""

import pytest

from database import SessionLocal
from matching.catalog import get_catalog
from matching.models import ListingRequirement
from matching.router import resolve_keys
from matching.rules import Requirement, evaluate

BASE = "/api/matching"
RESUME_BYTES = b"%PDF-1.4 fake resume content"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter")


def _create_job(client, recruiter, **overrides) -> int:
    body = {"title": "Backend Developer", "company": "Demo Co", **overrides}
    response = client.post("/api/jobs", json=body, headers=recruiter.headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _set_requirements(client, account, job_id, requirements):
    return client.put(
        f"{BASE}/listings/{job_id}/requirements",
        json={"requirements": requirements},
        headers=account.headers,
    )


def _set_quals(client, account, keys):
    return client.put(
        f"{BASE}/me/qualifications",
        json={"qualifications": [{"key": k} for k in keys]},
        headers=account.headers,
    )


def _apply(client, seeker, job_id):
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("cv.pdf", RESUME_BYTES, "application/pdf")},
        headers=seeker.headers,
    )
    assert upload.status_code == 200, upload.text
    response = client.post("/api/applications", json={"job_id": job_id}, headers=seeker.headers)
    assert response.status_code == 201, response.text


def _make_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with a real text layer (Helvetica)."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = "BT /F1 11 Tf 14 TL 50 750 Td " + " ".join(f"({esc(line)}) '" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


# ----------------------------------------------------------------------------
# Search and custom qualifications
# ----------------------------------------------------------------------------
def test_search_endpoint(client, user):
    response = client.get(
        f"{BASE}/qualifications/search", params={"q": "doctorate in computer science"}, headers=user.headers
    )
    assert response.status_code == 200
    assert response.json()[0]["name"] == "PhD — Computer Science"


def test_search_requires_login(client):
    assert client.get(f"{BASE}/qualifications/search", params={"q": "python"}).status_code == 401


def test_duplicate_custom_qualification_returns_existing(client, user, make_user):
    name = f"Forklift operator card {user.id}"
    first = client.post(f"{BASE}/qualifications/custom",
                        json={"category": "certification", "name": name}, headers=user.headers)
    assert first.status_code == 200, first.text
    assert first.json()["existing"] is False
    assert first.json()["key"].startswith("custom.")

    # Same name, different spacing / case / punctuation, different user.
    other = make_user()
    second = client.post(f"{BASE}/qualifications/custom",
                         json={"category": "certification", "name": f"  FORKLIFT operator card. {user.id} "},
                         headers=other.headers)
    assert second.status_code == 200
    assert second.json()["existing"] is True
    assert second.json()["key"] == first.json()["key"]


def test_custom_matching_a_catalog_alias_returns_the_catalog_entry(client, user):
    response = client.post(f"{BASE}/qualifications/custom",
                           json={"category": "skill", "name": "ReactJS"}, headers=user.headers)
    assert response.status_code == 200
    assert response.json() == {**response.json(), "key": "skill.react", "existing": True, "custom": False}


def test_custom_qualification_is_searchable(client, user):
    name = f"Zamboni driving {user.id}"
    created = client.post(f"{BASE}/qualifications/custom",
                          json={"category": "skill", "name": name}, headers=user.headers).json()
    hits = client.get(f"{BASE}/qualifications/search", params={"q": name}, headers=user.headers).json()
    assert hits[0]["key"] == created["key"] and hits[0]["custom"] is True


# ----------------------------------------------------------------------------
# The seeker's own qualifications
# ----------------------------------------------------------------------------
def test_seeker_sets_and_reads_qualifications(client, user):
    response = _set_quals(client, user, ["skill.python", "degree.bachelors.computer_science", "skill.python"])
    assert response.status_code == 200, response.text
    keys = [q["key"] for q in response.json()]
    assert sorted(keys) == ["degree.bachelors.computer_science", "skill.python"]

    assert len(client.get(f"{BASE}/me/qualifications", headers=user.headers).json()) == 2
    assert _set_quals(client, user, ["skill.docker"]).json()[0]["key"] == "skill.docker"
    assert len(client.get(f"{BASE}/me/qualifications", headers=user.headers).json()) == 1


def test_only_seekers_can_edit_qualifications(client, recruiter):
    assert _set_quals(client, recruiter, ["skill.python"]).status_code == 403
    assert client.get(f"{BASE}/me/qualifications", headers=recruiter.headers).status_code == 403
    assert client.post(f"{BASE}/me/qualifications/claim/skill.python", headers=recruiter.headers).status_code == 403


def test_unknown_key_is_rejected(client, user):
    assert _set_quals(client, user, ["skill.not_a_thing"]).status_code == 422
    assert _set_quals(client, user, ["custom.999999999"]).status_code == 422


def test_claim_adds_one_qualification(client, user):
    _set_quals(client, user, ["skill.python"])
    response = client.post(f"{BASE}/me/qualifications/claim/cert.whmis", headers=user.headers)
    assert response.status_code == 200
    assert {q["key"] for q in response.json()} == {"skill.python", "cert.whmis"}
    # Claiming twice is harmless.
    again = client.post(f"{BASE}/me/qualifications/claim/cert.whmis", headers=user.headers)
    assert len(again.json()) == 2


# ----------------------------------------------------------------------------
# Listing requirements
# ----------------------------------------------------------------------------
def test_only_the_listing_owner_can_set_requirements(client, recruiter, make_user, user):
    job_id = _create_job(client, recruiter)
    reqs = [{"key": "skill.python", "is_required": True},
            {"key": "skill.docker", "is_required": False, "weight": 3}]

    assert _set_requirements(client, make_user(role="recruiter"), job_id, reqs).status_code == 403
    assert _set_requirements(client, user, job_id, reqs).status_code == 403

    response = _set_requirements(client, recruiter, job_id, reqs)
    assert response.status_code == 200, response.text
    saved = {r["key"]: r for r in response.json()}
    assert saved["skill.python"]["is_required"] is True and saved["skill.python"]["weight"] == 1
    assert saved["skill.docker"]["weight"] == 3

    # Anyone who can see the listing can read them.
    assert len(client.get(f"{BASE}/listings/{job_id}/requirements", headers=user.headers).json()) == 2


def test_requirement_validation(client, recruiter):
    job_id = _create_job(client, recruiter)
    bad_weight = [{"key": "skill.python", "is_required": False, "weight": 4}]
    duplicate = [{"key": "skill.python"}, {"key": "skill.python"}]
    unknown = [{"key": "skill.nope"}]
    for body in (bad_weight, duplicate, unknown):
        assert _set_requirements(client, recruiter, job_id, body).status_code == 422
    assert _set_requirements(client, recruiter, 999999999, []).status_code == 404


def test_closed_listing_requirements_hidden_from_others(client, recruiter, user):
    job_id = _create_job(client, recruiter)
    _set_requirements(client, recruiter, job_id, [{"key": "skill.python"}])
    client.post(f"/api/jobs/{job_id}/close", headers=recruiter.headers)
    assert client.get(f"{BASE}/listings/{job_id}/requirements", headers=user.headers).status_code == 404
    assert client.get(f"{BASE}/listings/{job_id}/requirements", headers=recruiter.headers).status_code == 200


def test_deleting_a_job_removes_its_requirements(client, recruiter):
    job_id = _create_job(client, recruiter)
    _set_requirements(client, recruiter, job_id, [{"key": "skill.python"}])
    assert client.delete(f"/api/jobs/{job_id}", headers=recruiter.headers).status_code == 200
    db = SessionLocal()
    try:
        assert db.query(ListingRequirement).filter(ListingRequirement.listing_id == job_id).count() == 0
    finally:
        db.close()


# ----------------------------------------------------------------------------
# Match
# ----------------------------------------------------------------------------
def test_match_agrees_with_evaluate(client, recruiter, user):
    job_a = _create_job(client, recruiter, title="A")
    job_b = _create_job(client, recruiter, title="B")
    job_c = _create_job(client, recruiter, title="C")  # no requirements
    reqs_a = [{"key": "degree.bachelors.any"}, {"key": "skill.python"},
              {"key": "skill.docker", "is_required": False, "weight": 2}]
    reqs_b = [{"key": "degree.phd.computer_science"}, {"key": "skill.aws", "is_required": False}]
    _set_requirements(client, recruiter, job_a, reqs_a)
    _set_requirements(client, recruiter, job_b, reqs_b)
    mine = ["degree.masters.computer_science", "skill.python"]
    _set_quals(client, user, mine)

    response = client.post(f"{BASE}/match", json=[job_a, job_b, job_c, 999999999], headers=user.headers)
    assert response.status_code == 200, response.text
    results = {r["listing_id"]: r for r in response.json()}
    assert set(results) == {job_a, job_b, job_c}  # unknown id left out

    db = SessionLocal()
    try:
        seeker_quals = list(resolve_keys(mine, db).values())
        for job_id, reqs in ((job_a, reqs_a), (job_b, reqs_b), (job_c, [])):
            resolved = resolve_keys([r["key"] for r in reqs], db)
            requirements = [
                Requirement(resolved[r["key"]], r.get("is_required", True),
                            r.get("weight", 1) if not r.get("is_required", True) else 1)
                for r in reqs
            ]
            expected = evaluate(requirements, seeker_quals, get_catalog().implies)
            got = results[job_id]
            assert got["qualified"] == expected.qualified
            assert {i["key"]: (i["status"], i["exceeds"]) for i in got["requirements"]} == {
                i.key: (i.status, i.exceeds) for i in expected.items
            }
    finally:
        db.close()

    assert results[job_a]["qualified"] is True
    assert results[job_b]["qualified"] is False
    assert results[job_c]["qualified"] is True


def test_match_limits(client, user, recruiter):
    assert client.post(f"{BASE}/match", json=list(range(1, 102)), headers=user.headers).status_code == 422
    assert client.post(f"{BASE}/match", json=[], headers=user.headers).json() == []
    assert client.post(f"{BASE}/match", json=[1], headers=recruiter.headers).status_code == 403


def test_possible_match_and_claim(client, recruiter, user):
    job_id = _create_job(client, recruiter)
    _set_requirements(client, recruiter, job_id, [{"key": "cert.whmis"}])
    # A misspelled custom entry: close to the WHMIS alias, but not verified.
    custom = client.post(f"{BASE}/qualifications/custom",
                         json={"category": "certification", "name": "WHMISS"},
                         headers=user.headers).json()
    assert custom["custom"] is True
    _set_quals(client, user, [custom["key"]])

    item = client.post(f"{BASE}/match", json=[job_id], headers=user.headers).json()[0]["requirements"][0]
    assert item["status"] == "possible"
    assert item["possible_name"] == "WHMISS"

    client.post(f"{BASE}/me/qualifications/claim/cert.whmis", headers=user.headers)
    result = client.post(f"{BASE}/match", json=[job_id], headers=user.headers).json()[0]
    assert result["qualified"] is True and result["requirements"][0]["status"] == "met"


# ----------------------------------------------------------------------------
# Standing, end to end
# ----------------------------------------------------------------------------
def test_standing_end_to_end(client, recruiter, make_user):
    job_id = _create_job(client, recruiter)
    _set_requirements(client, recruiter, job_id, [
        {"key": "skill.python"},
        {"key": "skill.docker", "is_required": False, "weight": 2},
        {"key": "skill.aws", "is_required": False, "weight": 1},
    ])

    # Five other applicants (scores 0, 1, 2, 3, 3) plus one who isn't qualified.
    pools = [["skill.python"], ["skill.python", "skill.aws"], ["skill.python", "skill.docker"],
             ["skill.python", "skill.docker", "skill.aws"], ["skill.python", "skill.docker", "skill.aws"],
             ["skill.docker"]]
    for keys in pools:
        applicant = make_user()
        _set_quals(client, applicant, keys)
        _apply(client, applicant, job_id)

    seeker = make_user()  # has not applied; still counted exactly once
    _set_quals(client, seeker, ["skill.python", "skill.docker"])
    response = client.get(f"{BASE}/listings/{job_id}/standing", headers=seeker.headers)
    assert response.status_code == 200, response.text
    standing = response.json()
    assert standing["status"] == "percentile"
    assert standing["pool_size"] == 6 and standing["other_applicants"] == 5
    assert standing["percentile"] == 50 and standing["label"] == "Competitive"
    assert standing["suggestions"][0]["key"] == "skill.aws"
    assert standing["note"].startswith("Based only on listed qualifications")

    # Applying doesn't count the seeker twice.
    _apply(client, seeker, job_id)
    again = client.get(f"{BASE}/listings/{job_id}/standing", headers=seeker.headers).json()
    assert again["pool_size"] == 6 and again["percentile"] == 50


def test_standing_not_qualified_and_permissions(client, recruiter, user):
    job_id = _create_job(client, recruiter)
    _set_requirements(client, recruiter, job_id, [{"key": "skill.python"}])
    standing = client.get(f"{BASE}/listings/{job_id}/standing", headers=user.headers).json()
    assert standing["status"] == "not_qualified"
    assert standing["missing"][0]["key"] == "skill.python"
    assert client.get(f"{BASE}/listings/{job_id}/standing", headers=recruiter.headers).status_code == 403
    assert client.get(f"{BASE}/listings/999999999/standing", headers=user.headers).status_code == 404


# ----------------------------------------------------------------------------
# Resume import
# ----------------------------------------------------------------------------
RESUME_LINES = [
    "EDUCATION",
    "Bachelor of Science in Computer Science, 2018 - 2022",
    "SKILLS",
    "Python, Docker, Go",
]


def test_extract_from_uploaded_pdf(client, user):
    _set_quals(client, user, ["skill.python"])
    response = client.post(
        f"{BASE}/me/qualifications/extract",
        files={"file": ("cv.pdf", _make_pdf(RESUME_LINES), "application/pdf")},
        headers=user.headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    found = {c["key"]: c for c in body["candidates"]}
    assert {"degree.bachelors.computer_science", "skill.python", "skill.docker", "skill.go"} <= set(found)
    assert found["skill.python"]["already_added"] is True
    assert found["skill.docker"]["state"] == "found" and found["skill.docker"]["source"] == "scan"
    assert body["reviewer_enabled"] is False
    # Nothing was saved.
    assert len(client.get(f"{BASE}/me/qualifications", headers=user.headers).json()) == 1


def test_extract_from_saved_resume(client, user):
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("cv.pdf", _make_pdf(RESUME_LINES), "application/pdf")},
        headers=user.headers,
    ).json()["resume"]
    response = client.post(f"{BASE}/me/qualifications/extract", data={"resume_id": upload["id"]},
                           headers=user.headers)
    assert response.status_code == 200, response.text
    assert "skill.docker" in {c["key"] for c in response.json()["candidates"]}


def test_extract_without_text_layer(client, user):
    response = client.post(
        f"{BASE}/me/qualifications/extract",
        files={"file": ("scan.pdf", RESUME_BYTES, "application/pdf")},
        headers=user.headers,
    )
    assert response.status_code == 200
    assert response.json()["candidates"] == []
    assert "search box" in response.json()["message"]


def test_extract_validation(client, user, make_user):
    url = f"{BASE}/me/qualifications/extract"
    assert client.post(url, headers=user.headers).status_code == 400
    not_pdf = client.post(url, files={"file": ("a.txt", b"hello", "text/plain")}, headers=user.headers)
    assert not_pdf.status_code == 400
    upload = client.post("/api/resume/upload", files={"file": ("cv.pdf", RESUME_BYTES, "application/pdf")},
                         headers=user.headers).json()["resume"]
    other = make_user()
    assert client.post(url, data={"resume_id": upload["id"]}, headers=other.headers).status_code == 403


def test_reviewer_is_off_by_default(client, user):
    assert client.get(f"{BASE}/reviewer", headers=user.headers).json() == {"enabled": False}
