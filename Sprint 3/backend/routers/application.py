"""
Owner: Job Application feature
Routes:
  POST  /api/applications                - Task 6.2: a job seeker applies to a job
  GET   /api/applications/mine           - the logged-in job seeker's applications + statuses
  GET   /api/jobs/{job_id}/applications  - backend: a recruiter's applicants for one posting
  PATCH /api/applications/{id}/status    - the posting's recruiter changes the status
  GET   /api/applications/{id}/history   - status timeline (applicant or recruiter)
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, literal_column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Application, ApplicationStatusHistory, Job, Resume, User
from models.application import APPLICATION_STATUSES
from routers.auth import get_current_user
from schemas import (
    ApplicantOut,
    ApplicationCreate,
    ApplicationOut,
    ApplicationStatsOut,
    ApplicationSubmitResponse,
    PeriodCount,
    StatusChangeOut,
    StatusUpdate,
)
from services.notifications import notify_new_application, notify_status_change

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
        location=application.job.location,
        job_type=application.job.job_type,
        work_from=application.job.work_from,
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
        # flush() sends the INSERT now (so a duplicate is caught here and the
        # application gets its id) without ending the transaction yet.
        db.flush()
        # US-09: tell the recruiter. Staged in the SAME commit as the
        # application, so one can't exist without the other.
        notify_new_application(db, application, job, current_user)
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
    # US-09: tell the job seeker (an "interview invitation" when the new
    # status is Interview). Same commit as the status change itself.
    notify_status_change(db, application, payload.status)
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


# ---------------------------------------------------------------------------
# Dashboard statistics (US-08)
# ---------------------------------------------------------------------------
WEEKS_SHOWN = 10
MONTHS_SHOWN = 12


def _week_starts(today: datetime.date) -> list[datetime.date]:
    """Mondays of the last WEEKS_SHOWN weeks, oldest first, ending with this week's Monday."""
    this_monday = today - datetime.timedelta(days=today.weekday())
    return [this_monday - datetime.timedelta(weeks=i) for i in range(WEEKS_SHOWN - 1, -1, -1)]


def _month_starts(today: datetime.date) -> list[datetime.date]:
    """First day of each of the last MONTHS_SHOWN months, oldest first, ending with this month."""
    starts = []
    year, month = today.year, today.month
    for _ in range(MONTHS_SHOWN):
        starts.append(datetime.date(year, month, 1))
        # Step back one month, wrapping January -> December of the previous year
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return starts[::-1]


def _counts_by_period(
    db: Session, applicant_id: int, unit: str, starts: list[datetime.date]
) -> list[PeriodCount]:
    """
    Applications per week/month for one job seeker, one entry per period in
    `starts`. GROUP BY only returns periods that have rows, so the empty
    ones are filled with 0 afterwards.
    """
    # 'week' / 'month' is inlined as a SQL literal rather than sent as a bound
    # parameter: with a parameter, the SELECT and the GROUP BY would each get
    # their own placeholder, and Postgres would treat them as different
    # expressions ("must appear in the GROUP BY clause"). `unit` only ever
    # comes from this file, never from the request, so inlining is safe.
    period = func.date_trunc(literal_column(f"'{unit}'"), Application.applied_at)
    window_start = datetime.datetime.combine(starts[0], datetime.time.min)

    rows = (
        db.query(period, func.count(Application.id))
        .filter(Application.applicant_id == applicant_id, Application.applied_at >= window_start)
        .group_by(period)
        .all()
    )
    # date_trunc returns a timestamp (midnight); key by its date to match `starts`
    found = {period_start.date(): count for period_start, count in rows}
    return [PeriodCount(period_start=s, count=found.get(s, 0)) for s in starts]


@router.get("/applications/mine/stats", response_model=ApplicationStatsOut)
def my_application_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GET /api/applications/mine/stats — numbers for the application history
    dashboard, computed from the existing columns (no stored counters):
      - total and per-status counts over all of the job seeker's applications
      - applications submitted per week (last 10) and per month (last 12)

    Must stay above any future GET /applications/{id} route, or "mine"
    would be parsed as an id.
    """
    _require_job_seeker(current_user)

    rows = (
        db.query(Application.status, func.count(Application.id))
        .filter(Application.applicant_id == current_user.id)
        .group_by(Application.status)
        .all()
    )
    # Seed every status with 0 so the frontend always gets all five keys in pipeline order
    by_status = {s: 0 for s in APPLICATION_STATUSES}
    by_status.update(dict(rows))

    # applied_at is stored as naive UTC (utcnow), so "today" is in UTC too,
    # keeping the buckets and the window boundaries consistent
    today = datetime.datetime.utcnow().date()

    return ApplicationStatsOut(
        total=sum(by_status.values()),
        by_status=by_status,
        weekly=_counts_by_period(db, current_user.id, "week", _week_starts(today)),
        monthly=_counts_by_period(db, current_user.id, "month", _month_starts(today)),
    )