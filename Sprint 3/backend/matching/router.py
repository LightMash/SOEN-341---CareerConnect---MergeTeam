"""
Routes (all under /api/matching):
  GET  /qualifications/search?q=&category=   search the standard list + custom ones
  POST /qualifications/custom                 add a qualification that isn't in the list
  GET  /me/qualifications                     the job seeker's qualifications
  PUT  /me/qualifications                     replace them
  POST /me/qualifications/claim/{key}         "I have this" for a possible match
  POST /me/qualifications/extract             resume import (returns candidates, saves nothing)
  GET  /reviewer                              is the second-pass resume review on?
  GET  /listings/{id}/requirements            a listing's requirements (anyone who can see it)
  PUT  /listings/{id}/requirements            replace them (the listing's recruiter only)
  POST /match                                 match the job seeker against up to 100 listings
  GET  /listings/{id}/standing                "Your standing" for one listing

Existing job / application routes are not changed; this file only reads
the jobs, applications and resumes tables.
"""

import os

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Application, Job, Resume, User
from routers.auth import get_current_user

from .catalog import get_catalog
from .models import CustomQualification, ListingRequirement, SeekerQualification
from .normalize import normalize
from .resume_scan import NO_TEXT_MESSAGE, build_candidates, extract_pdf_text
from .reviewer import get_reviewer
from .rules import Qual, Requirement, evaluate
from .schemas import (
    MAX_MATCH_LISTINGS,
    CandidateOut,
    CustomQualificationIn,
    CustomQualificationOut,
    ExtractOut,
    ItemResultOut,
    MatchOut,
    RequirementOut,
    RequirementsUpdate,
    ReviewerStatusOut,
    SearchResultOut,
    SeekerQualificationOut,
    SeekerQualificationsUpdate,
    StandingOut,
)
from .search import search
from .standing import compute_standing

router = APIRouter(prefix="/matching")

# Load (and cache) the catalog when the app starts, not on the first request.
get_catalog()

MAX_RESUME_MB = 5
CUSTOM_PREFIX = "custom."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_job_seeker(user: User) -> None:
    if user.role != "job_seeker":
        raise HTTPException(status_code=403, detail="Only job seekers have qualifications.")


def _custom_to_qual(row: CustomQualification) -> Qual:
    return Qual(
        key=row.key,
        category=row.category,
        name=row.name,
        field=row.field,
        rank=None,
        aliases=(row.normalized_name,),
        custom=True,
    )


def _custom_id(key: str) -> int | None:
    if not key.startswith(CUSTOM_PREFIX):
        return None
    try:
        return int(key[len(CUSTOM_PREFIX):])
    except ValueError:
        return None


def resolve_keys(keys, db: Session) -> dict[str, Qual]:
    """key -> Qual for every key that exists (catalog or custom). Unknown keys are left out."""
    catalog = get_catalog()
    found = {}
    custom_ids = set()
    for key in keys:
        qual = catalog.get(key)
        if qual is not None:
            found[key] = qual
        elif (cid := _custom_id(key)) is not None:
            custom_ids.add(cid)
    if custom_ids:
        rows = db.query(CustomQualification).filter(CustomQualification.id.in_(custom_ids)).all()
        for row in rows:
            found[row.key] = _custom_to_qual(row)
    return found


def _check_keys(keys: list[str], db: Session) -> dict[str, Qual]:
    resolved = resolve_keys(keys, db)
    unknown = [k for k in keys if k not in resolved]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown qualification: {', '.join(unknown[:5])}")
    return resolved


def _qual_fields(qual: Qual) -> dict:
    return dict(
        key=qual.key, name=qual.name, category=qual.category,
        field=qual.field, rank=qual.rank, custom=qual.custom,
    )


