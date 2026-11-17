"""
Demo data for trying qualification matching and standing on a LOCAL database.
Refuses to run unless DATABASE_URL points at localhost / 127.0.0.1.

Run from Sprint 3/backend (PowerShell):
    $env:DATABASE_URL='postgresql+pg8000://postgres:postgres@localhost:5432/careerconnect_local'; python -m matching.demo_data
    $env:DATABASE_URL='postgresql+pg8000://postgres:postgres@localhost:5432/careerconnect_local'; python -m matching.demo_data --reset

Everything it creates is obviously fake: "Demo ..." names and *.demo@example.com
emails (example.com is reserved for documentation; the app's email check
rejects .test addresses, so those can't log in). Running it twice changes nothing; --reset removes only demo data.

Accounts (password for all of them: DEMO_PASSWORD below):
    seeker.demo@example.com      job seeker to log in as
    recruiter.demo@example.com   recruiter who owns the demo listings
    applicant1..13.demo@example.com  other applicants (one set per listing)
"""

import argparse
import os

from .local_only import require_local_database_url

DEMO_PASSWORD = "DemoPass123"
DEMO_EMAIL_SUFFIX = ".demo@example.com"
DEMO_NAME_PREFIX = "Demo "

SEEKER_EMAIL = "seeker.demo@example.com"
RECRUITER_EMAIL = "recruiter.demo@example.com"

# The demo seeker's qualifications. The custom "First aid + CPR" entry is
# close to, but not exactly, the catalog's "First aid and CPR", so listing 1
# shows it as a "possible" match with an "I have this" button.
SEEKER_KEYS = [
    "degree.bachelors.computer_science",
    "skill.python",
    "skill.docker",
    "skill.git",
    "skill.sql",
    "language.english",
    "language.french",
]
SEEKER_CUSTOM = ("certification", "First aid + CPR")

# title -> (description, requirements [(key, is_required, weight)], applicants, seeker applies?)
# applicants: list of qualification key lists, one per other applicant.
LISTINGS = [
    (
        "Demo — Backend Developer",
        "Percentile mode: 8 qualified applicants plus one who isn't qualified.",
        [
            ("degree.bachelors.any", True, 1),
            ("skill.python", True, 1),
            ("skill.docker", False, 2),
            ("skill.kubernetes", False, 3),
            ("skill.aws", False, 1),
            ("skill.postgresql", False, 1),
            ("cert.first_aid", False, 1),
        ],
        [
            ["degree.bachelors.computer_science", "skill.python"],
            ["degree.bachelors.software_engineering", "skill.python", "skill.docker"],
            ["degree.masters.computer_science", "skill.python", "skill.docker", "skill.aws"],
            ["degree.bachelors.computer_engineering", "skill.python", "skill.docker", "skill.kubernetes"],
            ["degree.bachelors.mathematics", "skill.python", "skill.postgresql"],
            ["degree.bachelors.computer_science", "skill.python", "skill.docker", "skill.kubernetes",
             "skill.aws", "skill.postgresql"],
            ["degree.bachelors.any", "skill.python", "skill.docker"],
            ["degree.phd.computer_science", "skill.python", "skill.aws"],
            ["skill.python", "skill.docker", "skill.kubernetes"],  # no degree: not qualified
        ],
        False,
    ),
    (
        "Demo — Data Analyst",
        "Fraction mode: only 2 other applicants, too few to compare.",
        [
            ("skill.sql", True, 1),
            ("skill.power_bi", False, 2),
            ("skill.python", False, 1),
            ("skill.excel", False, 1),
        ],
        [
            ["skill.sql", "skill.power_bi"],
            ["skill.sql", "skill.excel", "skill.python"],
        ],
        True,
    ),
    (
        "Demo — Bilingual Support Agent",
        "No bonus qualifications: every qualified applicant is equal on paper.",
        [
            ("language.english", True, 1),
            ("language.french", True, 1),
        ],
        [["language.english", "language.french"]],
        True,
    ),
    (
        "Demo — Machine Learning Researcher",
        "The demo seeker is not qualified for this one.",
        [
            ("degree.phd.computer_science", True, 1),
            ("skill.pytorch", True, 1),
            ("skill.tensorflow", False, 1),
        ],
        [["degree.phd.computer_science", "skill.pytorch"]],
        False,
    ),
]


def _is_demo_user(user) -> bool:
    return user.email.endswith(DEMO_EMAIL_SUFFIX) and user.full_name.startswith(DEMO_NAME_PREFIX)


def _demo_users(db):
    from models import User

    return [u for u in db.query(User).filter(User.email.like(f"%{DEMO_EMAIL_SUFFIX}")).all() if _is_demo_user(u)]


def _get_or_create_user(db, email, full_name, role):
    from models import User
    from security import hash_password

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(full_name=full_name, email=email, password_hash=hash_password(DEMO_PASSWORD), role=role)
        db.add(user)
        db.flush()
    elif not _is_demo_user(user):
        raise SystemExit(f"{email} exists but isn't a demo account; not touching it.")
    return user


def _set_seeker_keys(db, user_id, keys):
    from matching.models import SeekerQualification

    db.query(SeekerQualification).filter(SeekerQualification.seeker_id == user_id).delete()
    for key in dict.fromkeys(keys):
        db.add(SeekerQualification(seeker_id=user_id, qualification_key=key, source="manual"))


