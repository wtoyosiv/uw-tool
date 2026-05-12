"""Extract rent roll data from classified files."""
from typing import Dict, Any, List, Optional, Tuple
import re
import logging

from uw.underwriting.models import RentRollData, RentRollUnit, FileCategory

logger = logging.getLogger(__name__)

UNIT_COL_PATTERNS = [r"unit", r"apt", r"suite", r"#", r"id", r"number"]
TENANT_COL_PATTERNS = [r"tenant", r"name", r"occupant", r"resident", r"lessee"]
RENT_COL_PATTERNS = [r"rent", r"monthly.?rent", r"current.?rent", r"in.?place", r"lease.?rate"]
MARKET_RENT_PATTERNS = [r"market.?rent", r"market", r"asking", r"street.?rent"]
SQFT_COL_PATTERNS = [r"sq.?ft", r"sqft", r"sf", r"size", r"area"]
VACANT_PATTERNS = [r"vacant", r"vacancy", r"empty", r"available", r"avail"]


def extract_rent_roll(file_data: Dict[str, Dict[str, Any]]) -> RentRollData:
    """Find and extract rent roll data from all file data."""
    rent_roll_files = [
        (path, data) for path, data in file_data.items()
        if data.get("category") == FileCategory.RENT_ROLL
    ]

    if not rent_roll_files:
        logger.info("No rent roll file found; attempting extraction from all spreadsheets")
        rent_roll_files = [
            (path, data) for path, data in file_data.items()
            if data.get("sheets")
        ]

    best_result = RentRollData()

    for path, data in rent_roll_files:
        result = _try_extract_from_sheets(data.get("sheets", {}), path)
        if result.total_units > best_result.total_units:
            best_result = result

    if best_result.total_units == 0:
        for path, data in file_data.items():
            if data.get("text"):
                result = _try_extract_from_text(data["text"], path)
                if result.total_units > best_result.total_units:
                    best_result = result

    return best_result


def _try_extract_from_sheets(sheets: Dict, source_path: str) -> RentRollData:
    import pandas as pd

    best = RentRollData()
    for sheet_name, df in sheets.items():
        try:
            result = _parse_dataframe(df, source_path, sheet_name)
            if result.total_units > best.total_units:
                best = result
        except Exception as e:
            logger.debug(f"Sheet parse failed: {e}")
    return best


def _parse_dataframe(df, source_path: str, sheet_name: str = "") -> RentRollData:
    import pandas as pd
    import numpy as np

    df = df.copy()

    header_row = _find_header_row(df)
    if header_row is None:
        return RentRollData()

    df.columns = [str(c).strip().lower() for c in df.iloc[header_row]]
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    df = df.dropna(how="all")

    cols = list(df.columns)

    unit_col = _find_col(cols, UNIT_COL_PATTERNS)
    tenant_col = _find_col(cols, TENANT_COL_PATTERNS)
    rent_col = _find_col(cols, RENT_COL_PATTERNS)
    market_rent_col = _find_col(cols, MARKET_RENT_PATTERNS)
    sqft_col = _find_col(cols, SQFT_COL_PATTERNS)

    if rent_col is None and unit_col is None:
        return RentRollData()

    units: List[RentRollUnit] = []
    for _, row in df.iterrows():
        unit = RentRollUnit()

        if unit_col:
            unit.unit_id = str(row.get(unit_col, "")).strip()
        if tenant_col:
            unit.tenant_name = str(row.get(tenant_col, "")).strip()
        if sqft_col:
            unit.sqft = _to_float(row.get(sqft_col))
        if rent_col:
            unit.current_rent = _to_float(row.get(rent_col))
        if market_rent_col:
            unit.market_rent = _to_float(row.get(market_rent_col))

        tenant_lower = unit.tenant_name.lower()
        if any(v in tenant_lower for v in ["vacant", "vacancy", "available", "empty", ""]):
            if unit.current_rent is None or unit.current_rent == 0:
                unit.vacant = True

        # Include unit if we have any identifying data at all
        has_data = unit.unit_id or unit.tenant_name or unit.current_rent is not None or unit.market_rent is not None or unit.sqft is not None
        if has_data:
            units.append(unit)

    if not units:
        return RentRollData()

    total_units = len(units)
    vacant_units = sum(1 for u in units if u.vacant)
    total_sqft = sum(u.sqft for u in units if u.sqft) or 0.0
    in_place_monthly = sum(u.current_rent for u in units if u.current_rent and not u.vacant) or 0.0
    market_monthly = sum(
        u.market_rent or u.current_rent or 0 for u in units if not u.vacant
    ) or 0.0
    gpr_monthly = sum(
        u.market_rent or u.current_rent or 0 for u in units
    ) or 0.0

    vacancy_rate = vacant_units / total_units if total_units > 0 else 0.0

    return RentRollData(
        units=units,
        total_units=total_units,
        total_sqft=total_sqft,
        gross_potential_rent_monthly=gpr_monthly,
        in_place_rent_monthly=in_place_monthly,
        market_rent_monthly=market_monthly,
        vacant_units=vacant_units,
        physical_vacancy_rate=vacancy_rate,
        source_file=source_path,
        extraction_confidence=0.85,
    )


def _find_header_row(df) -> Optional[int]:
    """Find the row most likely containing column headers."""
    for i in range(min(10, len(df))):
        row = df.iloc[i]
        row_text = " ".join(str(v).lower() for v in row if str(v) != "nan")
        hits = sum(
            1 for patterns in [UNIT_COL_PATTERNS, TENANT_COL_PATTERNS, RENT_COL_PATTERNS, SQFT_COL_PATTERNS]
            for p in patterns if re.search(p, row_text)
        )
        if hits >= 2:
            return i
    return None


def _find_col(cols: List[str], patterns: List[str]) -> Optional[str]:
    for col in cols:
        for pat in patterns:
            if re.search(pat, col):
                return col
    return None


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    s = str(value).replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        f = float(s)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def _try_extract_from_text(text: str, source_path: str) -> RentRollData:
    """Rough extraction from plain text when no structured sheet is available."""
    lines = text.split("\n")
    units = []
    for line in lines:
        numbers = re.findall(r"\$?([\d,]+(?:\.\d{2})?)", line)
        floats = [_to_float(n) for n in numbers if _to_float(n)]
        rent_candidates = [f for f in floats if 200 < f < 20000]
        if rent_candidates:
            units.append(RentRollUnit(current_rent=rent_candidates[0]))

    if not units:
        return RentRollData()

    monthly = sum(u.current_rent for u in units if u.current_rent) or 0.0
    return RentRollData(
        units=units,
        total_units=len(units),
        in_place_rent_monthly=monthly,
        gross_potential_rent_monthly=monthly,
        source_file=source_path,
        extraction_confidence=0.3,
        notes=["Extracted from text — low confidence. Verify manually."],
    )
