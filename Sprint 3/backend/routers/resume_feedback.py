"""
Owner: AI Resume Feedback (US-16, Task 16.2)

Endpoints:
  POST /api/resume/{resume_id}/feedback   ask the AI for a new review (optional body: {"job_id": 3})
  GET  /api/resume/{resume_id}/feedback   the latest saved review, without calling the AI

Both reuse the resume feature's ownership check, so a user can only ever
review their own resumes.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Job, Resume, ResumeFeedback, User
from routers.auth import get_current_user
from routers.resume import _get_owned_resume
from schemas import FeedbackRequest, ResumeFeedbackOut
from services import resume_feedback as feedback_service
from services.ai_client import AIServiceError, model_name
from services.resume_parser import ResumeParseError, extract_text

router = APIRouter()


def _to_out(feedback: ResumeFeedback, resume: Resume) -> ResumeFeedbackOut:
    """Builds the response, adding the computed `is_outdated` flag."""
    return ResumeFeedbackOut(
        id=feedback.id,
        resume_id=feedback.resume_id,
        job_id=feedback.job_id,
        overall_score=feedback.overall_score,
        summary=feedback.summary,
        strengths=feedback.strengths,
        suggestions=feedback.suggestions,
        model=feedback.model,
        created_at=feedback.created_at,
        # Replacing a resume keeps its id but updates uploaded_at (see
        # replace_resume in routers/resume.py), so a newer upload means this
        # feedback describes a file that no longer exists.
        is_outdated=resume.uploaded_at is not None and resume.uploaded_at > feedback.created_at,
    )


# NOTE: a plain `def`, not `async def`, on purpose. The Gemini call blocks
# for several seconds. FastAPI runs plain `def` routes in a worker thread,
# so other users' requests keep being served meanwhile. Inside an
# `async def`, the same blocking call would freeze the whole server.
@router.post(
    "/resume/{resume_id}/feedback",
    response_model=ResumeFeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
def create_feedback(
    resume_id: int,
    body: FeedbackRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Task 16.2: reads the resume, asks Gemini for feedback, saves it, returns it.
    Order matters: every cheap check runs BEFORE the AI call, so a bad
    request never spends API quota.
    """
    # 1. The resume exists and belongs to this user (404 / 403 otherwise).
    resume = _get_owned_resume(resume_id, current_user, db)
    if not os.path.exists(resume.filepath):
        raise HTTPException(status_code=404, detail="File is missing from storage.")

    # 2. Optional job posting to tailor the feedback to.
    job = None
    if body is not None and body.job_id is not None:
        job = db.query(Job).filter(Job.id == body.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job posting not found.")

    # 3. Resume file -> text. 422 = "we understood the request, but this
    #    file can't be processed" (scanned, locked or damaged).
    try:
        resume_text = extract_text(resume.filepath)
    except ResumeParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 4. Text -> AI feedback. 503 = "a service we depend on is unavailable";
    #    the messages from ai_client are already safe to show users.
    try:
        feedback, suggestions = feedback_service.generate_feedback(resume_text, job)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # 5. Save it. Only reached when everything above worked, so a failed
    #    request never leaves a half-written row behind.
    row = ResumeFeedback(
        resume_id=resume.id,
        job_id=job.id if job else None,
        overall_score=feedback.overall_score,
        summary=feedback.summary,
        strengths=feedback.strengths,
        suggestions=suggestions,
        model=model_name(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return _to_out(row, resume)


@router.get("/resume/{resume_id}/feedback", response_model=ResumeFeedbackOut)
def get_latest_feedback(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The most recent saved feedback for this resume. Never calls the AI."""
    resume = _get_owned_resume(resume_id, current_user, db)

    latest = (
        db.query(ResumeFeedback)
        .filter(ResumeFeedback.resume_id == resume.id)
        .order_by(ResumeFeedback.id.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No feedback for this resume yet.")

    return _to_out(latest, resume)
