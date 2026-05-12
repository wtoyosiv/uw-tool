"""Dispatch file reading to the appropriate reader and return normalized content."""
from pathlib import Path
from typing import Dict, Any, List
import logging

from uw.underwriting.models import ClassifiedFile, FileCategory
from uw.ingestion.pdf_reader import read_pdf
from uw.ingestion.excel_reader import read_excel, df_to_text
from uw.ingestion.docx_reader import read_docx

logger = logging.getLogger(__name__)

EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".csv"}
TEXT_EXTENSIONS = {".txt", ".md", ".json"}
SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".pdf"}


def read_files(classified: List[ClassifiedFile]) -> Dict[str, Dict[str, Any]]:
    """Return {filepath: {text, sheets, category, filename}} for all readable files."""
    results = {}
    for cf in classified:
        path = Path(cf.path)
        ext = cf.extension.lower()

        if cf.category == FileCategory.PHOTOS:
            continue

        content: Dict[str, Any] = {
            "filename": cf.filename,
            "category": cf.category,
            "confidence": cf.confidence,
            "text": "",
            "sheets": {},
        }

        try:
            if ext == ".pdf":
                content["text"] = read_pdf(path)
            elif ext in EXCEL_EXTENSIONS:
                sheets = read_excel(path)
                content["sheets"] = sheets
                all_text = []
                for sheet_df in sheets.values():
                    all_text.append(df_to_text(sheet_df))
                content["text"] = "\n".join(all_text)
            elif ext == ".docx":
                content["text"] = read_docx(path)
            elif ext in TEXT_EXTENSIONS:
                content["text"] = path.read_text(encoding="utf-8", errors="replace")
            else:
                logger.debug(f"Skipping unsupported file type: {ext}")
                continue
        except Exception as e:
            logger.error(f"Failed to read {cf.filename}: {e}")

        results[cf.path] = content

    return results
