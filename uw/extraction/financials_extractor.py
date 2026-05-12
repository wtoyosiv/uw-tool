"""Extract T12 / pro forma financial data from files."""
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import re
import logging

from uw.underwriting.models import (
    HistoricalFinancials, FinancialLineItem, FileCategory
)

logger = logging.getLogger(__name__)

INCOME_KEYWORDS = [
    "rental income", "rent income", "gross rent", "base rent", "scheduled rent",
    "gross potential", "gpr", "effective gross", "egi", "other income",
    "laundry", "parking", "pet fee", "storage", "late fees", "miscellaneous income",
    "security deposit",
    "total income", "total revenue",
]

EXPENSE_KEYWORDS = [
    "property tax", "real estate tax", "taxes",
    "insurance", "hazard insurance",
    "management fee", "management",
    "payroll", "wages", "salary",
    "repairs", "maintenance", "r&m",
    "utilities", "electric", "gas", "water", "sewer",
    "trash", "landscaping", "grounds",
    "reserves", "replacement reserves", "capex",
    "admin", "administrative", "office",
    "marketing", "advertising",
    "legal", "professional fees",
    "total expenses", "total operating",
]

NOI_KEYWORDS = ["net operating income", "noi", "net income"]


def extract_financials(file_data: Dict[str, Dict[str, Any]]) -> HistoricalFinancials:
    """Extract the best available historical financials."""
    t12_files = [
        (p, d) for p, d in file_data.items()
        if d.get("category") == FileCategory.T12
    ]
    pf_files = [
        (p, d) for p, d in file_data.items()
        if d.get("category") == FileCategory.PRO_FORMA
    ]
    om_files = [
        (p, d) for p, d in file_data.items()
        if d.get("category") == FileCategory.OFFERING_MEMO
    ]

    # Prefer T12 → pro forma → OM
    for candidates, label in [(t12_files, "T12"), (pf_files, "Pro Forma"), (om_files, "Offering Memo")]:
        for path, data in candidates:
            result = _extract_from_file(data, label, path)
            if result.gross_revenue > 0 or result.total_expenses > 0:
                return result

    # Last resort: scan all files with text
    for path, data in file_data.items():
        result = _extract_from_file(data, "Unclassified", path)
        if result.gross_revenue > 0:
            return result

    return HistoricalFinancials(notes=["No financial data extracted from documents."])


def _extract_from_file(data: Dict[str, Any], label: str, path: str) -> HistoricalFinancials:
    sheets = data.get("sheets", {})
    text = data.get("text", "")

    if Path(path).suffix.lower() == ".pdf":
        result = _parse_financial_pdf(Path(path), label, path)
        if result.gross_revenue > 0 or result.total_expenses > 0:
            return result

    if sheets:
        for sheet_name, df in sheets.items():
            result = _parse_financial_sheet(df, label, path)
            if result.gross_revenue > 0 or result.total_expenses > 0:
                return result

    if text:
        return _parse_financial_text(text, label, path)

    return HistoricalFinancials()


def _parse_financial_pdf(pdf_path: Path, label: str, source: str) -> HistoricalFinancials:
    """Extract financials from PDFs where labels and monthly values are separate blocks."""
    try:
        import fitz
    except ImportError:
        return HistoricalFinancials()

    income_items: List[FinancialLineItem] = []
    expense_items: List[FinancialLineItem] = []
    extracted_noi = 0.0

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.debug(f"Could not parse financial PDF blocks for {pdf_path.name}: {e}")
        return HistoricalFinancials()

    try:
        for page in doc:
            for row_label, amount in _extract_pdf_rows(page):
                classification = _classify_financial_label(row_label)
                if classification == "income":
                    income_items.append(FinancialLineItem(
                        label=row_label,
                        amount=amount,
                        source="pdf_extracted",
                    ))
                elif classification == "expense":
                    expense_items.append(FinancialLineItem(
                        label=row_label,
                        amount=amount,
                        source="pdf_extracted",
                    ))
                elif classification == "noi":
                    extracted_noi = amount
    finally:
        doc.close()

    gross_revenue = _sum_items(income_items) or 0.0
    total_expenses = _sum_items(expense_items) or 0.0
    noi = extracted_noi or (gross_revenue - total_expenses)

    return HistoricalFinancials(
        year_label=label,
        income_items=income_items,
        expense_items=expense_items,
        gross_revenue=gross_revenue,
        total_expenses=total_expenses,
        noi=noi,
        source_file=source,
        extraction_confidence=0.75 if gross_revenue or total_expenses else 0.0,
    )


def _extract_pdf_rows(page) -> List[Tuple[str, float]]:
    labels = []
    numeric_blocks = []
    rows: List[Tuple[str, float]] = []

    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[:5]
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            continue

        first_number_idx = next((i for i, line in enumerate(lines) if _to_float(line) is not None), None)
        if first_number_idx is not None:
            label_parts = lines[:first_number_idx]
            values = [_to_float(line) for line in lines[first_number_idx:] if _to_float(line) is not None]
            if label_parts and values:
                rows.append((" ".join(label_parts), values[-1]))
            elif values:
                numeric_blocks.append((x0, y0, y1, values[-1]))
        elif x0 < 130:
            label = " ".join(lines)
            if not _is_pdf_header_label(label):
                labels.append((y0, y1, label))

    used_labels = set()
    for x0, y0, y1, amount in numeric_blocks:
        if x0 < 100:
            continue
        best_idx = None
        best_distance = 9999.0
        num_mid = (y0 + y1) / 2
        for idx, (ly0, ly1, label) in enumerate(labels):
            if idx in used_labels:
                continue
            label_mid = (ly0 + ly1) / 2
            distance = abs(label_mid - num_mid)
            overlaps = ly0 <= y1 and ly1 >= y0
            if overlaps or distance <= 16:
                if distance < best_distance:
                    best_idx = idx
                    best_distance = distance
        if best_idx is not None:
            used_labels.add(best_idx)
            rows.append((labels[best_idx][2], amount))

    return rows


