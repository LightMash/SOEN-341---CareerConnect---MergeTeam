"""
Owner: Resume upload feature.
"""

import datetime
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user
from models import User, Resume
from schemas import ResumeOut, ResumeUploadResponse

router = APIRouter()

# Folder next to backend/, not inside routers/ — easy to find, easy to gitignore.
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

# Maps each accepted content type to the file extension we expect it to have.
# Used both to validate an upload and to pick the right extension when we
# save the file under a random, collision-proof name (see _save_to_disk).
ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

MAX_UPLOAD_MB = 5


async def _read_valid_upload(file: UploadFile) -> tuple[bytes, str]:
    """
    Shared by upload and replace so both enforce the exact same rules.
    Rejects anything that isn't PDF/DOCX or is over the size limit, and
    returns (file bytes, extension to store it under).

    Nothing is written to disk here — a rejected file never changes anything,
    which is what lets "replace" validate first and delete the old file last.
    """
    # Reject anything that isn't PDF or DOCX.
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF or DOCX files are accepted (got {file.content_type}).",
        )

    contents = await file.read()

    # Reject anything over the size limit.
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max allowed is {MAX_UPLOAD_MB}MB.",
        )

    return contents, ALLOWED_CONTENT_TYPES[file.content_type]


def _save_to_disk(contents: bytes, extension: str) -> str:
    """
    Writes the bytes under a random unique name and returns the path.

    Random unique name on disk, correct extension for the file's real type
    (not trusting whatever extension the user's original filename had) —
    this avoids collisions between uploads and keeps storage safe.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    disk_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{extension}")
    with open(disk_path, "wb") as f:
        f.write(contents)
    return disk_path


@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Task 3.1 — POST /api/resume/upload
    Accepts PDF or DOCX, validates type and size, stores the file on disk
    and records it in the database. A user's FIRST resume automatically
    becomes their primary one, so they never have to set it manually.
    """
    contents, extension = await _read_valid_upload(file)
    disk_path = _save_to_disk(contents, extension)

    # Cheap existence check (selects only the id) — no resumes yet means this
    # one should be the primary.
    has_any = db.query(Resume.id).filter(Resume.user_id == current_user.id).first() is not None

    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        filepath=disk_path,
        is_primary=not has_any,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)  # reload so resume.id (auto-assigned by DB) is filled in

    return ResumeUploadResponse(message="Resume uploaded successfully", resume=resume)


@router.get("/resume/mine", response_model=list[ResumeOut])
def list_my_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Task 3.2 — GET /api/resume/mine: list every resume the logged-in user has uploaded.
    Newest first, ordered by id so the order is stable across refreshes (a
    replaced resume keeps its id, so it stays where it was).
    """
    return (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.id.desc())
        .all()
    )


def _get_owned_resume(resume_id: int, current_user: User, db: Session) -> Resume:
    """
    Shared lookup + ownership check used by download, replace, set-primary and delete.
    Keeping this in one place means the security check can't be
    accidentally skipped in one endpoint but not the others.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    # Block accessing/deleting someone else's resume by guessing/incrementing the ID.
    if resume.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to access this resume.")

    return resume


@router.put("/resume/{resume_id}", response_model=ResumeUploadResponse)
async def replace_resume(
    resume_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUT /api/resume/{id} — swap the file behind an existing resume.

    The row keeps its id and its primary status; only the file changes.
    The order of operations is deliberate so a failure can never lose the
    user's existing resume:
      1. ownership check
      2. validate the NEW file (nothing touched yet if it's rejected)
      3. write the new file, point the DB row at it, commit
      4. only then delete the old file from disk
    """
    resume = _get_owned_resume(resume_id, current_user, db)

    contents, extension = await _read_valid_upload(file)
    new_path = _save_to_disk(contents, extension)

    old_path = resume.filepath
    resume.filename = file.filename
    resume.filepath = new_path
    resume.uploaded_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(resume)

    # Safe to remove now: the database no longer points at the old file.
    if os.path.exists(old_path):
        os.remove(old_path)

    return ResumeUploadResponse(message="Resume replaced successfully", resume=resume)


@router.post("/resume/{resume_id}/primary", response_model=ResumeOut)
def set_primary_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    POST /api/resume/{id}/primary — make this the user's primary resume.
    "Only one primary at a time" is enforced here: clear the flag on every
    one of this user's resumes, then set it on the chosen one, in a single
    commit so there is never a moment with zero or two primaries.
    """
    resume = _get_owned_resume(resume_id, current_user, db)

    db.query(Resume).filter(
        Resume.user_id == current_user.id, Resume.is_primary.is_(True)
    ).update({"is_primary": False})
    resume.is_primary = True

    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resume/{resume_id}/download")
def download_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Task 3.3 — GET /api/resume/{id}/download
    Streams the actual file back to the caller, with its original filename
    so the browser's "Save As" dialog suggests the name the user uploaded it
    under (not the random UUID name it's stored as on disk).
    """
    resume = _get_owned_resume(resume_id, current_user, db)

    if not os.path.exists(resume.filepath):
        # The database row exists but the file itself is gone from disk —
        # shouldn't normally happen, but fail clearly instead of crashing.
        raise HTTPException(status_code=404, detail="File is missing from storage.")

    # Figure out the correct content type from the stored file's extension,
    # so the browser knows how to handle it (open a PDF viewer, offer to
    # open DOCX in Word, etc.) rather than guessing.
    extension = os.path.splitext(resume.filepath)[1]
    media_type = next(
        (ct for ct, ext in ALLOWED_CONTENT_TYPES.items() if ext == extension),
        "application/octet-stream",  # fallback: "just bytes", browser will prompt to save
    )

    return FileResponse(
        path=resume.filepath,
        filename=resume.filename,  # the name the browser will suggest when saving
        media_type=media_type,
    )


@router.delete("/resume/{resume_id}")
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Task 3.2 — DELETE /api/resume/{id}: remove one of the logged-in user's resumes."""
    resume = _get_owned_resume(resume_id, current_user, db)
    was_primary = resume.is_primary

    if os.path.exists(resume.filepath):
        os.remove(resume.filepath)

    db.delete(resume)
    db.commit()

    # If the primary resume was just deleted, promote the newest remaining one
    # so a user who still has resumes always has a primary (applications
    # depend on there being one to send).
    if was_primary:
        newest = (
            db.query(Resume)
            .filter(Resume.user_id == current_user.id)
            .order_by(Resume.id.desc())
            .first()
        )
        if newest:
            newest.is_primary = True
            db.commit()

    return {"message": "Resume deleted successfully"}
