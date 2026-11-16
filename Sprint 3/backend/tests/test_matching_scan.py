"""
Resume import: the keyword scan and the optional second-pass reviewer.
Pure logic on resume text (no PDF, no database).
"""

import time

import pytest

from matching.catalog import get_catalog
from matching.resume_scan import FOUND, IN_PROGRESS, QUESTIONABLE, SUGGESTED, build_candidates, scan
from matching.reviewer import DisabledReviewer, ReviewResult, run_review

YEAR = 2026

SAMPLE_RESUME = """Jane Demo
jane.demo@example.test

EDUCATION
Bachelor of Engineering, Software Engineering - Concordia University, 2021 - 2025
Ph.D. in Computer Science (expected 2029)

SKILLS
Languages: Python, JavaScript, C++, C#, Go, R
Tools: Docker, Git, Microsoft Excel, PostgreSQL

EXPERIENCE
Developer, Acme Inc. Built internal tools; go to client meetings and Excel at teamwork.

CERTIFICATIONS
AWS Certified Cloud Practitioner
WHMIS

LANGUAGES
English, Français
"""


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


def states(candidates):
    return {c.key: c.state for c in candidates}


@pytest.fixture(scope="module")
def sample(catalog):
    return states(scan(SAMPLE_RESUME, catalog, YEAR))


@pytest.mark.parametrize(
    "key",
    [
        "degree.bachelors.software_engineering",
        "skill.python",
        "skill.javascript",
        "skill.cpp",
        "skill.csharp",
        "skill.go",
        "skill.r",
        "skill.docker",
        "skill.git",
        "skill.excel",
        "skill.postgresql",
        "cert.aws_cloud_practitioner",
        "cert.whmis",
        "language.english",
        "language.french",
    ],
)
def test_sample_resume_finds(sample, key):
    assert sample.get(key) == FOUND


def test_expected_year_marks_degree_in_progress(sample):
    assert sample["degree.phd.computer_science"] == IN_PROGRESS


def test_longest_match_wins(sample):
    # "AWS Certified Cloud Practitioner" is the certification, not also the AWS skill.
    assert "skill.aws" not in sample


def test_javascript_does_not_produce_java(catalog):
    found = states(scan("SKILLS\nJavaScript, TypeScript", catalog, YEAR))
    assert "skill.javascript" in found
    assert "skill.java" not in found


def test_ambiguous_go_only_counts_in_skills(catalog):
    outside = states(scan("EXPERIENCE\nI like to Go hiking and Excel at sports.", catalog, YEAR))
    assert "skill.go" not in outside and "skill.excel" not in outside

    inside = states(scan("SKILLS\nGo, Rust", catalog, YEAR))
    assert inside.get("skill.go") == FOUND


def test_ambiguous_is_case_sensitive(catalog):
    found = states(scan("SKILLS\ngo, r, excel", catalog, YEAR))
    assert not {"skill.go", "skill.r", "skill.excel"} & set(found)


def test_c_does_not_match_cpp(catalog):
    found = states(scan("Skills: C++, C#", catalog, YEAR))
    assert "skill.c" not in found
    assert {"skill.cpp", "skill.csharp"} <= set(found)


@pytest.mark.parametrize(
    "line, expected_state",
    [
        ("Bachelor of Science in Computer Science, expected 2029", IN_PROGRESS),
        ("BSc Computer Science (in progress)", IN_PROGRESS),
        ("Baccalauréat en informatique (en cours)", IN_PROGRESS),
        ("PhD candidate, Computer Science", IN_PROGRESS),
        ("BSc Computer Science, 2019 - 2031", IN_PROGRESS),
        ("BSc Computer Science, 2018 - 2022", FOUND),
    ],
)
def test_degree_in_progress_detection(catalog, line, expected_state):
    found = scan(f"EDUCATION\n{line}", catalog, YEAR)
    degrees = [c for c in found if c.category == "degree"]
    assert degrees and degrees[0].state == expected_state


@pytest.mark.parametrize(
    "line, key",
    [
        ("Baccalauréat en génie logiciel, Polytechnique Montréal", "degree.bachelors.software_engineering"),
        ("Maîtrise en informatique", "degree.masters.computer_science"),
        ("MBA, HEC Montréal", "degree.masters.business"),
        ("DEC en sciences de la nature", "degree.college.any"),
        ("B.A. Psychology", "degree.bachelors.psychology"),
        ("Master of Science", "degree.masters.any"),
    ],
)
def test_degree_detection(catalog, line, key):
    found = states(scan(f"FORMATION\n{line}", catalog, YEAR))
    assert found.get(key) == FOUND


def test_degrees_only_searched_in_education_section(catalog):
    text = "EXPERIENCE\nTeaching assistant for a Master of Science course\nEDUCATION\nBSc Biology"
    found = states(scan(text, catalog, YEAR))
    assert "degree.bachelors.biology" in found
    assert "degree.masters.any" not in found


def test_french_des_word_is_not_a_degree(catalog):
    found = states(scan("FORMATION\nBaccalauréat en gestion des ressources humaines", catalog, YEAR))
    assert "degree.secondary.any" not in found
    assert "degree.bachelors.human_resources" in found


def test_snippet_is_the_source_line(catalog):
    found = scan("SKILLS\nPython, Docker", catalog, YEAR)
    assert {c.snippet for c in found} == {"Python, Docker"}


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------
class FakeReviewer:
    name = "fake"
    enabled = True

    def __init__(self, result=None, error=None, delay=0.0):
        self.result, self.error, self.delay = result, error, delay

    def review(self, resume_text, scan_results):
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


def test_disabled_reviewer_returns_scan_unchanged(catalog):
    expected = scan(SAMPLE_RESUME, catalog, YEAR)
    candidates, unresolved = build_candidates(SAMPLE_RESUME, catalog, DisabledReviewer(), current_year=YEAR)
    assert candidates == expected
    assert unresolved == []
    assert DisabledReviewer().review("text", []) == ReviewResult()


def test_reviewer_that_raises_still_returns_scan(catalog):
    expected = scan(SAMPLE_RESUME, catalog, YEAR)
    reviewer = FakeReviewer(error=RuntimeError("provider down"))
    candidates, unresolved = build_candidates(SAMPLE_RESUME, catalog, reviewer, current_year=YEAR)
    assert candidates == expected and unresolved == []


def test_reviewer_timeout_returns_none():
    assert run_review(FakeReviewer(result=ReviewResult(), delay=0.5), "text", [], timeout=0.05) is None


def test_enabled_reviewer_flags_and_suggests(catalog):
    reviewer = FakeReviewer(result=ReviewResult(
        confirmed=["skill.python"],
        questionable=[{"key": "skill.r", "reason": "Listed without any project using it"}],
        missed=[
            {"category": "skill", "name": "Kubernetes", "field": None},
            {"category": "degree", "name": "Master's", "field": "Computer Science"},
            {"category": "skill", "name": "Underwater basket weaving", "field": None},
        ],
    ))
    candidates, unresolved = build_candidates(SAMPLE_RESUME, catalog, reviewer, current_year=YEAR)
    by_key = {c.key: c for c in candidates}

    assert by_key["skill.r"].state == QUESTIONABLE
    assert by_key["skill.r"].reason == "Listed without any project using it"
    assert by_key["skill.python"].state == FOUND
    assert by_key["skill.kubernetes"].state == SUGGESTED and by_key["skill.kubernetes"].source == "reviewer"
    assert by_key["degree.masters.computer_science"].state == SUGGESTED
    assert unresolved == [{"category": "skill", "name": "Underwater basket weaving", "field": None}]
