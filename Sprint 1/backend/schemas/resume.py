"""
Owner: Resume upload feature.
Pydantic request/response shapes for /api/resume/*.
"""

import datetime
from pydantic import BaseModel


class ResumeOut(BaseModel):
    id: int
    user_id: int
    filename: str
    uploaded_at: datetime.datetime

    class Config:
        from_attributes = True


class ResumeUploadResponse(BaseModel):
    message: str
    resume: ResumeOut
