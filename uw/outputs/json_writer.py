"""Write extracted data and source summary to JSON files."""
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def write_json_outputs(model_data: Dict[str, Any], output_dir: Path):
    output_dir.mkdir(exist_ok=True)

    # extracted_data.json — everything extracted
    extracted = {
        "run_timestamp": datetime.now().isoformat(),
        "property_info": _serialize(model_data.get("property_info")),
        "rent_roll": _serialize(model_data.get("rent_roll")),
        "financials": _serialize(model_data.get("financials")),
        "assumptions": _serialize(model_data.get("assumptions")),
    }
    _write(output_dir / "extracted_data.json", extracted)

    # source_summary.json — document classification
    classified = model_data.get("classified_files", [])
    source_summary = {
        "run_timestamp": datetime.now().isoformat(),
        "files": [_serialize(cf) for cf in classified],
        "category_counts": _count_categories(classified),
    }
    _write(output_dir / "source_summary.json", source_summary)


def _write(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _count_categories(classified) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for cf in classified:
        key = cf.category.value if hasattr(cf.category, "value") else str(cf.category)
        counts[key] = counts.get(key, 0) + 1
    return counts
