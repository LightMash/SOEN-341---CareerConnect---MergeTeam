"""
Owner: Resume upload feature.
"""

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
# save the file under a random, collision-proof name (see upload_resume).
ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

MAX_UPLOAD_MB = 5


@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Task 3.1 — POST /api/resume/upload
    Accepts PDF or DOCX, validates type and size, stores the file on disk
    and records it in the database.
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

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Random unique name on disk, correct extension for the file's real type
    # (not trusting whatever extension the user's original filename had) —
    # this avoids collisions between uploads and keeps storage safe.
    extension = ALLOWED_CONTENT_TYPES[file.content_type]
    unique_filename = f"{uuid.uuid4()}{extension}"
    disk_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(disk_path, "wb") as f:
        f.write(contents)

    resume = Resume(user_id=current_user.id, filename=file.filename, filepath=disk_path)
    db.add(resume)
    db.commit()
    db.refresh(resume)  # reload so resume.id (auto-assigned by DB) is filled in

    return ResumeUploadResponse(message="Resume uploaded successfully", resume=resume)


@router.get("/resume/mine", response_model=list[ResumeOut])
def list_my_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Task 3.2 — GET /api/resume/mine: list every resume the logged-in user has uploaded."""
    return db.query(Resume).filter(Resume.user_id == current_user.id).all()


def _get_owned_resume(resume_id: int, current_user: User, db: Session) -> Resume:
    """
    Shared lookup + ownership check used by both download and delete.
    Keeping this in one place means the security check can't be
    accidentally skipped in one endpoint but not the other.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    # Block accessing/deleting someone else's resume by guessing/incrementing the ID.
    if resume.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to access this resume.")

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

    if os.path.exists(resume.filepath):
        os.remove(resume.filepath)

    db.delete(resume)
    db.commit()
    return {"message": "Resume deleted successfully"}