def _apply(db, job_id, user_id):
    from models import Application, ApplicationStatusHistory

    exists = db.query(Application).filter(
        Application.job_id == job_id, Application.applicant_id == user_id
    ).first()
    if exists is None:
        application = Application(job_id=job_id, applicant_id=user_id, resume_id=None)
        application.history.append(
            ApplicationStatusHistory(old_status=None, new_status="Applied", changed_by=user_id)
        )
        db.add(application)


def seed(db) -> None:
    from matching.catalog import get_catalog
    from matching.models import CustomQualification, ListingRequirement
    from matching.normalize import normalize
    from models import Job

    catalog = get_catalog()
    for _, _, reqs, applicants, _ in LISTINGS:
        for key in [r[0] for r in reqs] + [k for a in applicants for k in a]:
            assert catalog.get(key), f"unknown key in demo data: {key}"

    recruiter = _get_or_create_user(db, RECRUITER_EMAIL, "Demo Recruiter", "recruiter")
    seeker = _get_or_create_user(db, SEEKER_EMAIL, "Demo Seeker", "job_seeker")

    category, name = SEEKER_CUSTOM
    custom = db.query(CustomQualification).filter(
        CustomQualification.category == category,
        CustomQualification.normalized_name == normalize(name),
    ).first()
    if custom is None:
        custom = CustomQualification(category=category, name=name, normalized_name=normalize(name),
                                     created_by=seeker.id)
        db.add(custom)
        db.flush()
    _set_seeker_keys(db, seeker.id, SEEKER_KEYS + [custom.key])

    applicant_number = 0
    for title, description, reqs, applicants, seeker_applies in LISTINGS:
        job = db.query(Job).filter(Job.recruiter_id == recruiter.id, Job.title == title).first()
        if job is None:
            job = Job(recruiter_id=recruiter.id, title=title, company="Demo Company",
                      location="Montreal, QC", category="Demo", description=description)
            db.add(job)
            db.flush()

        db.query(ListingRequirement).filter(ListingRequirement.listing_id == job.id).delete()
        for key, is_required, weight in reqs:
            db.add(ListingRequirement(listing_id=job.id, qualification_key=key,
                                      is_required=is_required, weight=1 if is_required else weight))

        for keys in applicants:
            applicant_number += 1
            applicant = _get_or_create_user(
                db, f"applicant{applicant_number}{DEMO_EMAIL_SUFFIX}",
                f"Demo Applicant {applicant_number}", "job_seeker",
            )
            _set_seeker_keys(db, applicant.id, keys)
            _apply(db, job.id, applicant.id)

        if seeker_applies:
            _apply(db, job.id, seeker.id)

    db.commit()
    print(f"Demo data ready. Log in as {SEEKER_EMAIL} or {RECRUITER_EMAIL} "
          "(password: see DEMO_PASSWORD in matching/demo_data.py).")


def reset(db) -> None:
    """Removes demo users and everything that belongs to them. Nothing else."""
    from matching.models import CustomQualification
    from models import Application, ApplicationStatusHistory, Job, Profile, Resume
    from routers.profile import AVATAR_DIR
    from routers.resume import UPLOAD_DIR

    users = _demo_users(db)
    ids = [u.id for u in users]
    if not ids:
        print("No demo data found.")
        return

    db.query(CustomQualification).filter(CustomQualification.created_by.in_(ids)).delete(synchronize_session=False)
    # Jobs cascade to their applications, history and requirements.
    for job in db.query(Job).filter(Job.recruiter_id.in_(ids)).all():
        db.delete(job)
    db.flush()
    app_ids = [a.id for a in db.query(Application.id).filter(Application.applicant_id.in_(ids))]
    if app_ids:
        db.query(ApplicationStatusHistory).filter(
            ApplicationStatusHistory.application_id.in_(app_ids)
        ).delete(synchronize_session=False)
        db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
    db.query(ApplicationStatusHistory).filter(
        ApplicationStatusHistory.changed_by.in_(ids)
    ).delete(synchronize_session=False)

    # Files a demo user may have uploaded while testing (only inside uploads/).
    upload_root = os.path.realpath(UPLOAD_DIR)
    for resume in db.query(Resume).filter(Resume.user_id.in_(ids)).all():
        path = os.path.realpath(resume.filepath)
        if path.startswith(upload_root + os.sep) and os.path.exists(path):
            os.remove(path)
        db.delete(resume)
    for user_id in ids:
        for ext in (".jpg", ".png", ".webp"):
            avatar = os.path.join(AVATAR_DIR, f"{user_id}{ext}")
            if os.path.exists(avatar):
                os.remove(avatar)
    db.query(Profile).filter(Profile.user_id.in_(ids)).delete(synchronize_session=False)

    for user in users:
        db.delete(user)  # seeker_qualifications cascade
    db.commit()
    print(f"Removed {len(ids)} demo accounts and their data.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local demo data for qualification matching.")
    parser.add_argument("--reset", action="store_true", help="remove the demo data instead of creating it")
    args = parser.parse_args()

    require_local_database_url()

    # Only now is it safe to import anything that connects to the database.
    import database
    import matching.models  # noqa: F401  (registers the matching tables)
    import models  # noqa: F401

    database.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    try:
        if args.reset:
            reset(db)
        else:
            seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
