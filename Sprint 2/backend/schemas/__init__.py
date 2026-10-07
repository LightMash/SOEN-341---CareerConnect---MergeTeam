"""
Central import point so the rest of the app writes `from schemas import UserCreate, ...`
regardless of which file a schema actually lives in.

When you add a new feature's schemas, create its own file in this folder and
add one import line here.
"""

from .auth import UserCreate, UserLogin, UserOut, TokenResponse
from .resume import ResumeOut, ResumeUploadResponse

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserOut",
    "TokenResponse",
    "ResumeOut",
    "ResumeUploadResponse",
]
