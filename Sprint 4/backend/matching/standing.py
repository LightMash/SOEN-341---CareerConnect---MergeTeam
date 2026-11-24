"""
"Your standing": where a qualified seeker sits among the other qualified
applicants to a listing, based ONLY on the listed qualifications.

This is not a hiring probability. It ignores experience, interviews and
everything else a recruiter looks at, and the UI says so.

Pure functions: the caller passes in the requirements, the seeker's
qualifications and the qualifications of everyone who applied.
"""

import datetime
import math

from .rules import BONUS_MISSING, MET, MISSING, POSSIBLE, Evaluation, Qual, Requirement, evaluate

NOTE = "Based only on listed qualifications, not experience, interviews or other factors."
EQUAL_ON_PAPER_MESSAGE = (
    "This listing has no bonus qualifications, so all qualified applicants are equal on paper"
)
NOT_ENOUGH_MESSAGE = "Not enough applicants yet to compare."

MIN_POOL_FOR_PERCENTILE = 5
PROFILE_NUDGE_THRESHOLD = 5
MAX_SUGGESTIONS = 2

# Breakdown highlights (shares of the qualified pool, N >= 5 only).
SETS_APART_MAX_SHARE = 0.30
MOST_HAVE_MIN_SHARE = 0.60


def score(evaluation: Evaluation) -> int:
    """Weights of satisfied bonus items + 1 per required item the seeker exceeds."""
    total = 0
    for item in evaluation.items:
        if item.is_required:
            total += 1 if item.status == MET and item.exceeds else 0
        elif item.status == MET:
            total += item.weight
    return total


def max_score(requirements: list[Requirement]) -> int:
    """All bonus weights + one point per required item that has a rank."""
    return sum(
        r.weight if not r.is_required else (1 if r.qual.rank is not None else 0)
        for r in requirements
    )


def percentile(seeker_score: int, pool_scores: list[int]) -> int:
    """
    pool_scores includes the seeker. round((below + 0.5 * ties) / N * 100),
    where ties counts the seeker too. Rounds halves up.
    """
    n = len(pool_scores)
    below = sum(1 for s in pool_scores if s < seeker_score)
    ties = sum(1 for s in pool_scores if s == seeker_score)
    return math.floor((below + 0.5 * ties) / n * 100 + 0.5)


def percentile_label(value: int) -> str:
    if value >= 75:
        return "Strong"
    if value >= 40:
        return "Competitive"
    return "Below most applicants"


def fraction_label(value: float) -> str:
    if value >= 0.75:
        return "Strong match"
    if value >= 0.4:
        return "Partial match"
    return "Few bonus qualifications"


def _value(seeker_score: int, others: list[int], top: int, use_percentile: bool):
    if use_percentile:
        return percentile(seeker_score, others + [seeker_score])
    return round(seeker_score / top, 2)


def compute_standing(
    requirements: list[Requirement],
    seeker_quals: list[Qual],
    applicant_quals: list[list[Qual]],
    implies: set[tuple[str, str]],
    now: datetime.datetime | None = None,
) -> dict:
    """
    applicant_quals: the qualifications of every OTHER applicant to the listing
    (the seeker must not be in it). Only the qualified ones join the pool.
    """
    as_of = (now or datetime.datetime.utcnow()).isoformat()
    mine = evaluate(requirements, seeker_quals, implies)

    others_eval = [evaluate(requirements, quals, implies) for quals in applicant_quals]
    qualified_others = [e for e in others_eval if e.qualified]
    n = len(qualified_others) + 1

    result = {
        "status": None,
        "label": None,
        "percentile": None,
        "fraction": None,
        "score": None,
        "max_score": None,
        "pool_size": n,
        "other_applicants": n - 1,
        "as_of": as_of,
        "message": None,
        "breakdown": [],
        "suggestions": [],
        "missing": [],
        "profile_nudge": None,
        "note": NOTE,
    }

    if len(seeker_quals) < PROFILE_NUDGE_THRESHOLD:
        result["profile_nudge"] = (
            f"Your profile lists {len(seeker_quals)} qualifications. "
            "Make sure everything from your resume is added."
        )

    if not mine.qualified:
        result["status"] = "not_qualified"
        result["missing"] = [
            {"key": i.key, "name": i.name, "status": i.status, "possible_name": i.possible_name}
            for i in mine.items
            if i.is_required and i.status in (MISSING, POSSIBLE)
        ]
        return result

    top = max_score(requirements)
    my_score = score(mine)
    result["score"] = my_score
    result["max_score"] = top

    if top == 0:
        result["status"] = "equal_on_paper"
        result["message"] = EQUAL_ON_PAPER_MESSAGE
        return result

    other_scores = [score(e) for e in qualified_others]
    use_percentile = n >= MIN_POOL_FOR_PERCENTILE
    current = _value(my_score, other_scores, top, use_percentile)

    if use_percentile:
        result["status"] = "percentile"
        result["percentile"] = current
        result["label"] = percentile_label(current)
    else:
        result["status"] = "fraction"
        result["fraction"] = current
        result["label"] = fraction_label(current)
        result["message"] = NOT_ENOUGH_MESSAGE

    # Breakdown: one row per bonus item.
    my_items = {i.key: i for i in mine.items}
    for req in requirements:
        if req.is_required:
            continue
        has = my_items[req.qual.key].status == MET
        row = {"key": req.qual.key, "name": req.qual.name, "weight": req.weight, "has": has,
               "share": None, "highlight": None}
        if use_percentile:
            holders = 1 if has else 0
            holders += sum(
                1 for e in qualified_others
                if any(i.key == req.qual.key and i.status == MET for i in e.items)
            )
            share = holders / n
            row["share"] = round(share, 2)
            if has and share <= SETS_APART_MAX_SHARE:
                row["highlight"] = "Sets you apart"
            elif not has and share >= MOST_HAVE_MIN_SHARE:
                row["highlight"] = "Most applicants have this"
        result["breakdown"].append(row)

    # Suggestions: what each missing bonus would do to the result.
    options = []
    for req in requirements:
        if req.is_required or my_items[req.qual.key].status not in (BONUS_MISSING, POSSIBLE):
            continue
        new_score = score(evaluate(requirements, seeker_quals + [req.qual], implies))
        new_value = _value(new_score, other_scores, top, use_percentile)
        options.append({
            "key": req.qual.key,
            "name": req.qual.name,
            "current": current,
            "new": new_value,
            "improvement": round(new_value - current, 2),
        })
    options.sort(key=lambda o: (-o["improvement"], o["name"]))
    result["suggestions"] = options[:MAX_SUGGESTIONS]
    return result
