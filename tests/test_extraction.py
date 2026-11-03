import io

import pytest
from reportlab.pdfgen import canvas

from app.extraction import ExtractionError, extract_text


def _make_pdf(text: str) -> bytes:
    """Helper function to create a PDF in memory."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, text)
    c.save()
    return buffer.getvalue()


def test_extract_pdf_returns_correct_text() -> None:
    pdf_bytes = _make_pdf("Hello RAG world")
    result = extract_text(pdf_bytes, "application/pdf")
    assert "Hello RAG world" in result


def test_extract_pdf_plain_passes_through() -> None:
    result = extract_text(b"Just some text", "text/plain")
    assert result == "Just some text"


def test_extract_markdown_passes_through() -> None:
    result = extract_text(b"# Heading\nSome markdown text.", "text/markdown")
    assert "# Heading" in result


def test_extract_unsupported_content_type_raises() -> None:
    with pytest.raises(ExtractionError, match="Unsupported content type"):
        extract_text(b"data", "application/unsupported")


def test_extract_corrupted_pdf_raises() -> None:
    corrupted_pdf = b"%PDF-1.4\n%Corrupted content"
    with pytest.raises(ExtractionError, match="PDF read failed"):
        extract_text(corrupted_pdf, "application/pdf")


def test_extract_bad_utf8_txt_raises() -> None:
    bad_utf8 = b"\xff\xfe\xfd"
    with pytest.raises(ExtractionError, match="TXT decode failed"):
        extract_text(bad_utf8, "text/plain")
