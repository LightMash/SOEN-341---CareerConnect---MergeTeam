"""
Matching rules: does a seeker's set of qualifications satisfy a listing's
requirements? Pure functions only (no database, no FastAPI), so they are easy
to test and give the same answer everywhere they are used.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .normalize import normalize

CATEGORIES = ("degree", "license", "certification", "language", "skill")

# Requirement statuses, in the order the UI shows them.
MET = "met"
MISSING = "missing"
BONUS_MISSING = "bonus_missing"
POSSIBLE = "possible"

# How close a seeker's unverified (custom) qualification name has to be to a
# requirement's alias to be shown as a "possible" match.
POSSIBLE_MATCH_RATIO = 0.8


@dataclass(frozen=True)
class Qual:
    """One qualification, from the catalog or a custom one ("custom.<id>")."""

    key: str
    category: str
    name: str
    field: str | None = None
    rank: int | None = None
    # Normalized aliases (the normalized name is always included).
    aliases: tuple[str, ...] = ()
    ambiguous: bool = False
    custom: bool = False


@dataclass(frozen=True)
class Requirement:
    qual: Qual
    is_required: bool
    weight: int = 1


@dataclass
class ItemResult:
    key: str
    name: str
    category: str
    is_required: bool
    weight: int
    has_rank: bool
    status: str
    exceeds: bool = False
    # For "possible": the seeker's own (unverified) qualification that looks similar.
    possible_name: str | None = None


@dataclass
class Evaluation:
    items: list[ItemResult] = field(default_factory=list)
    qualified: bool = True


def satisfies(have: Qual, need: Qual, implies: set[tuple[str, str]]) -> bool:
    """True if holding `have` counts as holding `need`."""
    if have.key == need.key:
        return True
    if (have.key, need.key) in implies:
        return True
    if (
        have.category == need.category
        and have.rank is not None
        and need.rank is not None
        and have.rank >= need.rank
        and (need.field is None or have.field == need.field)
    ):
        return True
    return False


def _possible_match(need: Qual, seeker_quals: list[Qual]) -> Qual | None:
    """A custom (unverified) seeker qualification whose name looks like the requirement."""
    targets = set(need.aliases) | {normalize(need.name)}
    for have in seeker_quals:
        if not have.custom or have.category != need.category:
            continue
        mine = normalize(have.name)
        for alias in targets:
            if SequenceMatcher(None, mine, alias).ratio() >= POSSIBLE_MATCH_RATIO:
                return have
    return None


def evaluate(
    requirements: list[Requirement],
    seeker_quals: list[Qual],
    implies: set[tuple[str, str]],
) -> Evaluation:
    """Status of every requirement for this seeker, plus whether they qualify."""
    result = Evaluation()
    for req in requirements:
        need = req.qual
        matching = [have for have in seeker_quals if satisfies(have, need, implies)]

        item = ItemResult(
            key=need.key,
            name=need.name,
            category=need.category,
            is_required=req.is_required,
            weight=req.weight,
            has_rank=need.rank is not None,
            status=MET,
        )

        if matching:
            if need.rank is not None:
                ranks = [h.rank for h in matching if h.rank is not None and h.category == need.category]
                item.exceeds = bool(ranks) and max(ranks) > need.rank
        else:
            similar = _possible_match(need, seeker_quals)
            if similar is not None:
                item.status = POSSIBLE
                item.possible_name = similar.name
            else:
                item.status = MISSING if req.is_required else BONUS_MISSING

        if req.is_required and item.status in (MISSING, POSSIBLE):
            result.qualified = False
        result.items.append(item)
    return result
