"""
Automated tests for Resume Management.
Covers: upload, list, replace, set primary, download, delete, and ownership rules.
Endpoints: /api/resume/upload, /api/resume/mine, /api/resume/{id}[/primary|/download]

The `user` fixture is a logged-in job seeker; `make_user()` creates extra users.
Files are written to a temporary folder (see conftest.py), never to backend/uploads/.
"""

import os

# The two content types the API accepts, and some fake-but-valid file contents.
# The API only checks the declared type and the size, not the file's internals.
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_BYTES = b"%PDF-1.4 fake resume content"
DOCX_BYTES = b"PK fake docx content"


def _upload(client, user, name="resume.pdf", content=PDF_BYTES, content_type=PDF):
    """Upload a file as `user` and return the raw response."""
    return client.post(
        "/api/resume/upload",
        files={"file": (name, content, content_type)},
        headers=user.headers,
    )


def _upload_ok(client, user, **kwargs) -> dict:
    """Upload and assert it worked; returns the resume as a dict (id, filename, is_primary...)."""
    response = _upload(client, user, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()["resume"]


def _mine(client, user) -> list:
    """The logged-in user's resume list."""
    return client.get("/api/resume/mine", headers=user.headers).json()


# ----------------------------------------------------------------------------
# Upload
# ----------------------------------------------------------------------------
def test_upload_pdf(client, user):
    response = _upload(client, user, name="my_cv.pdf")

    assert response.status_code == 200
    resume = response.json()["resume"]
    assert resume["filename"] == "my_cv.pdf"
    assert resume["user_id"] == user.id
    assert "filepath" not in resume                  # server paths are never exposed


def test_upload_docx(client, user):
    response = _upload(client, user, name="cv.docx", content=DOCX_BYTES, content_type=DOCX)

    assert response.status_code == 200
    assert response.json()["resume"]["filename"] == "cv.docx"


def test_upload_saves_file_to_disk(client, user, upload_dir):
    _upload_ok(client, user)

    assert len(os.listdir(upload_dir)) == 1


def test_first_resume_becomes_primary_second_does_not(client, user):
    first = _upload_ok(client, user, name="first.pdf")
    second = _upload_ok(client, user, name="second.pdf")

    assert first["is_primary"] is True
    assert second["is_primary"] is False


def test_upload_rejects_wrong_file_type(client, user):
    response = _upload(client, user, name="notes.txt", content=b"hello", content_type="text/plain")

    assert response.status_code == 400
    assert _mine(client, user) == []                 # nothing was stored


def test_upload_rejects_file_over_5mb(client, user, upload_dir):
    too_big = b"0" * (5 * 1024 * 1024 + 1)

    response = _upload(client, user, content=too_big)

    assert response.status_code == 400
    assert not upload_dir.exists() or os.listdir(upload_dir) == []   # nothing written


def test_upload_accepts_file_just_under_5mb(client, user):
    just_under = b"0" * (5 * 1024 * 1024 - 1024)

    assert _upload(client, user, content=just_under).status_code == 200


def test_upload_requires_login(client):
    response = client.post("/api/resume/upload", files={"file": ("a.pdf", PDF_BYTES, PDF)})

    assert response.status_code == 401


# ----------------------------------------------------------------------------
# List
# ----------------------------------------------------------------------------
def test_list_is_empty_for_new_user(client, user):
    assert _mine(client, user) == []


def test_list_returns_newest_first(client, user):
    older = _upload_ok(client, user, name="older.pdf")
    newer = _upload_ok(client, user, name="newer.pdf")

    ids = [r["id"] for r in _mine(client, user)]

    assert ids == [newer["id"], older["id"]]


def test_list_only_shows_my_own_resumes(client, user, make_user):
    other = make_user()
    mine = _upload_ok(client, user, name="mine.pdf")
    _upload_ok(client, other, name="theirs.pdf")

    ids = [r["id"] for r in _mine(client, user)]

    assert ids == [mine["id"]]


def test_list_requires_login(client):
    assert client.get("/api/resume/mine").status_code == 401


# ----------------------------------------------------------------------------
# Replace (PUT /api/resume/{id})
# ----------------------------------------------------------------------------
def test_replace_keeps_id_and_primary_but_changes_file(client, user, upload_dir):
    original = _upload_ok(client, user, name="old.pdf")

    response = client.put(
        f"/api/resume/{original['id']}",
        files={"file": ("new.pdf", b"%PDF-1.4 new content", PDF)},
        headers=user.headers,
    )

    assert response.status_code == 200
    replaced = response.json()["resume"]
    assert replaced["id"] == original["id"]          # same row
    assert replaced["is_primary"] is True            # primary status is kept
    assert replaced["filename"] == "new.pdf"         # file changed
    assert len(os.listdir(upload_dir)) == 1          # the old file was deleted from disk


def test_replace_with_invalid_file_keeps_original(client, user):
    original = _upload_ok(client, user, name="keep.pdf")

    response = client.put(
        f"/api/resume/{original['id']}",
        files={"file": ("bad.txt", b"nope", "text/plain")},
        headers=user.headers,
    )

    assert response.status_code == 400
    assert _mine(client, user)[0]["filename"] == "keep.pdf"      # unchanged
    download = client.get(f"/api/resume/{original['id']}/download", headers=user.headers)
    assert download.status_code == 200                           # file still there


# ----------------------------------------------------------------------------
# Primary resume (POST /api/resume/{id}/primary)
# ----------------------------------------------------------------------------
def test_set_primary_switches_the_flag(client, user):
    first = _upload_ok(client, user, name="first.pdf")
    second = _upload_ok(client, user, name="second.pdf")

    response = client.post(f"/api/resume/{second['id']}/primary", headers=user.headers)

    assert response.status_code == 200
    by_id = {r["id"]: r for r in _mine(client, user)}
    assert by_id[second["id"]]["is_primary"] is True
    assert by_id[first["id"]]["is_primary"] is False             # only ONE primary at a time


# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------
def test_download_returns_same_bytes_and_original_name(client, user):
    resume = _upload_ok(client, user, name="Alice CV.pdf", content=PDF_BYTES)

    response = client.get(f"/api/resume/{resume['id']}/download", headers=user.headers)

    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert "Alice" in response.headers["content-disposition"]    # browser "Save as" name
    assert response.headers["content-type"].startswith("application/pdf")


# ----------------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------------
def test_delete_removes_resume_and_file(client, user, upload_dir):
    resume = _upload_ok(client, user)

    response = client.delete(f"/api/resume/{resume['id']}", headers=user.headers)

    assert response.status_code == 200
    assert _mine(client, user) == []
    assert os.listdir(upload_dir) == []                          # file gone from disk
    gone = client.get(f"/api/resume/{resume['id']}/download", headers=user.headers)
    assert gone.status_code == 404


def test_deleting_primary_promotes_newest_remaining(client, user):
    primary = _upload_ok(client, user, name="primary.pdf")
    _upload_ok(client, user, name="middle.pdf")
    newest = _upload_ok(client, user, name="newest.pdf")

    client.delete(f"/api/resume/{primary['id']}", headers=user.headers)

    remaining = {r["id"]: r for r in _mine(client, user)}
    assert remaining[newest["id"]]["is_primary"] is True


# ----------------------------------------------------------------------------
# Ownership & errors: nobody may touch someone else's resume
# ----------------------------------------------------------------------------
def test_other_users_cannot_access_my_resume(client, user, make_user):
    intruder = make_user()
    resume = _upload_ok(client, user)
    url = f"/api/resume/{resume['id']}"

    assert client.get(f"{url}/download", headers=intruder.headers).status_code == 403
    assert client.delete(url, headers=intruder.headers).status_code == 403
    assert client.post(f"{url}/primary", headers=intruder.headers).status_code == 403
    replace = client.put(url, files={"file": ("x.pdf", PDF_BYTES, PDF)}, headers=intruder.headers)
    assert replace.status_code == 403
    # ...and the owner's resume is untouched.
    assert len(_mine(client, user)) == 1


def test_unknown_resume_id_returns_404(client, user):
    assert client.get("/api/resume/999999999/download", headers=user.headers).status_code == 404
    assert client.delete("/api/resume/999999999", headers=user.headers).status_code == 404


def test_download_delete_require_login(client, user):
    resume = _upload_ok(client, user)

    assert client.get(f"/api/resume/{resume['id']}/download").status_code == 401
    assert client.delete(f"/api/resume/{resume['id']}").status_code == 401
