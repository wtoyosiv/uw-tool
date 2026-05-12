"""Read Excel and CSV files into pandas DataFrames."""
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def read_excel(path: Path) -> Dict[str, object]:
    """Return dict of {sheet_name: DataFrame} for Excel, or {'data': df} for CSV."""
    import pandas as pd

    ext = path.suffix.lower()
    result = {}

    try:
        if ext in (".xlsx", ".xls", ".xlsm"):
            xl = pd.ExcelFile(str(path), engine="openpyxl" if ext == ".xlsx" else None)
            for sheet in xl.sheet_names:
                try:
                    df = xl.parse(sheet, header=None)
                    result[sheet] = df
                except Exception as e:
                    logger.warning(f"Could not parse sheet '{sheet}' in {path.name}: {e}")
        elif ext == ".csv":
            # Pre-scan to find the widest row, then force that many columns so that
            # rows with trailing commas (e.g. vacant units) are padded with NaN
            # instead of being dropped as "bad lines".
            import io
            raw = path.read_text(encoding="utf-8-sig", errors="replace")
            max_cols = max(
                (len(line.split(",")) for line in raw.splitlines() if line.strip()),
                default=1,
            )
            df = pd.read_csv(
                io.StringIO(raw),
                header=None,
                names=range(max_cols),
            )
            result["data"] = df
        else:
            logger.warning(f"Unsupported spreadsheet format: {ext}")
    except Exception as e:
        logger.error(f"Excel read error {path.name}: {e}")

    return result


def df_to_text(df) -> str:
    """Convert DataFrame to plain text for pattern matching."""
    try:
        return df.to_string(header=False, index=False)
    except Exception:
        return ""
