"""
Qualification search: maps whatever the user typed onto catalog entries (and
custom qualifications) through their aliases. Pure function, no database:
the caller passes in the custom qualifications to consider.

Ranking, best first:
  4. exact alias match          "doctorate in computer science"
  3. an alias starts with q     "pyth" -> "python"
  2. word overlap               "computer science degree"
  1. close spelling (difflib)   "pyhton" -> "python"
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from .catalog import Catalog
from .normalize import normalize
from .rules import Qual

MAX_RESULTS = 10
FUZZY_CUTOFF = 0.75

EXACT, PREFIX, OVERLAP, FUZZY = 4, 3, 2, 1


@dataclass
class SearchHit:
    qual: Qual
    tier: int
    score: float
    matched_alias: str


def _score_alias(query: str, query_tokens: set[str], alias: str, matcher: SequenceMatcher, fuzzy: bool):
    """(tier, score) for one alias, or None if it doesn't match at all."""
    if alias == query:
        return EXACT, 1.0
    if alias.startswith(query):
        # Shorter aliases first: "python" before "python3" for "pyth".
        return PREFIX, len(query) / len(alias)
    alias_tokens = alias.split()
    overlap = query_tokens.intersection(alias_tokens)
    if overlap:
        # Mostly how much of the query is covered; then prefer tighter aliases.
        coverage = len(overlap) / len(query_tokens)
        tightness = len(overlap) / len(alias_tokens)
        return OVERLAP, coverage + 0.1 * tightness
    if fuzzy:
        matcher.set_seq1(alias)
        if (
            matcher.real_quick_ratio() >= FUZZY_CUTOFF
            and matcher.quick_ratio() >= FUZZY_CUTOFF
        ):
            ratio = matcher.ratio()
            if ratio >= FUZZY_CUTOFF:
                return FUZZY, ratio
    return None


def _rank(query: str, quals: list[Qual], fuzzy: bool) -> dict[str, SearchHit]:
    query_tokens = set(query.split())
    # seq2 is the one SequenceMatcher caches, so the query goes there.
    matcher = SequenceMatcher(None, "", query, autojunk=False)
    best: dict[str, SearchHit] = {}
    for qual in quals:
        for alias in qual.aliases:
            scored = _score_alias(query, query_tokens, alias, matcher, fuzzy)
            if scored is None:
                continue
            tier, score = scored
            current = best.get(qual.key)
            if current is None or (tier, score) > (current.tier, current.score):
                best[qual.key] = SearchHit(qual, tier, score, alias)
    return best


def search(
    catalog: Catalog,
    q: str,
    category: str | None = None,
    custom: list[Qual] | None = None,
    limit: int = MAX_RESULTS,
) -> list[SearchHit]:
    """Best `limit` qualifications for the typed text, one hit per qualification."""
    query = normalize(q)
    if not query:
        return []

    quals = list(catalog.entries.values()) + list(custom or [])
    if category:
        quals = [qual for qual in quals if qual.category == category]

    # The fuzzy pass is the slow one; only run it when the cheap tiers did
    # not already find enough results.
    best = _rank(query, quals, fuzzy=False)
    if len(best) < limit:
        best = _rank(query, quals, fuzzy=True)

    hits = sorted(
        best.values(),
        # Ties: catalog before custom, then shorter (more general) names.
        key=lambda h: (-h.tier, -h.score, h.qual.custom, len(h.qual.name), h.qual.name),
    )
    return hits[:limit]
