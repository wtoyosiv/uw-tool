"""Extract text from PDF files using pymupdf."""
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def read_pdf(path: Path) -> str:
    """Return extracted text from a PDF file."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)
    except ImportError:
        logger.warning("pymupdf not available, trying pypdf")
        return _read_pdf_fallback(path)
    except Exception as e:
        logger.error(f"PDF read error {path.name}: {e}")
        return ""


def _read_pdf_fallback(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
    except Exception as e:
        logger.error(f"pypdf fallback failed {path.name}: {e}")
        return ""
