"""
Owner: Resume upload feature.
"""

import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)

    # Must match an existing row in "users" — DB rejects bad user_ids.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Original uploaded name, for display only — never used to find the file.
    filename = Column(String(255), nullable=False)

    # Actual unique location on disk — this is what we use to read/delete it.
    filepath = Column(Text, nullable=False)

    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Lets us write resume.owner to get the linked User object.
    owner = relationship("User", back_populates="resumes")