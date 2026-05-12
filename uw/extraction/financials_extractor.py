"""Extract T12 / pro forma financial data from files."""
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

    if sheets:
        for sheet_name, df in sheets.items():
            result = _parse_financial_sheet(df, label, path)
            if result.gross_revenue > 0 or result.total_expenses > 0:
                return result

    if text:
        return _parse_financial_text(text, label, path)

    return HistoricalFinancials()


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

        if any(kw in label_cell for kw in INCOME_KEYWORDS):
            income_items.append(FinancialLineItem(
                label=row_values[0],
                amount=amount,
                source="extracted",
            ))
        elif any(kw in label_cell for kw in EXPENSE_KEYWORDS):
            expense_items.append(FinancialLineItem(
                label=row_values[0],
                amount=amount,
                source="extracted",
            ))
        elif any(kw in label_cell for kw in NOI_KEYWORDS):
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

        if any(kw in line_lower for kw in INCOME_KEYWORDS):
            income_items.append(FinancialLineItem(
                label=line.strip()[:80],
                amount=amount,
                source="text_extracted",
            ))
        elif any(kw in line_lower for kw in EXPENSE_KEYWORDS):
            expense_items.append(FinancialLineItem(
                label=line.strip()[:80],
                amount=amount,
                source="text_extracted",
            ))
        elif any(kw in line_lower for kw in NOI_KEYWORDS):
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
