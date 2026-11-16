"""
Application history dashboard statistics.
Endpoint:
  GET /api/applications/mine/stats

Weekly/monthly tests move applications into the past by editing applied_at
straight in the database (there is no endpoint for that, on purpose).
"""

import datetime

import pytest

from database import SessionLocal
from models import Application, Job

PDF_BYTES = b"%PDF-1.4 fake resume content"
STATUSES = ["Applied", "Under Review", "Interview", "Offered", "Rejected"]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@pytest.fixture
def recruiter(make_user):
    return make_user(role="recruiter", full_name="Rita Recruiter")


@pytest.fixture
def make_job(recruiter):
    """Factory that inserts an open job posted by `recruiter`."""

    def _make(title="Junior Developer") -> int:
        db = SessionLocal()
        try:
            job = Job(recruiter_id=recruiter.id, title=title, company="Acme")
            db.add(job)
            db.commit()
            return job.id
        finally:
            db.close()

    return _make


@pytest.fixture
def make_application(client, user, make_job):
    """Factory: `user` applies to a brand-new job. Returns the application id."""
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")},
        headers=user.headers,
    )
    assert upload.status_code == 200, upload.text

    def _make() -> int:
        response = client.post("/api/applications", json={"job_id": make_job()}, headers=user.headers)
        assert response.status_code == 201, response.text
        return response.json()["application"]["id"]

    return _make


def _set_status(client, account, application_id, status):
    response = client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": status},
        headers=account.headers,
    )
    assert response.status_code == 200, response.text


def _backdate(application_id, applied_at):
    db = SessionLocal()
    try:
        db.query(Application).filter(Application.id == application_id).update({"applied_at": applied_at})
        db.commit()
    finally:
        db.close()


def _stats(client, account):
    return client.get("/api/applications/mine/stats", headers=account.headers)


def _today():
    # Same clock as the endpoint (applied_at is stored in UTC)
    return datetime.datetime.utcnow().date()


def _this_monday():
    today = _today()
    return today - datetime.timedelta(days=today.weekday())


