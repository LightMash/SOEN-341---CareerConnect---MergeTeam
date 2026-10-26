"""
Owner: Job Search feature (US-05: 5.1)
Route: GET /api/jobs. 

Read-only: posting management lives in routers/job.py (create/edit/close)
"""

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models import Job, User
from routers.auth import get_current_user
from schemas import JobOut
from schemas.job import JobType, WorkFrom

router = APIRouter()


@router.get("/jobs", response_model=list[JobOut])
def search_jobs(
    q: str | None = None,
    location: str | None = None,
    category: str | None = None,
    job_type: JobType | None = None,
    work_from: WorkFrom | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GET /api/jobs — open postings, newest first. Every filter is optional and they combine with AND.
      q          : keyword, matched (case-insensitive, partial) against title, company OR description
      location   : partial, case-insensitive  ("montreal" matches "Montreal, QC")
      category   : partial, case-insensitive
      job_type   : exact, one of JOB_TYPES  (anything else is a 422 before the route runs)
      work_from  : exact, one of WORK_FROM
    current_user is unused; the dependency is only there to require login.
    """
    # Closed postings never appear in search (see Job.is_open).
    query = db.query(Job).filter(Job.is_open.is_(True))

    # Strip so "  " is treated the same as "not provided" instead of matching everything with "%  %".
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )

    if location and location.strip():
        query = query.filter(Job.location.ilike(f"%{location.strip()}%"))

    if category and category.strip():
        query = query.filter(Job.category.ilike(f"%{category.strip()}%"))

    # Already validated against the Literal, so a plain equality is safe.
    if job_type:
        query = query.filter(Job.job_type == job_type)

    if work_from:
        query = query.filter(Job.work_from == work_from)

    # id as a tiebreaker: postings created in the same instant (e.g. in tests) still come back in a stable order.
    return query.order_by(Job.created_at.desc(), Job.id.desc()).all()