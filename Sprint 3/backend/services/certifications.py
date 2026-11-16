"""
Owner: AI Job Study Partner

Useful certifications for a job posting.

The list is a small CURATED catalog on purpose, not something the AI writes:
Gemini can invent plausible-looking links, and a broken or wrong certification
URL is worse than none. So every entry below has a link to its official page,
and matching a posting is plain keyword search (deterministic, free, instant,
works with no API key).

To add a certification, append one entry to CATALOG and open its link once to
check it still works.
"""

import re
from dataclasses import dataclass

from models import Job

MAX_RESULTS = 5


@dataclass(frozen=True)
class Certification:
    id: str
    name: str
    issuer: str
    level: str  # "Entry" or "Intermediate"
    topic: str  # the skill it matches, shown as "Matches: <topic>"
    summary: str
    url: str  # the OFFICIAL page
    keywords: tuple[str, ...]  # lowercase; matched as whole words/phrases


CATALOG: tuple[Certification, ...] = (
    Certification(
        id="pcep",
        name="PCEP: Certified Entry-Level Python Programmer",
        issuer="Python Institute",
        level="Entry",
        topic="Python",
        summary="Proves the Python basics.",
        url="https://pythoninstitute.org/pcep",
        keywords=("python", "django", "flask", "fastapi", "pandas"),
    ),
    Certification(
        id="github-foundations",
        name="GitHub Foundations (GH-900)",
        issuer="Microsoft and GitHub",
        level="Entry",
        topic="Git",
        summary="Covers Git, pull requests and GitHub workflows.",
        url="https://learn.microsoft.com/credentials/certifications/github-foundations",
        keywords=("git", "github", "version control", "pull request", "pull requests", "ci/cd", "devops"),
    ),
    Certification(
        id="aws-cloud-practitioner",
        name="AWS Certified Cloud Practitioner",
        issuer="Amazon Web Services",
        level="Entry",
        topic="Cloud",
        summary="Cloud basics for roles that deploy to AWS.",
        url="https://aws.amazon.com/certification/certified-cloud-practitioner/",
        keywords=("aws", "amazon web services", "cloud", "ec2", "s3", "lambda", "devops"),
    ),
    Certification(
        id="azure-fundamentals",
        name="Microsoft Azure Fundamentals (AZ-900)",
        issuer="Microsoft",
        level="Entry",
        topic="Cloud",
        summary="The Azure equivalent, if the company runs on Azure.",
        url="https://learn.microsoft.com/credentials/certifications/azure-fundamentals/",
        keywords=("azure", "cloud", "microsoft"),
    ),
    Certification(
        id="ckad",
        name="Certified Kubernetes Application Developer (CKAD)",
        issuer="CNCF and Linux Foundation",
        level="Intermediate",
        topic="Containers",
        summary="A hands-on exam for running apps in containers.",
        url="https://www.cncf.io/training/certification/ckad/",
        keywords=("kubernetes", "k8s", "docker", "container", "containers", "microservices", "devops"),
    ),
)


def _contains(text: str, keyword: str) -> bool:
    """Whole-word match, so "git" does not match "digital" and "s3" not "ss3x"."""
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def find_for_job(job: Job) -> list[Certification]:
    """Certifications whose keywords appear in the posting, best match first."""
    text = " ".join([job.title or "", job.category or "", job.description or ""]).lower()
    scored = []
    for position, cert in enumerate(CATALOG):
        hits = sum(1 for keyword in cert.keywords if _contains(text, keyword))
        if hits:
            scored.append((-hits, position, cert))  # most hits first, catalog order breaks ties
    return [cert for _, _, cert in sorted(scored)[:MAX_RESULTS]]
