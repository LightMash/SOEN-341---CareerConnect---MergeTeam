"""
Owner: Notifications feature (US-09)
Pydantic request/response shapes for /api/notifications/*.
"""

import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    message: str
    application_id: int | None
    is_read: bool
    created_at: datetime.datetime


class UnreadCountOut(BaseModel):
    unread: int

