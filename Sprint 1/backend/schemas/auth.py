"""
Owner: Auth feature (registration/login).
Pydantic request/response shapes for /api/register, /api/login, /api/profile.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Literal


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt cannot hash beyond 72 bytes
    role: Literal["job_seeker", "recruiter"] = "job_seeker"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str

    class Config:
        from_attributes = True  # lets us build this straight from the SQLAlchemy model


class TokenResponse(BaseModel):
    message: str
    token: str
    user: UserOut
