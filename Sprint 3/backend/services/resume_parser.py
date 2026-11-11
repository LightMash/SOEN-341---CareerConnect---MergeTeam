"""
Owner: AI Resume Feedback (US-16, Task 16.1)

Turns a stored resume file (PDF or DOCX) into plain text that can be sent
to the AI. This file knows nothing about the database, FastAPI or Gemini:
it takes a path on disk and returns a string. That keeps it easy to test
and easy to reuse (e.g. for AI Job Matching later).

Supported formats match what routers/resume.py accepts on upload
(ALLOWED_CONTENT_TYPES): .pdf and .docx.
"""

import os
import re

from docx import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError

# Upper bound on how much text we send to the AI. A dense 2-page resume is
# roughly 5-8k characters, so 20k leaves plenty of room while protecting us
# from a huge file blowing up the cost / token limit of a single request.
MAX_CHARS = 20_000


class ResumeParseError(Exception):
    """Raised when we can't get usable text out of a resume file.

    The message is written for the end user: the router turns it straight
    into an HTTP 422 response, so it must not leak server paths.
    """


def extract_text(filepath: str) -> str:
    """
    Read the resume at `filepath` and return its text, cleaned up and capped
    at MAX_CHARS. Picks the reader from the file's extension, which we can
    trust because routers/resume.py chose it from the real content type when
    the file was saved (it never keeps the user's own extension).
    """
    extension = os.path.splitext(filepath)[1].lower()

    if extension == ".pdf":
        raw = _extract_pdf(filepath)
    elif extension == ".docx":
        raw = _extract_docx(filepath)
    else:
        raise ResumeParseError(f"Unsupported resume format: {extension or 'unknown'}.")

    text = _clean(raw)

    if not text:
        # Most common cause: a scanned PDF, which is just an image of text.
        # Reading it would need OCR, which is out of scope for this sprint.
        raise ResumeParseError(
            "We couldn't find any text in this resume. If it's a scanned "
            "document, please upload a version with selectable text."
        )

    return text[:MAX_CHARS]


def _extract_pdf(filepath: str) -> str:
    try:
        reader = PdfReader(filepath)
        if reader.is_encrypted:
            raise ResumeParseError("This PDF is password-protected. Please upload an unlocked copy.")
        # extract_text() can return None for an empty page, hence `or ""`.
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ResumeParseError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise ResumeParseError("This PDF appears to be damaged and couldn't be read.") from exc


def _extract_docx(filepath: str) -> str:
    try:
        document = Document(filepath)
    except Exception as exc:  # python-docx raises several unrelated error types
        raise ResumeParseError("This Word document appears to be damaged and couldn't be read.") from exc

    lines = [paragraph.text for paragraph in document.paragraphs]

    # Many resume templates lay out sections with TABLES (e.g. dates in the
    # left column, job details in the right). document.paragraphs skips table
    # contents entirely, so without this loop those resumes lose most of
    # their text. Merged cells show up more than once, so skip repeats.
    for table in document.tables:
        for row in table.rows:
            seen = []
            for cell in row.cells:
                if cell.text not in seen:
                    seen.append(cell.text)
            lines.append(" | ".join(seen))

    return "\n".join(lines)


def _clean(text: str) -> str:
    """Normalize whitespace so the AI sees tidy text and we waste fewer tokens."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", " ")             # non-breaking spaces from Word
    text = re.sub(r"[ \t]+", " ", text)            # runs of spaces/tabs -> one space
    text = re.sub(r" *\n *", "\n", text)           # trim spaces around line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)         # at most one blank line in a row
    return text.strip()
