"""
Owner: User Profile feature.
Routes: GET/PUT /api/profile/me

Note: the existing GET /api/profile in routers/auth.py (returns the logged-in
User, used by the frontend for session restore) is left untouched. This file
only adds /profile/me, so the two routes never collide.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user
from models import User, Profile, Resume
from schemas import ProfileUpdate, ProfileOut

router = APIRouter()

# Profile photos live next to the resume uploads (backend/uploads/, which is
# already gitignored), in their own sub-folder. One photo per user, named
# after the USER ID (e.g. avatars/7.png) rather than a random UUID:
#   - there can only ever be one, so there is nothing to collide with,
#   - no database column is needed (so no manual ALTER TABLE for the team),
#   - the file is only ever served through the authenticated endpoints below,
#     so a predictable name doesn't expose it.
AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "avatars")
MAX_PHOTO_MB = 2

# extension we store under -> content type we serve it with. SVG is
# deliberately NOT allowed: an SVG can contain scripts.
PHOTO_MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

# The columns copied straight from the DB row into the response. Listing them
# once keeps _to_out() short and makes "add a profile field" a one-line change here.
PROFILE_FIELDS = (
    "headline", "location", "phone", "summary",
    "skills", "education", "experience",
    "linkedin_url", "github_url", "portfolio_url",
)


def _require_job_seeker(current_user: User) -> None:
    # Profiles belong to job seekers; recruiters will get their own tools later.
    if current_user.role != "job_seeker":
        raise HTTPException(status_code=403, detail="Only job seekers have a profile.")


def _get_or_create_profile(current_user: User, db: Session) -> Profile:
    """
    Profiles are created lazily the first time they're needed, so the auth
    code (register/login) doesn't have to know the profile feature exists —
    and users who registered before this feature shipped just work.
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)  # reload so column defaults ("" / []) are filled in
    return profile


def _completeness(profile: Profile, db: Session) -> tuple[int, list[str]]:
    """
    Returns (percent 0-100, names of the sections still missing).

    Only the five sections below count. Phone, summary, experience and the
    LinkedIn / GitHub / portfolio links are deliberately NOT part of the
    calculation: they are optional, so leaving them empty never lowers the
    score or shows up as "missing". To change what counts, edit this one dict.

    Computed on the backend so there is exactly one definition of
    "complete" (the frontend only draws the bar and lists what's missing).
    The resume check queries the resumes table, which is why this takes `db`.
    """
    has_resume = db.query(Resume.id).filter(Resume.user_id == profile.user_id).first() is not None

    # label shown to the user -> is it filled in? (dicts keep insertion order,
    # so "missing" comes out in this same order.)
    checks = {
        "Headline": bool(profile.headline.strip()),
        "Location": bool(profile.location.strip()),
        "Skills": bool(profile.skills),
        "Education": bool(profile.education),
        "Resume": has_resume,
    }

    missing = [label for label, done in checks.items() if not done]
    percent = round(100 * (len(checks) - len(missing)) / len(checks))
    return percent, missing


def _to_out(profile: Profile, db: Session) -> ProfileOut:
    # Built by hand (instead of from_attributes) because `completeness` and
    # `missing` are computed, not stored. JSON columns hold plain dicts;
    # Pydantic converts them into EducationItem/ExperienceItem objects here.
    completeness, missing = _completeness(profile, db)
    return ProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        **{field: getattr(profile, field) for field in PROFILE_FIELDS},
        completeness=completeness,
        missing=missing,
        updated_at=profile.updated_at,
    )


@router.get("/profile/me", response_model=ProfileOut)
def get_my_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """GET /api/profile/me — the logged-in job seeker's profile (created empty on first call)."""
    _require_job_seeker(current_user)
    profile = _get_or_create_profile(current_user, db)
    return _to_out(profile, db)


