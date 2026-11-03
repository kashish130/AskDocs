import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

PDF = "application/pdf"
TXT = "text/plain"
MD = "text/markdown"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ExtractionError(Exception):
    """Custom exception for extraction errors."""

    pass


def extract_text(data: bytes, content_type: str) -> str:
    """Extract text from a file based on its content type.

    Args:
        data (bytes): The file data.
        content_type (str): The MIME type of the file.

    Returns:
        str: The extracted text.

    Raises:
        ExtractionError: If the content type is unsupported or extraction fails.
    """
    if content_type == PDF:
        return _extract_pdf(data)
    if content_type in (TXT, MD):
        return _extract_txt(data)
    if content_type == DOCX:
        return _extract_docx(data)
    raise ExtractionError(f"Unsupported content type: {content_type}")


def _extract_pdf(data: bytes) -> str:
    """Extract text from a PDF file."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as e:
        raise ExtractionError(f"PDF read failed: {e}") from e
    return "\n\n".join(p.strip() for p in pages if p.strip())


def _extract_txt(data: bytes) -> str:
    """Extract text from a TXT file."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ExtractionError(f"TXT decode failed: {e}") from e


def _extract_docx(data: bytes) -> str:
    """Extract text from a DOCX file."""
    from docx import Document as DocxDocument

    try:
        doc = DocxDocument(io.BytesIO(data))
    except Exception as e:
        raise ExtractionError(f"DOCX extraction failed: {e}") from e
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
