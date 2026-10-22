"""
Owner: Job Application feature
  POST /api/applications        - a job seeker applies to a job
  GET  /api/applications/mine   - the logged-in job seeker's applications + statuses
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Application, Job, Resume, User
from routers.auth import get_current_user
from schemas import ApplicationCreate, ApplicationOut, ApplicationSubmitResponse

router = APIRouter()

DUPLICATE_MESSAGE = "You have already applied to this job."


def _require_job_seeker(current_user: User) -> None:
    if current_user.role != "job_seeker":
        raise HTTPException(status_code=403, detail="Only job seekers can apply to jobs.")


def _pick_resume(resume_id: int | None, current_user: User, db: Session) -> Resume:
    """
    The resume to send with the application:
      - the one the job seeker selected, if they selected one (must be theirs)
      - otherwise their primary resume
    A job seeker with no resume at all cannot apply.
    """
    if resume_id is not None:
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found.")
        if resume.user_id != current_user.id:
            # Same rule as routers/resume.py: you can't use someone else's resume.
            raise HTTPException(status_code=403, detail="You don't have permission to use this resume.")
        return resume

    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id, Resume.is_primary.is_(True))
        .first()
    )
    if not resume:
        raise HTTPException(status_code=400, detail="Upload a resume before applying to jobs.")
    return resume


def _to_out(application: Application) -> ApplicationOut:
    # Built by hand because job_title / company / resume_filename come from
    # the related rows, not from the applications table itself.
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        job_title=application.job.title,
        company=application.job.company,
        resume_id=application.resume_id,
        resume_filename=application.resume.filename if application.resume else None,
        status=application.status,
        applied_at=application.applied_at,
        updated_at=application.updated_at,
    )


@router.post(
    "/applications",
    response_model=ApplicationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_application(
    payload: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    POST /api/applications
    Checks, in order: job seeker? -> job exists? -> job open? -> already applied?
    -> valid resume? Then saves the application with status "Applied".
    """
    _require_job_seeker(current_user)

    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.is_open:
        raise HTTPException(status_code=400, detail="This job is no longer accepting applications.")

    # early check so the user gets a clear message in the normal case
    already_applied = (
        db.query(Application.id)
        .filter(Application.job_id == job.id, Application.applicant_id == current_user.id)
        .first()
    )
    if already_applied:
        raise HTTPException(status_code=409, detail=DUPLICATE_MESSAGE)

    resume = _pick_resume(payload.resume_id, current_user, db)

    application = Application(job_id=job.id, applicant_id=current_user.id, resume_id=resume.id)
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        # Two requests at the same moment (like a double-click) can both passthe check above
        db.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_MESSAGE)
    db.refresh(application)

    return ApplicationSubmitResponse(
        message="Application submitted successfully.",
        application=_to_out(application),
    )


@router.get("/applications/mine", response_model=list[ApplicationOut])
def list_my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/applications/mine — every application the job seeker submitted, newest first."""
    _require_job_seeker(current_user)
    applications = (
        db.query(Application)
        .filter(Application.applicant_id == current_user.id)
        .order_by(Application.id.desc())
        .all()
    )
    return [_to_out(a) for a in applications]