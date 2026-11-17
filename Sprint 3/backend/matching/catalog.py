"""
The standard qualification list. It lives in catalog_data.json (not in the
database) and is loaded once, then cached for the life of the process.

Degree entries are not written out in the JSON file: the file only lists the
degree levels and the fields of study, and every "level x field" entry (plus
one "any field" entry per level) is generated here when the catalog loads.
"""

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

from .normalize import normalize
from .rules import CATEGORIES, Qual

DATA_FILE = os.path.join(os.path.dirname(__file__), "catalog_data.json")

# Ways people join a degree level and a field: "PhD Computer Science",
# "PhD in Computer Science", "Maîtrise en informatique", "Bachelor of Commerce".
_CONNECTORS = (" ", " in ", " en ", " of ")


@dataclass(frozen=True)
class DegreeLevel:
    id: str
    name: str
    rank: int
    with_fields: bool
    aliases: tuple[str, ...]  # as written in the data file (original case)


@dataclass(frozen=True)
class FieldOfStudy:
    id: str
    name: str
    aliases: tuple[str, ...]


@dataclass
class Catalog:
    entries: dict[str, Qual] = field(default_factory=dict)
    implies: set[tuple[str, str]] = field(default_factory=set)
    levels: list[DegreeLevel] = field(default_factory=list)
    fields: list[FieldOfStudy] = field(default_factory=list)
    # Level aliases that only count when written in capitals in a resume
    # ("DES" vs the French word "des"), normalized with keep_case=True.
    case_sensitive_level_aliases: set[str] = field(default_factory=set)
    # Degree aliases that name one specific degree ("MBA"), original case.
    degree_extra_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Aliases exactly as written in the data file, for case-sensitive matching.
    raw_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def get(self, key: str) -> Qual | None:
        return self.entries.get(key)

    def degree_key(self, level_id: str, field_id: str | None) -> str:
        return f"degree.{level_id}.{field_id or 'any'}"


def _norm_aliases(*groups) -> tuple[str, ...]:
    """Normalize and de-duplicate aliases, keeping their first-seen order."""
    seen: dict[str, None] = {}
    for group in groups:
        for alias in group:
            n = normalize(alias)
            if n:
                seen.setdefault(n, None)
    return tuple(seen)


def build_catalog(data: dict) -> Catalog:
    catalog = Catalog()
    catalog.levels = [
        DegreeLevel(
            id=lv["id"],
            name=lv["name"],
            rank=lv["rank"],
            with_fields=lv.get("with_fields", True),
            aliases=tuple(lv["aliases"]),
        )
        for lv in data["degree_levels"]
    ]
    catalog.fields = [
        FieldOfStudy(id=f["id"], name=f["name"], aliases=tuple(f["aliases"])) for f in data["fields"]
    ]
    catalog.case_sensitive_level_aliases = {
        normalize(a, keep_case=True) for a in data.get("case_sensitive_level_aliases", [])
    }
    extras = {k: tuple(v) for k, v in data.get("degree_extra_aliases", {}).items()}
    catalog.degree_extra_aliases = extras

    def add(qual: Qual, raw: tuple[str, ...]):
        if qual.key in catalog.entries:
            raise ValueError(f"Duplicate qualification key in catalog: {qual.key}")
        if qual.category not in CATEGORIES:
            raise ValueError(f"Unknown category {qual.category!r} for {qual.key}")
        catalog.entries[qual.key] = qual
        catalog.raw_aliases[qual.key] = raw

    # Generated degrees.
    for level in catalog.levels:
        any_key = catalog.degree_key(level.id, None)
        any_name = level.name if level.id == "secondary" else f"{level.name} (any field)"
        any_raw = (any_name,) + level.aliases + extras.get(any_key, ())
        add(
            Qual(
                key=any_key,
                category="degree",
                name=any_name,
                field=None,
                rank=level.rank,
                aliases=_norm_aliases(any_raw),
            ),
            any_raw,
        )
        if not level.with_fields:
            continue
        for fos in catalog.fields:
            key = catalog.degree_key(level.id, fos.id)
            combos = [
                la + connector + fa
                for la in level.aliases
                for fa in fos.aliases
                for connector in _CONNECTORS
            ]
            name = f"{level.name} — {fos.name}"
            raw = (name,) + tuple(combos) + extras.get(key, ())
            add(
                Qual(
                    key=key,
                    category="degree",
                    name=name,
                    field=fos.id,
                    rank=level.rank,
                    aliases=_norm_aliases(raw),
                ),
                raw,
            )

    # Everything else is written out in full in the data file.
    for entry in data["entries"]:
        raw = (entry["name"],) + tuple(entry.get("aliases", []))
        add(
            Qual(
                key=entry["key"],
                category=entry["category"],
                name=entry["name"],
                field=entry.get("field"),
                rank=entry.get("rank"),
                aliases=_norm_aliases(raw),
                ambiguous=bool(entry.get("ambiguous", False)),
            ),
            raw,
        )

    for have, implied in data.get("implies", []):
        catalog.implies.add((have, implied))
    return catalog


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """The catalog, read from disk the first time and cached afterwards."""
    with open(DATA_FILE, encoding="utf-8") as f:
        return build_catalog(json.load(f))


def alias_collisions(catalog: Catalog) -> list[tuple[str, str, list[str]]]:
    """(category, alias, [keys]) for every alias that points at two or more entries in one category."""
    seen: dict[tuple[str, str], list[str]] = {}
    for qual in catalog.entries.values():
        for alias in qual.aliases:
            seen.setdefault((qual.category, alias), []).append(qual.key)
    return [(cat, alias, keys) for (cat, alias), keys in seen.items() if len(keys) > 1]
