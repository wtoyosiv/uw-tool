"""Extract property info (name, type, units, sqft, asking price) from documents."""
from typing import Dict, Any, Optional
import re
import logging

from uw.underwriting.models import PropertyInfo, FileCategory

logger = logging.getLogger(__name__)

PROPERTY_TYPE_KEYWORDS = {
    "multifamily": ["apartment", "multifamily", "multi-family", "units", "residential",
                    "duplex", "triplex", "fourplex", "complex", "townhome", "townhouse"],
    "retail": ["retail", "shopping", "strip center", "strip mall", "storefront", "commercial"],
    "office": ["office", "professional", "medical office", "flex office"],
    "industrial": ["industrial", "warehouse", "distribution", "flex", "manufacturing", "storage"],
    "mixed_use": ["mixed-use", "mixed use", "mixed_use", "live-work"],
    "land": ["land", "lot", "parcel", "acres", "ground", "undeveloped"],
    "covered_land": ["covered land", "covered-land", "redevelopment", "assemblage"],
    "net_lease": ["net lease", "nnn", "nn lease", "triple net", "single tenant"],
}

PRICE_PATTERNS = [
    r"asking.{0,20}price.{0,20}\$?([\d,]+(?:\.\d{0,2})?)",
    r"list.{0,10}price.{0,20}\$?([\d,]+(?:\.\d{0,2})?)",
    r"sale.{0,10}price.{0,20}\$?([\d,]+(?:\.\d{0,2})?)",
    r"purchase.{0,10}price.{0,20}\$?([\d,]+(?:\.\d{0,2})?)",
    r"offered.{0,20}\$?([\d,]+(?:\.\d{0,2})?)",
    r"offering[:\s]*\$?([\d,]+(?:\.\d{0,2})?)",
    r"priced.{0,10}at.{0,10}\$?([\d,]+(?:\.\d{0,2})?)",
    r"list(?:ed)?.{0,5}at.{0,10}\$?([\d,]+(?:\.\d{0,2})?)",
    r"\$\s?([\d,]+(?:\.\d{0,2})?)\s*(?:million|mm|M)\b",
]

UNIT_COUNT_PATTERNS = [
    r"([\d,]+)\s*(?:unit|apt|apartment|residence|home|door)s?\b",
    r"(?:total|number of).{0,10}unit.{0,20}([\d,]+)",
]

SQFT_PATTERNS = [
    r"([\d,]+)\s*(?:sq\.?\s*ft|sqft|sf|square feet|rentable)",
    r"(?:total|gross|rentable|leasable|nra).{0,10}(?:sq|area|sf|sqft).{0,20}([\d,]+)",
]


def extract_property_info(file_data: Dict[str, Dict[str, Any]], folder_name: str) -> PropertyInfo:
    prop = PropertyInfo(name=folder_name)

    all_text = ""
    for data in file_data.values():
        all_text += "\n" + data.get("text", "")

    all_text_lower = all_text.lower()

    # Detect property type
    best_type = "unknown"
    best_score = 0
    for ptype, keywords in PROPERTY_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in all_text_lower)
        if score > best_score:
            best_score = score
            best_type = ptype
    prop.property_type = best_type

    # Extract asking price
    for pattern in PRICE_PATTERNS:
        match = re.search(pattern, all_text_lower)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                value = float(raw)
                # Handle millions shorthand
                if "million" in match.group(0).lower() or "mm" in match.group(0).lower():
                    value *= 1_000_000
                # Sanity check: real property between $50k and $2B
                if 50_000 <= value <= 2_000_000_000:
                    prop.asking_price = value
                    break
            except ValueError:
                pass

    # Extract unit count
    for pattern in UNIT_COUNT_PATTERNS:
        match = re.search(pattern, all_text_lower)
        if match:
            try:
                count = int(match.group(1).replace(",", ""))
                if 1 <= count <= 10_000:
                    prop.total_units = count
                    break
            except ValueError:
                pass

    # Extract total sqft
    for pattern in SQFT_PATTERNS:
        match = re.search(pattern, all_text_lower)
        if match:
            try:
                sqft = float(match.group(1).replace(",", ""))
                if 500 <= sqft <= 5_000_000:
                    prop.total_sqft = sqft
                    break
            except ValueError:
                pass

    # Extract year built
    year_match = re.search(r"(?:built|year built|constructed)[:\s]+(\d{4})", all_text_lower)
    if year_match:
        yr = int(year_match.group(1))
        if 1800 <= yr <= 2030:
            prop.year_built = yr

    return prop
