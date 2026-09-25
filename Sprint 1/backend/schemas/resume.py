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
    # filepath left out on purpose — frontend doesn't need our server path.

    class Config:
        from_attributes = True # lets this build from SQLAlchemy object


class ResumeUploadResponse(BaseModel):
    message: str
    resume: ResumeOut
