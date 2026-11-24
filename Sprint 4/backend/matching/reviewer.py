"""
Optional second-pass review of a resume scan.

The keyword scan (resume_scan.py) is always on. A reviewer is an extra,
OFF-by-default step that can confirm scan results, flag doubtful ones and
point out things the scan missed. Only a disabled reviewer ships here; no
external service is called.

ADDING A REAL REVIEWER
  1. Write a class with `name`, `enabled = True` and a
     `review(resume_text, scan_results) -> ReviewResult` method.
  2. Add it to REVIEWERS below under a short name, e.g. "myprovider".
  3. Set the environment variable MATCHING_REVIEWER=myprovider.
Nothing else changes: the extract endpoint already handles errors, timeouts
and turning "missed" items into suggestions.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)

SETTING_NAME = "MATCHING_REVIEWER"
DEFAULT_TIMEOUT_SECONDS = 20


@dataclass
class ReviewResult:
    # Keys from the scan that the reviewer agrees with.
    confirmed: list[str] = field(default_factory=list)
    # [{"key": ..., "reason": ...}] scan results the reviewer doubts.
    questionable: list[dict] = field(default_factory=list)
    # [{"category": ..., "name": ..., "field": ...}] things the scan did not find.
    missed: list[dict] = field(default_factory=list)


class Reviewer(Protocol):
    name: str
    enabled: bool

    def review(self, resume_text: str, scan_results: list[dict]) -> ReviewResult: ...


class DisabledReviewer:
    """The default: reviews nothing and returns nothing."""

    name = "off"
    enabled = False

    def review(self, resume_text: str, scan_results: list[dict]) -> ReviewResult:
        return ReviewResult()


# Short name (the value of MATCHING_REVIEWER) -> reviewer class.
REVIEWERS: dict[str, type] = {
    "off": DisabledReviewer,
}


def get_reviewer() -> Reviewer:
    """The reviewer chosen by the MATCHING_REVIEWER setting ("off" when unset)."""
    choice = os.environ.get(SETTING_NAME, "").strip().lower() or "off"
    reviewer_cls = REVIEWERS.get(choice)
    if reviewer_cls is None:
        logger.warning("Unknown %s=%r; the second-pass review stays off.", SETTING_NAME, choice)
        reviewer_cls = DisabledReviewer
    return reviewer_cls()


def run_review(
    reviewer: Reviewer,
    resume_text: str,
    scan_results: list[dict],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ReviewResult | None:
    """
    Calls the reviewer, but never lets it break extraction: any exception or
    a timeout returns None, and the caller falls back to the scan alone.
    """
    if not reviewer.enabled:
        return None
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(reviewer.review, resume_text, scan_results)
        result = future.result(timeout=timeout)
        return result if isinstance(result, ReviewResult) else None
    except FutureTimeout:
        logger.warning("Second-pass review timed out after %ss; using the scan only.", timeout)
        return None
    except Exception:  # noqa: BLE001 - any reviewer failure falls back to the scan
        logger.exception("Second-pass review failed; using the scan only.")
        return None
    finally:
        # Don't wait for a reviewer that is still running after a timeout.
        pool.shutdown(wait=False)
