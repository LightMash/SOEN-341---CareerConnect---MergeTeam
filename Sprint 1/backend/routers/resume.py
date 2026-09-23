"""
Owner: Resume upload feature.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user  # reuse auth's dependency, don't redefine it
from models import User, Resume
from schemas import ResumeOut, ResumeUploadResponse

router = APIRouter()


@router.post("/resume/upload", response_model=ResumeUploadResponse)
def upload_resume(
    filename: str,  # TODO: replace with an actual file upload (UploadFile) when building this out
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = Resume(user_id=current_user.id, filename=filename)
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return {"message": "Resume uploaded", "resume": resume}


@router.get("/resume/mine", response_model=list[ResumeOut])
def list_my_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Resume).filter(Resume.user_id == current_user.id).all()
