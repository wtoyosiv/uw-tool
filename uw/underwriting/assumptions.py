"""Load and build UWAssumptions from config + extracted property info."""
import json
from pathlib import Path
from typing import Optional
import logging

from uw.underwriting.models import UWAssumptions, PropertyInfo

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_assumptions() -> dict:
    path = CONFIG_DIR / "default_assumptions.json"
    with open(path) as f:
        return json.load(f)


def load_templates() -> dict:
    path = CONFIG_DIR / "property_type_templates.json"
    with open(path) as f:
        return json.load(f)


def merge_assumptions(defaults: dict, prop: PropertyInfo) -> UWAssumptions:
    """Merge default assumptions with property-type template and extracted property info."""
    templates = load_templates()
    template = templates.get(prop.property_type, templates.get("multifamily", {}))

    # Start from defaults, overlay template
    merged = {**defaults}
    for k, v in template.items():
        if k in UWAssumptions.model_fields:
            merged[k] = v

    # Overlay with known facts from extraction
    if prop.purchase_price:
        merged["purchase_price"] = prop.purchase_price
    elif prop.asking_price:
        merged["purchase_price"] = prop.asking_price

    if prop.property_type and prop.property_type != "unknown":
        merged["property_type"] = prop.property_type

    if prop.total_units:
        merged["total_units"] = prop.total_units

    if prop.total_sqft:
        merged["total_sqft"] = prop.total_sqft

    merged["hold_years"] = prop.hold_years

    flags = []
    if merged.get("purchase_price", 0) == 0:
        flags.append("ASSUMPTION: purchase_price not found — set to $0")
    if prop.property_type == "unknown":
        flags.append("ASSUMPTION: property_type unknown — defaulting to multifamily logic")

    merged["assumption_flags"] = flags

    return UWAssumptions(**{k: v for k, v in merged.items() if k in UWAssumptions.model_fields})
