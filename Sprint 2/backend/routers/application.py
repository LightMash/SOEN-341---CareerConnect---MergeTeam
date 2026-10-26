"""
Owner: Job Application feature
Routes:
  POST  /api/applications                - Task 6.2: a job seeker applies to a job
  GET   /api/applications/mine           - the logged-in job seeker's applications + statuses
  GET   /api/jobs/{job_id}/applications  - backend: a recruiter's applicants for one posting
  PATCH /api/applications/{id}/status    - the posting's recruiter changes the status
  GET   /api/applications/{id}/history   - status timeline (applicant or recruiter)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Application, ApplicationStatusHistory, Job, Resume, User
from routers.auth import get_current_user
from schemas import (
    ApplicantOut,
    ApplicationCreate,
    ApplicationOut,
    ApplicationSubmitResponse,
    StatusChangeOut,
    StatusUpdate,
)

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


def _common_fields(application: Application) -> dict:
    # Built by hand because job_title / company / resume_filename come from
    # the related rows, not from the applications table itself.
    return dict(
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


def _to_out(application: Application) -> ApplicationOut:
    """The job seeker's view of their own application."""
    return ApplicationOut(**_common_fields(application))


def _to_applicant_out(application: Application) -> ApplicantOut:
    """The recruiter's view: the same fields plus who applied."""
    return ApplicantOut(
        **_common_fields(application),
        applicant_id=application.applicant_id,
        applicant_name=application.applicant.full_name,
        applicant_email=application.applicant.email,
    )


def _get_application(application_id: int, db: Session) -> Application:
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")
    return application


def _is_posting_recruiter(application: Application, user: User) -> bool:
    """True only for the recruiter who posted the job this application is for."""
    return user.role == "recruiter" and application.job.recruiter_id == user.id


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
    # First timeline entry: Saved in the SAME commit as the application
    # so there is never an application without its history
    application.history.append(
        ApplicationStatusHistory(old_status=None, new_status="Applied", changed_by=current_user.id)
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        # Two requests at the same moment (like a double-click) can both pass the check above
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


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------
@router.get("/jobs/{job_id}/applications", response_model=list[ApplicantOut])
def list_job_applications(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GET /api/jobs/{job_id}/applications — everyone who applied to one posting,
    oldest first. Only the recruiter who posted the job may see this list.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if current_user.role != "recruiter" or job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the recruiter who posted this job can see its applicants.")

    applications = (
        db.query(Application)
        .filter(Application.job_id == job.id)
        .order_by(Application.id.asc())
        .all()
    )
    return [_to_applicant_out(a) for a in applications]


@router.patch("/applications/{application_id}/status", response_model=ApplicantOut)
def update_application_status(
    application_id: int,
    payload: StatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PATCH /api/applications/{id}/status  body: {"status": "Interview"}

    Restricted to the recruiter who posted the job: job seekers (including the
    applicant) and other recruiters get 403. An invalid status never reaches
    this function (StatusUpdate rejects it with 422).

    The status change and its history entry are saved in one commit.
    """
    application = _get_application(application_id, db)
    if not _is_posting_recruiter(application, current_user):
        raise HTTPException(
            status_code=403,
            detail="Only the recruiter who posted this job can update the application status.",
        )

    if payload.status == application.status:
        raise HTTPException(status_code=400, detail=f"Application is already '{application.status}'.")

    application.history.append(
        ApplicationStatusHistory(
            old_status=application.status,
            new_status=payload.status,
            changed_by=current_user.id,
        )
    )
    application.status = payload.status
    db.commit()
    db.refresh(application)
    return _to_applicant_out(application)


@router.get("/applications/{application_id}/history", response_model=list[StatusChangeOut])
def get_application_history(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GET /api/applications/{id}/history: every status change with
    its timestamp, oldest first. Visible to the applicant and to the
    recruiter who posted the job; anyone else gets 403.
    """
    application = _get_application(application_id, db)
    is_applicant = application.applicant_id == current_user.id
    if not (is_applicant or _is_posting_recruiter(application, current_user)):
        raise HTTPException(status_code=403, detail="You don't have permission to view this application.")

    return application.history
