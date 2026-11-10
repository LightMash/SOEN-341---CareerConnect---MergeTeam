"""
Creating notifications.

KEY IDEA: `notify()` only db.add()s the row; it does NOT commit. The calling
router commits once, so "the status changed" and "the user was notified" are
saved together or not at all (same trick as the application history entry).
"""

from sqlalchemy.orm import Session

from models import Application, Job, Notification, User


def notify(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    message: str,
    application_id: int | None = None,
) -> Notification:
    """Stage one notification in the current transaction (caller commits)."""
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title[:150],
        message=message[:500],
        application_id=application_id,
    )
    db.add(notification)
    return notification


# ---------------------------------------------------------------------------
# Events raised by the application routes
# ---------------------------------------------------------------------------
def notify_new_application(db: Session, application: Application, job: Job, applicant: User) -> Notification:
    """-> the recruiter who owns the posting."""
    return notify(
        db,
        user_id=job.recruiter_id,
        type="new_application",
        title="New application received",
        message=f"{applicant.full_name} applied to {job.title} at {job.company}.",
        application_id=application.id,
    )


def notify_status_change(db: Session, application: Application, new_status: str) -> Notification:
    """-> the job seeker whose application was moved by the recruiter."""
    job = application.job
    if new_status == "Interview":
        return notify(
            db,
            user_id=application.applicant_id,
            type="interview_invitation",
            title="Interview invitation",
            message=f"{job.company} invited you to interview for {job.title}.",
            application_id=application.id,
        )
    return notify(
        db,
        user_id=application.applicant_id,
        type="status_changed",
        title="Application update",
        message=f"Your application for {job.title} at {job.company} is now: {new_status}.",
        application_id=application.id,
    )
