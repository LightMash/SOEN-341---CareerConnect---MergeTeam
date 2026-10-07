"""
Owner: Auth feature (registration/login).
Only edit this file for changes to the User model itself.
"""
#Python's built-in module for working with dates/times.
import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False, default="job_seeker")  # or "recruiter"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships to other features' models are declared with a string name
    # (SQLAlchemy resolves it at runtime), so this file never has to import
    # Resume/Job/Application directly and never conflicts with those files.
    resumes = relationship("Resume", back_populates="owner")
