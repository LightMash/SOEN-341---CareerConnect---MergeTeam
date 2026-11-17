"""
Resume import: turns a resume into a checklist of candidate qualifications
the seeker then confirms. Nothing here saves anything.

  1. extract_pdf_text()  - text layer of the PDF (empty for scanned images)
  2. scan()              - plain keyword scan against the catalog aliases
  3. build_candidates()  - scan + the optional second-pass reviewer
"""

import datetime
import io
import re
from dataclasses import asdict, dataclass

from .catalog import Catalog
from .normalize import normalize
from .reviewer import Reviewer, run_review
from .rules import Qual
from .search import EXACT, FUZZY, OVERLAP, PREFIX, search

# Candidate states shown in the checklist.
FOUND = "found"
IN_PROGRESS = "in_progress"
QUESTIONABLE = "questionable"
SUGGESTED = "suggested"

NO_TEXT_MESSAGE = (
    "We couldn't read any text from this file (it may be a scanned image). "
    "Add your qualifications with the search box instead."
)

# Section headings (normalized) -> section. Anything that is not one of the
# sections we care about still ends the previous section ("other").
_HEADINGS = {
    "education": [
        "education", "formation", "academic background", "education and training", "etudes",
        "scolarite", "academic history", "formation academique", "academic qualifications",
    ],
    "skills": [
        "skills", "technical skills", "competences", "competences techniques", "core competencies",
        "key skills", "skills and interests", "technologies", "tools and technologies", "skills and tools",
        "technical expertise", "programming languages", "computer skills", "competences informatiques",
    ],
    "certifications": [
        "certifications", "certificates", "certifications and licenses", "licenses and certifications",
        "licences and certifications", "certifications et permis", "licenses", "licences", "permis",
    ],
    "languages": ["languages", "langues", "spoken languages", "langues parlees"],
    "experience": [
        "experience", "work experience", "professional experience", "experience professionnelle",
        "employment history", "experiences", "relevant experience",
    ],
    "other": [
        "summary", "profile", "profil", "objective", "objectif", "interests", "interets", "hobbies",
        "references", "awards", "activities", "projects", "projets", "volunteer experience",
        "benevolat", "publications", "contact",
    ],
}
_HEADING_LOOKUP = {phrase: section for section, phrases in _HEADINGS.items() for phrase in phrases}

_IN_PROGRESS_WORDS = ("expected", "in progress", "candidate", "en cours")
_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")


@dataclass
class Candidate:
    key: str
    name: str
    category: str
    source: str  # "scan" | "reviewer"
    state: str  # found | in_progress | questionable | suggested
    reason: str | None = None
    snippet: str = ""


# ---------------------------------------------------------------------------
# PDF text
# ---------------------------------------------------------------------------
def extract_pdf_text(data: bytes) -> str:
    """Text layer of a PDF, or "" when there is none / the file can't be read."""
    from pypdf import PdfReader  # imported here so the pure scan code doesn't need it

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception:  # noqa: BLE001 - a broken PDF is treated like "no text"
        return ""
    return "\n".join(pages)


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
def _pattern(alias: str) -> re.Pattern:
    # Word boundaries that also treat + and # as part of a word, so "java"
    # doesn't match inside "javascript" and "c" doesn't match "c++".
    return re.compile(r"(?<![\w+#])" + re.escape(alias) + r"(?![\w+#])")


@dataclass
class _Patterns:
    # (key, pattern, case_sensitive)
    entries: list[tuple[Qual, re.Pattern, bool]]
    extras: list[tuple[str, re.Pattern]]
    levels: list[tuple[str, re.Pattern, bool]]  # (level id, pattern, case_sensitive)
    fields: list[tuple[str, re.Pattern, int]]  # (field id, pattern, alias length)


_pattern_cache: dict[int, _Patterns] = {}


