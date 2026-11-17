"""
Qualification matching: pure logic only (no database, no API).
normalize, the catalog, satisfies/evaluate and search.
"""

import pytest

from matching.catalog import alias_collisions, get_catalog
from matching.normalize import normalize
from matching.rules import (
    BONUS_MISSING,
    MET,
    MISSING,
    POSSIBLE,
    Qual,
    Requirement,
    evaluate,
    satisfies,
)
from matching.search import search


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


def deg(level: str, rank: int, field: str | None) -> Qual:
    return Qual(key=f"degree.{level}.{field or 'any'}", category="degree", name=f"{level} {field}",
                field=field, rank=rank)


def skill(name: str) -> Qual:
    return Qual(key=f"skill.{name}", category="skill", name=name.title(), aliases=(name,))


BSC_CS = deg("bachelors", 3, "computer_science")
MSC_CS = deg("masters", 4, "computer_science")
PHD_CS = deg("phd", 5, "computer_science")
BSC_BIO = deg("bachelors", 3, "biology")
BSC_ANY = deg("bachelors", 3, None)
DEC_CS = deg("college", 2, "computer_science")
PYTHON = skill("python")
DOCKER = skill("docker")


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Ph.D.", "phd"),
        ("PhD", "phd"),
        ("Baccalauréat", "baccalaureat"),
        ("Génie   Logiciel", "genie logiciel"),
        ("C++", "c++"),
        ("C#", "c#"),
        ("Python/Java, SQL", "python java sql"),
        ("  Bachelor's  ", "bachelors"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_normalize_phd_spellings_are_equal():
    assert normalize("Ph.D.") == normalize("PhD") == normalize("PHD") == normalize("Ph.D")


def test_normalize_keep_case():
    assert normalize("Go, R", keep_case=True) == "Go R"


# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------
def test_catalog_keys_unique_and_well_formed(catalog):
    # Keys are dict keys (so unique by construction); build_catalog raises on a duplicate.
    assert all(key == qual.key for key, qual in catalog.entries.items())
    assert all("." in key for key in catalog.entries)


def test_catalog_implies_keys_exist(catalog):
    for have, implied in catalog.implies:
        assert have in catalog.entries, have
        assert implied in catalog.entries, implied


def test_generated_degree_entries_and_aliases(catalog):
    phd_cs = catalog.get("degree.phd.computer_science")
    assert phd_cs.name == "PhD — Computer Science"
    assert phd_cs.rank == 5 and phd_cs.field == "computer_science"
    for alias in ("doctorate in computer science", "phd computer science", "doctorat en informatique"):
        assert alias in phd_cs.aliases

    any_bachelor = catalog.get("degree.bachelors.any")
    assert any_bachelor.name == "Bachelor's degree (any field)"
    assert any_bachelor.field is None
    assert "baccalaureat" in any_bachelor.aliases

    assert "mba" in catalog.get("degree.masters.business").aliases


@pytest.mark.parametrize("level, rank", [("secondary", 1), ("college", 2), ("bachelors", 3), ("masters", 4), ("phd", 5)])
def test_degree_level_ranks(catalog, level, rank):
    assert catalog.get(f"degree.{level}.any").rank == rank


def test_catalog_contents(catalog):
    by_category = {}
    for qual in catalog.entries.values():
        by_category.setdefault(qual.category, []).append(qual)
    assert len(by_category["language"]) == 10
    assert len(by_category["certification"]) >= 20
    assert len(by_category["skill"]) >= 80
    for cls in ("1", "2", "3", "4a", "4b", "4c", "5", "6", "8"):
        assert f"license.qc.class_{cls}" in catalog.entries
    for ambiguous in ("skill.go", "skill.r", "skill.c", "skill.excel"):
        assert catalog.get(ambiguous).ambiguous


def test_no_alias_maps_to_two_entries_in_one_category(catalog):
    collisions = alias_collisions(catalog)
    assert collisions == [], "aliases shared within a category:\n" + "\n".join(map(str, collisions))


# ---------------------------------------------------------------------------
# satisfies / evaluate
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "have, need, implies, expected",
    [
        (PYTHON, PYTHON, set(), True),  # exact match
        (MSC_CS, BSC_CS, set(), True),  # higher rank satisfies lower
        (BSC_CS, MSC_CS, set(), False),  # lower rank fails
        (BSC_BIO, BSC_CS, set(), False),  # same rank, different field
        (PHD_CS, BSC_BIO, set(), False),  # higher rank, different field
        (BSC_BIO, BSC_ANY, set(), True),  # "any field" accepts any field
        (MSC_CS, BSC_ANY, set(), True),
        (DEC_CS, BSC_ANY, set(), False),
        (DOCKER, PYTHON, set(), False),
        (DOCKER, PYTHON, {("skill.docker", "skill.python")}, True),  # implies
        (PYTHON, DOCKER, {("skill.docker", "skill.python")}, False),  # implies is one-way
    ],
)
def test_satisfies(have, need, implies, expected):
    assert satisfies(have, need, implies) is expected


