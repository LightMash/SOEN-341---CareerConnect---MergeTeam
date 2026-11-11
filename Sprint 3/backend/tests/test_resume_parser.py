"""
Unit tests for services/resume_parser.py

These only touch files in a temporary folder: no database, no AI calls.
Test files are built on the fly so we don't commit binary fixtures.
"""

import pytest
from docx import Document

from services.resume_parser import MAX_CHARS, ResumeParseError, extract_text


# -----------------------------------------------------------------------------
# Helpers that build small resume files inside pytest's tmp_path
# -----------------------------------------------------------------------------
def make_pdf(path, lines: list[str]) -> str:
    """
    Writes a minimal one-page PDF whose page shows `lines` as real text.
    Pass [] to get a page with no text at all (like a scanned resume).
    Built by hand because pypdf can read text but can't write it.
    """
    ops = ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({safe}) Tj T*")  # T* = move to the next line
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()

    full_path = path / "resume.pdf"
    full_path.write_bytes(bytes(out))
    return str(full_path)


def make_docx(path, paragraphs: list[str], table_rows: list[list[str]] | None = None) -> str:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    if table_rows:
        table = document.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r, row in enumerate(table_rows):
            for c, value in enumerate(row):
                table.cell(r, c).text = value
    full_path = path / "resume.docx"
    document.save(full_path)
    return str(full_path)


# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------
def test_pdf_text_is_extracted(tmp_path):
    path = make_pdf(tmp_path, ["Jane Doe", "Software Developer", "Python, React, SQL"])

    text = extract_text(path)

    assert "Jane Doe" in text
    assert "Software Developer" in text
    assert "Python, React, SQL" in text


def test_pdf_without_text_is_rejected_with_helpful_message(tmp_path):
    path = make_pdf(tmp_path, [])

    with pytest.raises(ResumeParseError, match="scanned"):
        extract_text(path)


def test_corrupted_pdf_is_rejected(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"this is definitely not a pdf")

    with pytest.raises(ResumeParseError, match="damaged"):
        extract_text(str(path))


# -----------------------------------------------------------------------------
# DOCX
# -----------------------------------------------------------------------------
def test_docx_paragraphs_are_extracted(tmp_path):
    path = make_docx(tmp_path, ["Jane Doe", "Experience", "Built a REST API with FastAPI"])

    text = extract_text(path)

    assert "Jane Doe" in text
    assert "Built a REST API with FastAPI" in text


def test_docx_table_contents_are_extracted(tmp_path):
    # Many resume templates put dates and job details side by side in a table.
    path = make_docx(
        tmp_path,
        ["Jane Doe"],
        table_rows=[["2024 - 2025", "Intern at Acme: wrote unit tests"]],
    )

    text = extract_text(path)

    assert "2024 - 2025" in text
    assert "Intern at Acme: wrote unit tests" in text


def test_empty_docx_is_rejected(tmp_path):
    path = make_docx(tmp_path, ["", "   "])

    with pytest.raises(ResumeParseError):
        extract_text(path)


def test_corrupted_docx_is_rejected(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip file, so not a docx")

    with pytest.raises(ResumeParseError, match="damaged"):
        extract_text(str(path))


# -----------------------------------------------------------------------------
# Shared behaviour
# -----------------------------------------------------------------------------
def test_unsupported_extension_is_rejected(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text("plain text resume")

    with pytest.raises(ResumeParseError, match="Unsupported"):
        extract_text(str(path))


def test_whitespace_is_normalized(tmp_path):
    path = make_docx(tmp_path, ["Jane    Doe", "", "", "", "", "Skills: Python"])

    text = extract_text(path)

    assert "Jane Doe" in text          # repeated spaces collapsed
    assert "\n\n\n" not in text        # no more than one blank line in a row
    assert "Skills: Python" in text    # non-breaking space became a normal space


def test_very_long_resume_is_capped(tmp_path):
    path = make_docx(tmp_path, ["word " * 10_000])  # ~50k characters

    text = extract_text(path)

    assert len(text) == MAX_CHARS
