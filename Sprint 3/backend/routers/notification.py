"""
Owner: Notifications feature (US-09)
Routes (all require a logged-in user and only ever touch THEIR OWN rows):
  GET    /api/notifications               - newest first (?unread_only=true, ?limit=50)
  GET    /api/notifications/unread-count  - number for the sidebar badge
  POST   /api/notifications/read-all      - mark everything read
  POST   /api/notifications/{id}/read     - mark one read
  DELETE /api/notifications/{id}

Events (new application, status change) are raised from routers/application.py
through services/notifications.py; this file is only the "read / manage" side.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import Notification, User
from routers.auth import get_current_user
from schemas.notification import NotificationOut, UnreadCountOut

router = APIRouter()


def _get_own_notification(notification_id: int, user: User, db: Session) -> Notification:
    # 404 (not 403) for someone else's row, so ids can't be probed.
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return notification


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.id.desc()).limit(limit).all()


@router.get("/notifications/unread-count", response_model=UnreadCountOut)
def unread_count(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .count()
    )
    return UnreadCountOut(unread=count)


@router.post("/notifications/read-all")
def mark_all_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = _get_own_notification(notification_id, current_user, db)
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.delete(_get_own_notification(notification_id, current_user, db))
    db.commit()