@router.put("/profile/me", response_model=ProfileOut)
def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUT /api/profile/me — replace the editable fields with the submitted values.

    PUT (not PATCH) on purpose: the client always sends the complete form, so
    clearing a field is just sending "" — no special "delete" semantics needed.
    Pydantic (schemas/profile.py) rejects invalid input with a 422 before this
    function runs, so on a failed save the stored profile is never touched.
    """
    _require_job_seeker(current_user)
    profile = _get_or_create_profile(current_user, db)

    profile.headline = payload.headline
    profile.location = payload.location
    profile.phone = payload.phone
    profile.summary = payload.summary

    # Assign NEW lists (never mutate in place) so SQLAlchemy sees the change.
    # model_dump() turns each validated Pydantic item back into a plain dict
    # that the JSON column can store.
    profile.skills = payload.skills
    profile.education = [item.model_dump() for item in payload.education]
    profile.experience = [item.model_dump() for item in payload.experience]

    profile.linkedin_url = payload.linkedin_url
    profile.github_url = payload.github_url
    profile.portfolio_url = payload.portfolio_url

    db.commit()
    db.refresh(profile)
    return _to_out(profile, db)


# ---------------------------------------------------------------------------
# Profile photo
# ---------------------------------------------------------------------------
# Unlike the /profile/me routes above (job seekers only), the photo routes are
# open to EVERY logged-in user, recruiters included: a photo is part of any
# account, not part of the job seeker's professional profile.

def _sniff_image_type(contents: bytes) -> str | None:
    """
    Decide the real image type from the file's first bytes ("magic numbers")
    instead of trusting the filename or the Content-Type the client claims,
    both of which are trivially faked. Returns the extension to store under,
    or None if the bytes aren't a JPEG / PNG / WebP.
    """
    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return ".webp"
    return None


def _photo_path(user_id: int, extension: str) -> str:
    return os.path.join(AVATAR_DIR, f"{user_id}{extension}")


def _find_photo(user_id: int) -> str | None:
    """Path of this user's stored photo, whichever extension it has, or None."""
    for extension in PHOTO_MEDIA_TYPES:
        path = _photo_path(user_id, extension)
        if os.path.exists(path):
            return path
    return None


@router.get("/profile/photo")
def get_my_photo(current_user: User = Depends(get_current_user)):
    """
    GET /api/profile/photo — the logged-in user's photo bytes.
    Returns 204 (success, empty body) when they haven't set one, rather than
    404, so the browser console isn't filled with red errors for every user
    who simply has no photo. The frontend fetches this with the auth header
    (an <img src> can't send one) and shows the result as a blob URL.
    """
    path = _find_photo(current_user.id)
    if path is None:
        return Response(status_code=204)

    return FileResponse(
        path,
        media_type=PHOTO_MEDIA_TYPES[os.path.splitext(path)[1]],
        # no-store: after a replace the browser must not hand back the old picture.
        # nosniff: never let the browser reinterpret these bytes as anything but an image.
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.put("/profile/photo")
async def upload_my_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    PUT /api/profile/photo — set or replace the logged-in user's photo.
    PUT because the resource is "my photo": sending it again simply replaces it.
    """

    contents = await file.read()

    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_PHOTO_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Photo too large ({size_mb:.1f}MB). Max allowed is {MAX_PHOTO_MB}MB.",
        )

    extension = _sniff_image_type(contents)
    if extension is None:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WebP images are accepted.")

    # Write the new photo first, THEN remove any older one with a different
    # extension (e.g. replacing a .png with a .jpg) — so a failed write can
    # never leave the user with no photo at all.
    os.makedirs(AVATAR_DIR, exist_ok=True)
    with open(_photo_path(current_user.id, extension), "wb") as f:
        f.write(contents)
    for other in PHOTO_MEDIA_TYPES:
        if other != extension and os.path.exists(_photo_path(current_user.id, other)):
            os.remove(_photo_path(current_user.id, other))

    return {"message": "Photo updated successfully"}


@router.delete("/profile/photo")
def delete_my_photo(current_user: User = Depends(get_current_user)):
    """DELETE /api/profile/photo — remove the photo (the UI falls back to initials)."""
    path = _find_photo(current_user.id)
    if path is not None:
        os.remove(path)
    return {"message": "Photo removed"}