def _patterns(catalog: Catalog) -> _Patterns:
    cached = _pattern_cache.get(id(catalog))
    if cached is not None:
        return cached

    entries = []
    for qual in catalog.entries.values():
        if qual.category == "degree":
            continue
        if qual.ambiguous:
            # Matched case-sensitively, exactly as written in the data file.
            raw = {normalize(a, keep_case=True) for a in catalog.raw_aliases[qual.key][1:]}
            entries += [(qual, _pattern(a), True) for a in raw if a]
        else:
            entries += [(qual, _pattern(a), False) for a in qual.aliases]

    extras = [
        (key, _pattern(normalize(alias)))
        for key, aliases in catalog.degree_extra_aliases.items()
        for alias in aliases
    ]

    levels = []
    for level in catalog.levels:
        for alias in level.aliases:
            exact_case = normalize(alias, keep_case=True)
            if exact_case in catalog.case_sensitive_level_aliases:
                levels.append((level.id, _pattern(exact_case), True))
            else:
                levels.append((level.id, _pattern(normalize(alias)), False))

    fields = [
        (fos.id, _pattern(normalize(alias)), len(normalize(alias)))
        for fos in catalog.fields
        for alias in fos.aliases
    ]

    built = _Patterns(entries, extras, levels, fields)
    _pattern_cache[id(catalog)] = built
    return built


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def _heading(text: str) -> str | None:
    return _HEADING_LOOKUP.get(normalize(text))


def split_sections(text: str) -> list[tuple[str | None, str]]:
    """
    (section, line) for every non-empty content line. Heading lines themselves
    are dropped. Lines before the first heading have section None.

    An inline label ("Certifications: AWS, PMP") only applies to its own line,
    and inside a Skills section "Languages: Python, Go" stays a skills line
    (programming languages, not spoken ones).
    """
    section = None
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        found = _heading(line)
        if found:
            section = found
            continue
        line_section = section
        if ":" in line:
            head, rest = line.split(":", 1)
            found = _heading(head)
            if found:
                line = rest.strip()
                if not line:
                    section = found
                    continue
                if not (section == "skills" and found == "languages"):
                    line_section = found
        out.append((line_section, line))
    return out


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
def _overlaps(span, spans) -> bool:
    return any(span[0] < other[1] and other[0] < span[1] for other in spans)


def _longest_non_overlapping(matches):
    """matches: [(span, value)]. Keeps the longest, dropping ones that overlap it."""
    kept = []
    for span, value in sorted(matches, key=lambda m: m[0][0] - m[0][1]):
        if not _overlaps(span, [k[0] for k in kept]):
            kept.append((span, value))
    return kept


def _is_in_progress(norm_line: str, raw_line: str, current_year: int) -> bool:
    if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", norm_line) for w in _IN_PROGRESS_WORDS):
        return True
    return any(int(y) > current_year for y in _YEAR.findall(raw_line))


def _degrees_on_line(line: str, catalog: Catalog, pats: _Patterns) -> list[str]:
    norm = normalize(line)
    keep = normalize(line, keep_case=True)

    # 1. Aliases that name one specific degree ("MBA").
    extra_matches = _longest_non_overlapping(
        [(m.span(), key) for key, pat in pats.extras for m in pat.finditer(norm)]
    )
    taken = [span for span, _ in extra_matches]
    keys = [key for _, key in extra_matches]

    # 2. Degree levels, then the longest field of study on the same line.
    level_matches = []
    for level_id, pat, case_sensitive in pats.levels:
        for m in pat.finditer(keep if case_sensitive else norm):
            if not _overlaps(m.span(), taken):
                level_matches.append((m.span(), level_id))
    level_matches = _longest_non_overlapping(level_matches)
    if not level_matches:
        return keys

    level_spans = taken + [span for span, _ in level_matches]
    best_field, best_len = None, 0
    for field_id, pat, length in pats.fields:
        for m in pat.finditer(norm):
            if length > best_len and not _overlaps(m.span(), level_spans):
                best_field, best_len = field_id, length

    by_id = {lv.id: lv for lv in catalog.levels}
    for _, level_id in level_matches:
        field_id = best_field if by_id[level_id].with_fields else None
        keys.append(catalog.degree_key(level_id, field_id))
    return keys