def _visible_job(job_id: int, user: User, db: Session) -> Job:
    """Same visibility rule as GET /api/jobs/{id}: closed postings are owner-only."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (not job.is_open and job.recruiter_id != user.id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _requirements_for(job_ids: list[int], db: Session) -> dict[int, list[Requirement]]:
    rows = db.query(ListingRequirement).filter(ListingRequirement.listing_id.in_(job_ids)).all()
    resolved = resolve_keys({r.qualification_key for r in rows}, db)
    out: dict[int, list[Requirement]] = {job_id: [] for job_id in job_ids}
    for row in rows:
        qual = resolved.get(row.qualification_key)
        if qual is not None:
            weight = 1 if row.is_required else row.weight
            out[row.listing_id].append(Requirement(qual, row.is_required, weight))
    for reqs in out.values():
        # Stable order: required first, then by name.
        reqs.sort(key=lambda r: (not r.is_required, r.qual.name))
    return out


def _seeker_rows(user_id: int, db: Session) -> list[SeekerQualification]:
    return (
        db.query(SeekerQualification)
        .filter(SeekerQualification.seeker_id == user_id)
        .order_by(SeekerQualification.created_at, SeekerQualification.qualification_key)
        .all()
    )


def _seeker_quals(user_id: int, db: Session) -> list[Qual]:
    rows = _seeker_rows(user_id, db)
    resolved = resolve_keys([r.qualification_key for r in rows], db)
    return [resolved[r.qualification_key] for r in rows if r.qualification_key in resolved]


def _seeker_out(user_id: int, db: Session) -> list[SeekerQualificationOut]:
    rows = _seeker_rows(user_id, db)
    resolved = resolve_keys([r.qualification_key for r in rows], db)
    return [
        SeekerQualificationOut(**_qual_fields(resolved[r.qualification_key]), source=r.source)
        for r in rows
        if r.qualification_key in resolved
    ]


def _all_custom(db: Session) -> list[Qual]:
    return [_custom_to_qual(row) for row in db.query(CustomQualification).all()]


# ---------------------------------------------------------------------------
# The qualification list
# ---------------------------------------------------------------------------
@router.get("/qualifications/search", response_model=list[SearchResultOut])
def search_qualifications(
    q: str = "",
    category: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hits = search(get_catalog(), q, category=category or None, custom=_all_custom(db))
    return [SearchResultOut(**_qual_fields(h.qual), matched_alias=h.matched_alias) for h in hits]


@router.post("/qualifications/custom", response_model=CustomQualificationOut)
def create_custom_qualification(
    payload: CustomQualificationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Adds a qualification that isn't in the standard list. If the name already
    matches a catalog alias or an existing custom qualification in the same
    category, that one is returned instead (existing = true).
    """
    normalized = normalize(payload.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="Enter a name for the qualification.")

    for qual in get_catalog().entries.values():
        if qual.category == payload.category and normalized in qual.aliases:
            return CustomQualificationOut(**_qual_fields(qual), existing=True)

    def existing_custom():
        return (
            db.query(CustomQualification)
            .filter(
                CustomQualification.category == payload.category,
                CustomQualification.normalized_name == normalized,
            )
            .order_by(CustomQualification.id)
            .first()
        )

    row = existing_custom()
    if row is not None:
        return CustomQualificationOut(**_qual_fields(_custom_to_qual(row)), existing=True)

    row = CustomQualification(
        category=payload.category,
        name=payload.name,
        normalized_name=normalized,
        field=payload.field or None,
        created_by=current_user.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Someone created the same one at the same moment.
        db.rollback()
        row = existing_custom()
        if row is None:
            raise
        return CustomQualificationOut(**_qual_fields(_custom_to_qual(row)), existing=True)
    db.refresh(row)
    return CustomQualificationOut(**_qual_fields(_custom_to_qual(row)), existing=False)


# ---------------------------------------------------------------------------
# The job seeker's qualifications
# ---------------------------------------------------------------------------
@router.get("/me/qualifications", response_model=list[SeekerQualificationOut])
def get_my_qualifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_job_seeker(current_user)
    return _seeker_out(current_user.id, db)


@router.put("/me/qualifications", response_model=list[SeekerQualificationOut])
def replace_my_qualifications(
    payload: SeekerQualificationsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replaces the whole list. Items that were already there keep their original source and date."""
    _require_job_seeker(current_user)
    wanted = {}
    for item in payload.qualifications:
        wanted.setdefault(item.key, item.source)
    _check_keys(list(wanted), db)

    existing = {r.qualification_key: r for r in _seeker_rows(current_user.id, db)}
    for key, row in existing.items():
        if key not in wanted:
            db.delete(row)
    for key, source in wanted.items():
        if key not in existing:
            db.add(SeekerQualification(seeker_id=current_user.id, qualification_key=key, source=source))
    db.commit()
    return _seeker_out(current_user.id, db)


@router.post("/me/qualifications/claim/{key}", response_model=list[SeekerQualificationOut])
def claim_qualification(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """'I have this': adds one qualification (used for possible matches)."""
    _require_job_seeker(current_user)
    _check_keys([key], db)
    exists = (
        db.query(SeekerQualification)
        .filter(SeekerQualification.seeker_id == current_user.id, SeekerQualification.qualification_key == key)
        .first()
    )
    if exists is None:
        db.add(SeekerQualification(seeker_id=current_user.id, qualification_key=key, source="manual"))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # double click: it's already there, which is the goal
    return _seeker_out(current_user.id, db)


# ---------------------------------------------------------------------------
# Resume import
# ---------------------------------------------------------------------------
@router.get("/reviewer", response_model=ReviewerStatusOut)
def reviewer_status(current_user: User = Depends(get_current_user)):
    """Lets the UI warn that resume text would be sent to an external reviewer."""
    return ReviewerStatusOut(enabled=get_reviewer().enabled)


def _resume_bytes(resume_id: int, user: User, db: Session) -> bytes:
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")
    if resume.user_id != user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to access this resume.")
    if os.path.splitext(resume.filepath)[1].lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF resumes can be scanned. Upload a PDF instead.")
    if not os.path.exists(resume.filepath):
        raise HTTPException(status_code=404, detail="File is missing from storage.")
    with open(resume.filepath, "rb") as f:
        return f.read()


@router.post("/me/qualifications/extract", response_model=ExtractOut)
async def extract_from_resume(
    file: UploadFile | None = File(None),
    resume_id: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Scans a PDF (uploaded directly, or one of the seeker's saved resumes) and
    returns candidate qualifications for the seeker to confirm. Saves nothing.
    """
    _require_job_seeker(current_user)
    if (file is None) == (resume_id is None):
        raise HTTPException(status_code=400, detail="Send either a PDF file or a resume_id.")

    if file is not None:
        data = await file.read()
        if len(data) > MAX_RESUME_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File too large. Max allowed is {MAX_RESUME_MB}MB.")
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Only PDF files can be scanned.")
    else:
        data = _resume_bytes(resume_id, current_user, db)

    reviewer = get_reviewer()
    text = extract_pdf_text(data)
    if not text.strip():
        return ExtractOut(candidates=[], unresolved=[], message=NO_TEXT_MESSAGE, reviewer_enabled=reviewer.enabled)

    candidates, unresolved = build_candidates(text, get_catalog(), reviewer, custom=_all_custom(db))
    mine = {r.qualification_key for r in _seeker_rows(current_user.id, db)}
    return ExtractOut(
        candidates=[
            CandidateOut(
                key=c.key, name=c.name, category=c.category, source=c.source, state=c.state,
                reason=c.reason, snippet=c.snippet, already_added=c.key in mine,
            )
            for c in candidates
        ],
        unresolved=unresolved,
        message=None if candidates or unresolved else "No qualifications were recognized in this resume.",
        reviewer_enabled=reviewer.enabled,
    )


# ---------------------------------------------------------------------------
# Listing requirements
# ---------------------------------------------------------------------------
def _requirements_out(job_id: int, db: Session) -> list[RequirementOut]:
    return [
        RequirementOut(**_qual_fields(r.qual), is_required=r.is_required, weight=r.weight)
        for r in _requirements_for([job_id], db)[job_id]
    ]


@router.get("/listings/{job_id}/requirements", response_model=list[RequirementOut])
def get_listing_requirements(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _visible_job(job_id, current_user, db)
    return _requirements_out(job_id, db)


@router.put("/listings/{job_id}/requirements", response_model=list[RequirementOut])
def replace_listing_requirements(
    job_id: int,
    payload: RequirementsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if current_user.role != "recruiter" or job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the recruiter who posted this job can set its requirements.")

    keys = [r.key for r in payload.requirements]
    if len(set(keys)) != len(keys):
        raise HTTPException(status_code=422, detail="Each qualification can only be listed once.")
    _check_keys(keys, db)

    db.query(ListingRequirement).filter(ListingRequirement.listing_id == job_id).delete()
    for item in payload.requirements:
        db.add(ListingRequirement(
            listing_id=job_id,
            qualification_key=item.key,
            is_required=item.is_required,
            weight=1 if item.is_required else item.weight,
        ))
    db.commit()
    return _requirements_out(job_id, db)


# ---------------------------------------------------------------------------
# Matching and standing
# ---------------------------------------------------------------------------
@router.post("/match", response_model=list[MatchOut])
def match_listings(
    listing_ids: list[int] = Body(..., max_length=MAX_MATCH_LISTINGS),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Body: a JSON list of listing ids. Listings the seeker can't see are left out."""
    _require_job_seeker(current_user)
    ids = list(dict.fromkeys(listing_ids))
    if not ids:
        return []
    visible = {
        job.id
        for job in db.query(Job.id).filter(
            Job.id.in_(ids), or_(Job.is_open.is_(True), Job.recruiter_id == current_user.id)
        )
    }
    reqs = _requirements_for([i for i in ids if i in visible], db)
    mine = _seeker_quals(current_user.id, db)
    implies = get_catalog().implies

    out = []
    for job_id in ids:
        if job_id not in visible:
            continue
        evaluation = evaluate(reqs[job_id], mine, implies)
        out.append(MatchOut(
            listing_id=job_id,
            qualified=evaluation.qualified,
            requirements=[ItemResultOut(**vars(item)) for item in evaluation.items],
        ))
    return out


@router.get("/listings/{job_id}/standing", response_model=StandingOut)
def get_standing(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_job_seeker(current_user)
    _visible_job(job_id, current_user, db)

    requirements = _requirements_for([job_id], db)[job_id]
    mine = _seeker_quals(current_user.id, db)

    # Everyone else who applied (read-only), with their current qualifications.
    applicant_ids = [
        row.applicant_id
        for row in db.query(Application.applicant_id).filter(
            Application.job_id == job_id, Application.applicant_id != current_user.id
        )
    ]
    rows = (
        db.query(SeekerQualification).filter(SeekerQualification.seeker_id.in_(applicant_ids)).all()
        if applicant_ids else []
    )
    resolved = resolve_keys({r.qualification_key for r in rows}, db)
    by_applicant: dict[int, list[Qual]] = {aid: [] for aid in applicant_ids}
    for row in rows:
        if row.qualification_key in resolved:
            by_applicant[row.seeker_id].append(resolved[row.qualification_key])

    return compute_standing(requirements, mine, list(by_applicant.values()), get_catalog().implies)

