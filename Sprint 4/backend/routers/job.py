"""
Owner: Job Posting Management
Routes:
  POST   /api/jobs              - a recruiter creates a posting
  GET    /api/jobs/mine         - the recruiter's own postings (open and closed)
  GET    /api/jobs/{id}         - one posting (open: any logged-in user; closed: owner only)
  PUT    /api/jobs/{id}         - edit a posting                 (owner only)
  POST   /api/jobs/{id}/close   - stop accepting applications    (owner only)
  POST   /api/jobs/{id}/reopen  - accept applications again      (owner only)
  DELETE /api/jobs/{id}         - remove a posting               (owner only)

Searching / filtering the open postings belongs to the Job Search feature and is not in this file.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Job, User
from routers.auth import get_current_user
from schemas import JobIn, JobOut

router = APIRouter()


def _require_recruiter(current_user: User) -> None:
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Only recruiters can manage job postings.")


def _get_owned_job(job_id: int, current_user: User, db: Session) -> Job:
    """
    Shared lookup + ownership check used by every "change a posting" route
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.recruiter_id != current_user.id:
        # Covers job seekers AND other recruiters.
        raise HTTPException(status_code=403, detail="You can only manage your own job postings.")
    return job


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/jobs — create a posting owned by the logged-in recruiter. Starts open."""
    _require_recruiter(current_user)
    # recruiter_id comes from the token, never from the request body.
    job = Job(recruiter_id=current_user.id, **payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# Declared BEFORE /jobs/{job_id}: FastAPI matches routes in order and
# "/jobs/mine" must not be read as a job id.
@router.get("/jobs/mine", response_model=list[JobOut])
def list_my_jobs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """GET /api/jobs/mine — every posting the recruiter created, newest first (Task 4.3's list)."""
    _require_recruiter(current_user)
    return (
        db.query(Job)
        .filter(Job.recruiter_id == current_user.id)
        .order_by(Job.id.desc())
        .all()
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    GET /api/jobs/{id} : one posting (job details page, or the edit form).
    A closed posting is only visible to its owner; to anyone else it looks
    like it doesn't exist (404) the same as it disappearing from search.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (not job.is_open and job.recruiter_id != current_user.id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.put("/jobs/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUT /api/jobs/{id} — replace the editable fields. Open/closed is changed with close/reopen."""
    job = _get_owned_job(job_id, current_user, db)
    for field, value in payload.model_dump().items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


def _set_open(job_id: int, is_open: bool, current_user: User, db: Session) -> Job:
    job = _get_owned_job(job_id, current_user, db)
    if job.is_open == is_open:
        state = "open" if is_open else "closed"
        raise HTTPException(status_code=400, detail=f"This job is already {state}.")
    job.is_open = is_open
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/close", response_model=JobOut)
def close_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """POST /api/jobs/{id}/close — hide from search and stop new applications; nothing is deleted."""
    return _set_open(job_id, False, current_user, db)


@router.post("/jobs/{job_id}/reopen", response_model=JobOut)
def reopen_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """POST /api/jobs/{id}/reopen — undo a close."""
    return _set_open(job_id, True, current_user, db)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """DELETE /api/jobs/{id} — permanently remove a posting."""
    job = _get_owned_job(job_id, current_user, db)
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully."}