def scan(text: str, catalog: Catalog, current_year: int | None = None) -> list[Candidate]:
    """Keyword scan of resume text against the catalog. Deterministic."""
    if current_year is None:
        current_year = datetime.date.today().year
    pats = _patterns(catalog)
    lines = split_sections(text)
    has_education = any(section == "education" for section, _ in lines)

    found: dict[str, Candidate] = {}

    def add(qual: Qual, state: str, snippet: str):
        current = found.get(qual.key)
        if current is None:
            found[qual.key] = Candidate(qual.key, qual.name, qual.category, "scan", state, None, snippet)
        elif current.state == IN_PROGRESS and state == FOUND:
            current.state, current.snippet = FOUND, snippet

    for section, line in lines:
        norm = normalize(line)
        keep = normalize(line, keep_case=True)

        if section == "education" or not has_education:
            degree_keys = _degrees_on_line(line, catalog, pats)
            if degree_keys:
                state = IN_PROGRESS if _is_in_progress(norm, line, current_year) else FOUND
                for key in degree_keys:
                    qual = catalog.get(key)
                    if qual:
                        add(qual, state, line)

        matches = []
        for qual, pat, case_sensitive in pats.entries:
            if case_sensitive:
                # Short / ambiguous names ("Go", "R", "Excel") only count in a
                # Skills section, written with the right capitals.
                if section == "skills":
                    matches += [(m.span(), qual) for m in pat.finditer(keep)]
            else:
                matches += [(m.span(), qual) for m in pat.finditer(norm)]
        # The longest match wins where two overlap: "AWS Certified Cloud
        # Practitioner" is the certification, not also the "AWS" skill.
        for _, qual in _longest_non_overlapping(matches):
            add(qual, FOUND, line)

    return list(found.values())


# ---------------------------------------------------------------------------
# Scan + optional review
# ---------------------------------------------------------------------------
def _resolved(hits) -> bool:
    """Is the top search hit a confident enough match to suggest it?"""
    if not hits:
        return False
    top = hits[0]
    if top.tier in (EXACT, PREFIX):
        return True
    if top.tier == OVERLAP:
        return top.score >= 1.0
    return top.tier == FUZZY and top.score >= 0.85


def build_candidates(
    text: str,
    catalog: Catalog,
    reviewer: Reviewer,
    custom: list[Qual] | None = None,
    current_year: int | None = None,
) -> tuple[list[Candidate], list[dict]]:
    """
    Returns (candidates, unresolved). `unresolved` are things the reviewer
    says the scan missed that don't match anything in the list; the UI offers
    to add them as new qualifications.
    """
    candidates = scan(text, catalog, current_year)
    review = run_review(reviewer, text, [asdict(c) for c in candidates])
    if review is None:
        return candidates, []

    by_key = {c.key: c for c in candidates}
    for item in review.questionable:
        candidate = by_key.get(item.get("key"))
        if candidate is not None:
            candidate.state = QUESTIONABLE
            candidate.reason = str(item.get("reason") or "") or None

    unresolved = []
    for item in review.missed:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        category = item.get("category") or None
        field_name = str(item.get("field") or "").strip()
        query = f"{name} {field_name}".strip()
        hits = search(catalog, query, category=category, custom=custom, limit=1)
        if _resolved(hits):
            qual = hits[0].qual
            if qual.key not in by_key:
                suggestion = Candidate(qual.key, qual.name, qual.category, "reviewer", SUGGESTED, None, "")
                by_key[qual.key] = suggestion
                candidates.append(suggestion)
        else:
            unresolved.append({"category": category, "name": name, "field": field_name or None})
    return candidates, unresolved
