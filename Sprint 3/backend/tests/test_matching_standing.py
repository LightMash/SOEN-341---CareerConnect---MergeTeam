"""
"Your standing": pure logic (no database). Scores, percentile vs fraction
mode, equal_on_paper, breakdown highlights and suggestions.
"""

from matching.rules import Qual, Requirement
from matching.standing import (
    EQUAL_ON_PAPER_MESSAGE,
    NOT_ENOUGH_MESSAGE,
    NOTE,
    compute_standing,
    max_score,
    percentile,
)

PYTHON = Qual(key="skill.python", category="skill", name="Python")
DOCKER = Qual(key="skill.docker", category="skill", name="Docker")
AWS = Qual(key="skill.aws", category="skill", name="AWS")
GIT = Qual(key="skill.git", category="skill", name="Git")
EXTRA = [Qual(key=f"skill.extra{i}", category="skill", name=f"Extra {i}") for i in range(5)]
BSC_CS = Qual(key="degree.bachelors.computer_science", category="degree", name="BSc CS",
              field="computer_science", rank=3)
MSC_CS = Qual(key="degree.masters.computer_science", category="degree", name="MSc CS",
              field="computer_science", rank=4)

# Python required; Docker bonus worth 2, AWS bonus worth 1. max_score = 3.
REQS = [Requirement(PYTHON, True), Requirement(DOCKER, False, 2), Requirement(AWS, False, 1)]

# Applicants by score: 0 = Python only, 1 = +AWS, 2 = +Docker, 3 = both.
SCORE_QUALS = {0: [PYTHON], 1: [PYTHON, AWS], 2: [PYTHON, DOCKER], 3: [PYTHON, DOCKER, AWS]}


def others(*scores):
    return [list(SCORE_QUALS[s]) for s in scores]


def test_max_score_counts_bonus_weights_and_ranked_required():
    assert max_score(REQS) == 3
    assert max_score([Requirement(BSC_CS, True), Requirement(PYTHON, True)]) == 1


def test_percentile_formula_with_ties():
    # below = 2, ties = 2 (incl. seeker), N = 6 -> (2 + 1) / 6 = 50
    assert percentile(2, [0, 1, 2, 3, 3, 2]) == 50
    # rounds halves up: (0 + 0.5 * 5) / 5... all tied -> 50
    assert percentile(1, [1, 1, 1, 1, 1]) == 50
    assert percentile(3, [0, 0, 0, 0, 3]) == 90


def test_percentile_mode():
    result = compute_standing(REQS, SCORE_QUALS[2] + EXTRA, others(0, 1, 2, 3, 3), set())
    assert result["status"] == "percentile"
    assert result["pool_size"] == 6 and result["other_applicants"] == 5
    assert result["percentile"] == 50
    assert result["label"] == "Competitive"
    assert result["fraction"] is None
    assert result["note"] == NOTE
    assert result["as_of"]


def test_percentile_labels():
    strong = compute_standing(REQS, SCORE_QUALS[3], others(0, 0, 1, 2), set())
    assert strong["percentile"] == 90 and strong["label"] == "Strong"
    low = compute_standing(REQS, SCORE_QUALS[0], others(3, 3, 2, 2), set())
    assert low["percentile"] == 10 and low["label"] == "Below most applicants"
    # A low result always comes with suggestions.
    assert low["suggestions"]


def test_unqualified_applicants_are_not_in_the_pool():
    unqualified = [[DOCKER, AWS]] * 10  # no Python
    result = compute_standing(REQS, SCORE_QUALS[2], others(0, 1) + unqualified, set())
    assert result["pool_size"] == 3
    assert result["status"] == "fraction"


def test_small_pool_falls_back_to_fraction():
    result = compute_standing(REQS, SCORE_QUALS[2], others(3, 0), set())
    assert result["status"] == "fraction"
    assert result["percentile"] is None
    assert result["fraction"] == 0.67
    assert result["label"] == "Partial match"
    assert result["message"] == NOT_ENOUGH_MESSAGE
    assert result["other_applicants"] == 2


def test_fraction_labels():
    assert compute_standing(REQS, SCORE_QUALS[3], [], set())["label"] == "Strong match"
    assert compute_standing(REQS, SCORE_QUALS[0], [], set())["label"] == "Few bonus qualifications"


def test_not_qualified_has_no_standing():
    result = compute_standing(REQS, [DOCKER], others(1, 2), set())
    assert result["status"] == "not_qualified"
    assert result["percentile"] is None and result["fraction"] is None and result["label"] is None
    assert [m["key"] for m in result["missing"]] == ["skill.python"]


def test_equal_on_paper_when_max_score_is_zero():
    reqs = [Requirement(PYTHON, True), Requirement(GIT, True)]
    result = compute_standing(reqs, [PYTHON, GIT], others(0, 0, 0, 0, 0), set())
    assert result["status"] == "equal_on_paper"
    assert result["message"] == EQUAL_ON_PAPER_MESSAGE
    assert result["max_score"] == 0


def test_exceeding_a_ranked_requirement_scores_a_point():
    reqs = [Requirement(BSC_CS, True)]
    result = compute_standing(reqs, [MSC_CS], [], set())
    assert result["score"] == 1 and result["max_score"] == 1
    assert result["fraction"] == 1.0


def test_suggestions_ordered_by_improvement():
    result = compute_standing(REQS, SCORE_QUALS[0], [], set())
    suggestions = result["suggestions"]
    assert [s["key"] for s in suggestions] == ["skill.docker", "skill.aws"]
    assert suggestions[0]["current"] == 0.0 and suggestions[0]["new"] == 0.67
    assert suggestions[1]["new"] == 0.33
    assert suggestions[0]["improvement"] > suggestions[1]["improvement"]


def test_suggestions_in_percentile_mode_use_percentile():
    result = compute_standing(REQS, SCORE_QUALS[0], others(0, 1, 2, 3), set())
    top = result["suggestions"][0]
    assert top["key"] == "skill.docker"
    assert top["current"] == result["percentile"]
    assert top["new"] > top["current"]


def test_at_most_two_suggestions():
    reqs = [Requirement(PYTHON, True)] + [Requirement(q, False, 1) for q in EXTRA]
    assert len(compute_standing(reqs, [PYTHON], [], set())["suggestions"]) == 2


def test_breakdown_shares_and_highlights():
    # Pool of 5: the seeker is the only one with AWS; everyone else has Docker.
    seeker = [PYTHON, AWS] + EXTRA
    result = compute_standing(REQS, seeker, others(2, 2, 2, 2), set())
    rows = {r["key"]: r for r in result["breakdown"]}

    assert rows["skill.aws"]["has"] is True
    assert rows["skill.aws"]["share"] == 0.2
    assert rows["skill.aws"]["highlight"] == "Sets you apart"

    assert rows["skill.docker"]["has"] is False
    assert rows["skill.docker"]["share"] == 0.8
    assert rows["skill.docker"]["highlight"] == "Most applicants have this"
    assert rows["skill.docker"]["weight"] == 2


def test_breakdown_has_no_shares_in_fraction_mode():
    result = compute_standing(REQS, SCORE_QUALS[1], others(2), set())
    assert all(r["share"] is None and r["highlight"] is None for r in result["breakdown"])


def test_profile_nudge_below_five_qualifications():
    few = compute_standing(REQS, SCORE_QUALS[1], [], set())
    assert few["profile_nudge"] == (
        "Your profile lists 2 qualifications. Make sure everything from your resume is added."
    )
    many = compute_standing(REQS, SCORE_QUALS[1] + EXTRA, [], set())
    assert many["profile_nudge"] is None