def _month_start(months_back):
    """First day of the month `months_back` months before the current one."""
    today = _today()
    index = today.year * 12 + (today.month - 1) - months_back
    return datetime.date(index // 12, index % 12 + 1, 1)


def _mid_week(weeks_back):
    """Noon, two days into the week `weeks_back` weeks ago: never on a boundary."""
    day = _this_monday() - datetime.timedelta(weeks=weeks_back) + datetime.timedelta(days=2)
    return datetime.datetime.combine(day, datetime.time(12))


def _mid_month(months_back):
    """Noon on the 15th of the month `months_back` months ago."""
    return datetime.datetime.combine(_month_start(months_back).replace(day=15), datetime.time(12))


# ----------------------------------------------------------------------------
# Totals and per-status counts
# ----------------------------------------------------------------------------
def test_stats_empty_for_new_job_seeker(client, user):
    response = _stats(client, user)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["by_status"] == {s: 0 for s in STATUSES}
    assert [w["count"] for w in body["weekly"]] == [0] * 10
    assert [m["count"] for m in body["monthly"]] == [0] * 12


def test_by_status_lists_every_status_in_order(client, user, make_application):
    make_application()

    by_status = _stats(client, user).json()["by_status"]

    assert list(by_status) == STATUSES


def test_stats_count_each_status(client, user, recruiter, make_application):
    ids = [make_application() for _ in range(5)]
    _set_status(client, recruiter, ids[0], "Interview")
    _set_status(client, recruiter, ids[1], "Interview")
    _set_status(client, recruiter, ids[2], "Rejected")
    _set_status(client, recruiter, ids[3], "Offered")
    # ids[4] stays "Applied"

    body = _stats(client, user).json()

    assert body["total"] == 5
    assert body["by_status"] == {
        "Applied": 1,
        "Under Review": 0,
        "Interview": 2,
        "Offered": 1,
        "Rejected": 1,
    }


def test_status_change_moves_the_count(client, user, recruiter, make_application):
    application_id = make_application()
    _set_status(client, recruiter, application_id, "Under Review")
    _set_status(client, recruiter, application_id, "Interview")

    body = _stats(client, user).json()

    # Counted once, under its current status only
    assert body["total"] == 1
    assert body["by_status"]["Interview"] == 1
    assert body["by_status"]["Applied"] == 0
    assert body["by_status"]["Under Review"] == 0


def test_stats_only_count_my_applications(client, user, make_user, make_job):
    other = make_user()
    client.post(
        "/api/resume/upload",
        files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")},
        headers=other.headers,
    )
    response = client.post("/api/applications", json={"job_id": make_job()}, headers=other.headers)
    assert response.status_code == 201

    assert _stats(client, user).json()["total"] == 0


def test_recruiter_cannot_view_stats(client, recruiter):
    assert _stats(client, recruiter).status_code == 403


def test_stats_require_login(client):
    assert client.get("/api/applications/mine/stats").status_code == 401


# ----------------------------------------------------------------------------
# Weekly counts (last 10 weeks)
# ----------------------------------------------------------------------------
def test_weekly_periods_are_the_last_10_mondays(client, user):
    weekly = _stats(client, user).json()["weekly"]

    expected = [_this_monday() - datetime.timedelta(weeks=i) for i in range(9, -1, -1)]
    assert [w["period_start"] for w in weekly] == [d.isoformat() for d in expected]


def test_weekly_counts_with_empty_weeks(client, user, make_application):
    make_application()  # this week (applied_at = now)
    _backdate(make_application(), _mid_week(3))
    _backdate(make_application(), _mid_week(3))
    _backdate(make_application(), _mid_week(9))  # oldest week still shown

    weekly = _stats(client, user).json()["weekly"]

    counts = [w["count"] for w in weekly]  # oldest first
    assert counts == [1, 0, 0, 0, 0, 0, 2, 0, 0, 1]


def test_weekly_window_excludes_older_weeks(client, user, make_application):
    _backdate(make_application(), _mid_week(10))  # 11th week back: outside the window

    body = _stats(client, user).json()

    assert sum(w["count"] for w in body["weekly"]) == 0
    # Still counted in the all-time numbers
    assert body["total"] == 1
    assert body["by_status"]["Applied"] == 1


# ----------------------------------------------------------------------------
# Monthly counts (last 12 months)
# ----------------------------------------------------------------------------
def test_monthly_periods_are_the_last_12_months(client, user):
    monthly = _stats(client, user).json()["monthly"]

    expected = [_month_start(i) for i in range(11, -1, -1)]
    assert [m["period_start"] for m in monthly] == [d.isoformat() for d in expected]


def test_monthly_counts_with_empty_months(client, user, make_application):
    make_application()  # this month
    _backdate(make_application(), _mid_month(2))
    _backdate(make_application(), _mid_month(2))
    _backdate(make_application(), _mid_month(11))  # oldest month still shown

    monthly = _stats(client, user).json()["monthly"]

    counts = [m["count"] for m in monthly]  # oldest first
    assert counts == [1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 1]


def test_monthly_window_excludes_older_months(client, user, make_application):
    _backdate(make_application(), _mid_month(12))  # 13th month back: outside the window

    body = _stats(client, user).json()

    assert sum(m["count"] for m in body["monthly"]) == 0
    assert body["total"] == 1


def test_monthly_window_crosses_year_boundary(client, user):
    # 12 consecutive months always span two calendar years unless it's December;
    # check the list is strictly increasing with no gaps or duplicate months
    monthly = _stats(client, user).json()["monthly"]

    starts = [datetime.date.fromisoformat(m["period_start"]) for m in monthly]
    month_indexes = [d.year * 12 + d.month for d in starts]
    assert month_indexes == list(range(month_indexes[0], month_indexes[0] + 12))