def test_evaluate_met_missing_and_exceeds():
    reqs = [Requirement(BSC_CS, True), Requirement(DOCKER, True), Requirement(PYTHON, False, 2)]
    result = evaluate(reqs, [MSC_CS, PYTHON], set())

    status = {i.key: i for i in result.items}
    assert status[BSC_CS.key].status == MET and status[BSC_CS.key].exceeds is True
    assert status[DOCKER.key].status == MISSING
    assert status[PYTHON.key].status == MET and status[PYTHON.key].exceeds is False
    assert result.qualified is False


def test_exact_rank_does_not_exceed():
    result = evaluate([Requirement(BSC_CS, True)], [BSC_CS], set())
    assert result.items[0].status == MET and result.items[0].exceeds is False


def test_bonus_missing_is_still_qualified():
    result = evaluate([Requirement(PYTHON, True), Requirement(DOCKER, False)], [PYTHON], set())
    assert [i.status for i in result.items] == [MET, BONUS_MISSING]
    assert result.qualified is True


def test_no_requirements_is_qualified():
    assert evaluate([], [], set()).qualified is True


def test_possible_match_from_custom_qualification():
    need = Qual(key="cert.whmis", category="certification", name="WHMIS (SIMDUT)", aliases=("whmis", "simdut"))
    mine = Qual(key="custom.7", category="certification", name="WHMIS.", custom=True, aliases=("whmis",))
    unrelated = Qual(key="custom.8", category="certification", name="Forklift", custom=True)

    result = evaluate([Requirement(need, True)], [mine, unrelated], set())
    assert result.items[0].status == POSSIBLE
    assert result.items[0].possible_name == "WHMIS."
    # A possible match is not verified, so the seeker isn't qualified yet.
    assert result.qualified is False


def test_possible_needs_same_category_and_custom():
    need = Qual(key="cert.whmis", category="certification", name="WHMIS", aliases=("whmis",))
    other_category = Qual(key="custom.9", category="skill", name="WHMIS", custom=True)
    result = evaluate([Requirement(need, False)], [other_category], set())
    assert result.items[0].status == BONUS_MISSING


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
def test_search_doctorate_in_computer_science(catalog):
    hits = search(catalog, "doctorate in computer science")
    assert hits[0].qual.key == "degree.phd.computer_science"
    assert hits[0].qual.name == "PhD — Computer Science"


@pytest.mark.parametrize(
    "query, expected_key",
    [
        ("pyhton", "skill.python"),  # typo
        ("javscript", "skill.javascript"),  # typo
        ("Ph.D.", "degree.phd.any"),
        ("c++", "skill.cpp"),
        ("C#", "skill.csharp"),
        ("baccalauréat en génie logiciel", "degree.bachelors.software_engineering"),
        ("MBA", "degree.masters.business"),
        ("classe 5", "license.qc.class_5"),
    ],
)
def test_search_top_result(catalog, query, expected_key):
    assert search(catalog, query)[0].qual.key == expected_key


def test_search_limit_dedup_and_category(catalog):
    hits = search(catalog, "computer science")
    assert len(hits) <= 10
    assert len({h.qual.key for h in hits}) == len(hits)
    assert all(h.qual.category == "skill" for h in search(catalog, "py", category="skill"))
    assert search(catalog, "   ") == []


def test_search_includes_custom(catalog):
    custom = Qual(key="custom.1", category="skill", name="Underwater welding",
                  aliases=("underwater welding",), custom=True)
    hits = search(catalog, "underwater welding", custom=[custom])
    assert hits[0].qual.key == "custom.1"
