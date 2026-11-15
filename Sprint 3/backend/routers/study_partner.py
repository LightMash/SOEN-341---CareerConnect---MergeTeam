"""
Owner: AI Job Study Partner

Endpoints (job seekers only):
  GET    /api/jobs/{job_id}/study-chat            the conversation so far (never calls the AI)
  POST   /api/jobs/{job_id}/study-chat/messages   send a message, get the AI's reply
  DELETE /api/jobs/{job_id}/study-chat            start over
  GET    /api/jobs/{job_id}/certifications        useful certifications for the job (no AI)
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_db
from models import Job, StudyChat, StudyChatMessage, User
from routers.auth import get_current_user
from schemas import CertificationsOut, StudyChatOut, StudyMessageIn
from services import certifications as certification_service
from services import study_partner as study_service
from services.ai_client import AIServiceError

router = APIRouter()


def _require_job_seeker(current_user: User) -> None:
    if current_user.role != "job_seeker":
        raise HTTPException(status_code=403, detail="Only job seekers can use the study partner.")


def _get_job(job_id: int, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found.")
    return job


def _find_chat(job_id: int, current_user: User, db: Session) -> StudyChat | None:
    return (
        db.query(StudyChat)
        .filter(StudyChat.job_id == job_id, StudyChat.user_id == current_user.id)
        .first()
    )


def _to_out(job_id: int, chat: StudyChat | None) -> StudyChatOut:
    messages = chat.messages if chat else []
    return StudyChatOut(
        job_id=job_id,
        messages=messages,
        starter_questions=[] if messages else study_service.STARTER_QUESTIONS,
    )


@router.get("/jobs/{job_id}/study-chat", response_model=StudyChatOut)
def get_chat(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The conversation so far. A chat that hasn't started returns no messages."""
    _require_job_seeker(current_user)
    _get_job(job_id, db)
    return _to_out(job_id, _find_chat(job_id, current_user, db))


# A plain `def` on purpose (not `async def`): the Gemini call blocks for a
# few seconds, and FastAPI runs plain `def` routes in a worker thread so other
# requests keep being served meanwhile.
@router.post(
    "/jobs/{job_id}/study-chat/messages",
    response_model=StudyChatOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    job_id: int,
    body: StudyMessageIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sends the user's message, with the job posting and the recent history,
    to the AI, then saves BOTH messages. Nothing is saved if the AI fails,
    so the conversation never ends with an unanswered message.
    """
    _require_job_seeker(current_user)
    job = _get_job(job_id, db)
    chat = _find_chat(job_id, current_user, db)
    previous = chat.messages if chat else []

    try:
        reply, model = study_service.ask(job, previous, body.text)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if chat is None:
        chat = StudyChat(user_id=current_user.id, job_id=job.id)
        db.add(chat)

    now = datetime.datetime.utcnow()
    chat.messages.append(StudyChatMessage(role="user", text=body.text, created_at=now))
    chat.messages.append(
        StudyChatMessage(
            role="assistant",
            text=reply.reply,
            suggested_questions=reply.suggested_questions,
            model=model,
            created_at=now,
        )
    )
    chat.updated_at = now
    db.commit()
    db.refresh(chat)

    return _to_out(job_id, chat)


@router.delete("/jobs/{job_id}/study-chat", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes the conversation so the user can start over. Fine if there was none."""
    _require_job_seeker(current_user)
    _get_job(job_id, db)
    chat = _find_chat(job_id, current_user, db)
    if chat:
        db.delete(chat)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs/{job_id}/certifications", response_model=CertificationsOut)
def get_certifications(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Certifications from our curated list that fit the posting. Plain keyword
    matching, so it never calls the AI and the links are always ones we checked.
    """
    _require_job_seeker(current_user)
    job = _get_job(job_id, db)
    return CertificationsOut(job_id=job_id, certifications=certification_service.find_for_job(job))