def _is_pdf_header_label(label: str) -> bool:
    lower = label.lower()
    if lower.startswith((
        "blue door",
        "properties:",
        "fund type:",
        "period range:",
        "accounting basis:",
        "level of detail:",
        "include zero",
        "income statement",
        "created on",
        "page ",
    )):
        return True
    return lower in {
        "account name jan 2025 feb 2025 mar 2025 apr 2025 may 2025 jun 2025 jul 2025 aug 2025 sep 2025 oct 2025 nov 2025 dec 2025 total",
        "income",
        "expense",
        "operating income & expense",
        "utilities",
        "materials",
        "other income & expense",
        "other expense",
    }


def _parse_financial_sheet(df, label: str, source: str) -> HistoricalFinancials:
    import pandas as pd

    income_items: List[FinancialLineItem] = []
    expense_items: List[FinancialLineItem] = []
    extracted_noi = 0.0

    for _, row in df.iterrows():
        row_values = [str(v).strip() for v in row if str(v) not in ("nan", "")]
        if len(row_values) < 2:
            continue

        label_cell = row_values[0].lower()
        # Exclude percentage columns — they contain "%" and are never dollar amounts.
        # Then prefer the rightmost remaining value (most recent year in multi-year T12s).
        dollar_values = [
            _to_float(v) for v in row_values[1:]
            if "%" not in str(v) and _to_float(v) is not None
        ]
        if not dollar_values:
            continue

        amount = dollar_values[-1]  # rightmost dollar column = most recent year

        classification = _classify_financial_label(label_cell)
        if classification == "income":
            income_items.append(FinancialLineItem(
                label=row_values[0],
                amount=amount,
                source="extracted",
            ))
        elif classification == "expense":
            expense_items.append(FinancialLineItem(
                label=row_values[0],
                amount=amount,
                source="extracted",
            ))
        elif classification == "noi":
            extracted_noi = amount

    gross_revenue = _sum_items(income_items) or 0.0
    total_expenses = _sum_items(expense_items) or 0.0
    noi = extracted_noi or (gross_revenue - total_expenses)

    return HistoricalFinancials(
        year_label=label,
        income_items=income_items,
        expense_items=expense_items,
        gross_revenue=gross_revenue,
        total_expenses=total_expenses,
        noi=noi,
        source_file=source,
        extraction_confidence=0.7,
    )


def _parse_financial_text(text: str, label: str, source: str) -> HistoricalFinancials:
    """Extract financials from plain text using keyword + number matching."""
    income_items: List[FinancialLineItem] = []
    expense_items: List[FinancialLineItem] = []
    extracted_noi = 0.0

    lines = text.split("\n")
    for line in lines:
        line_lower = line.lower()
        amount = _find_largest_number(line)
        if amount is None or amount <= 0:
            continue

        classification = _classify_financial_label(line_lower)
        if classification == "income":
            income_items.append(FinancialLineItem(
                label=line.strip()[:80],
                amount=amount,
                source="text_extracted",
            ))
        elif classification == "expense":
            expense_items.append(FinancialLineItem(
                label=line.strip()[:80],
                amount=amount,
                source="text_extracted",
            ))
        elif classification == "noi":
            extracted_noi = amount

    gross_revenue = _sum_items(income_items) or 0.0
    total_expenses = _sum_items(expense_items) or 0.0
    noi = extracted_noi or (gross_revenue - total_expenses)

    return HistoricalFinancials(
        year_label=label,
        income_items=income_items,
        expense_items=expense_items,
        gross_revenue=gross_revenue,
        total_expenses=total_expenses,
        noi=noi,
        source_file=source,
        extraction_confidence=0.4,
        notes=["Extracted from text — verify all line items manually."],
    )


def _sum_items(items: List[FinancialLineItem]) -> float:
    totals = [i for i in items if "total" in i.label.lower()]
    if totals:
        return max(i.amount for i in totals)
    return sum(i.amount for i in items)


def _classify_financial_label(label: str) -> str:
    label_lower = label.lower().strip()

    if "net operating income" in label_lower or label_lower.startswith("noi"):
        return "noi"

    if label_lower in ("net income", "net other income", "total expense", "total other expense"):
        return ""

    if "total operating income" in label_lower or label_lower == "total income":
        return "income"

    if "laundry facilities" in label_lower:
        return "expense"

    if any(kw in label_lower for kw in EXPENSE_KEYWORDS):
        return "expense"

    if any(kw in label_lower for kw in INCOME_KEYWORDS):
        return "income"

    return ""


def _find_largest_number(line: str) -> Optional[float]:
    numbers = re.findall(r"\$?([\d,]+(?:\.\d{0,2})?)", line)
    floats = [_to_float(n) for n in numbers if _to_float(n) and _to_float(n) > 100]
    return max(floats) if floats else None


def _to_float(value) -> Optional[float]:
    s = str(value).replace(",", "").replace("$", "").replace("(", "-").replace(")", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None
