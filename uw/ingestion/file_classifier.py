"""Classify files by likely purpose based on filename and extension."""
from pathlib import Path
from typing import List, Dict, Tuple
import re

from uw.underwriting.models import FileCategory, ClassifiedFile


CATEGORY_PATTERNS: List[Tuple[FileCategory, float, List[str]]] = [
    (FileCategory.RENT_ROLL, 0.95, [
        r"rent.?roll", r"rentroll", r"tenant.?list", r"rent.?schedule",
        r"unit.?mix", r"unitmix", r"occupancy.?report",
    ]),
    (FileCategory.T12, 0.90, [
        r"t12", r"trailing.?12", r"t-12", r"trailing.?twelve",
        r"historical.?financials?", r"actuals?", r"ytd.?financials?",
        r"income.?statement", r"p.?&.?l", r"profit.?loss",
    ]),
    (FileCategory.PRO_FORMA, 0.90, [
        r"pro.?forma", r"proforma", r"projection", r"stabilized",
        r"budget", r"forward.?looking",
    ]),
    (FileCategory.OFFERING_MEMO, 0.90, [
        r"\bom\b", r"offering.?memo", r"memorandum", r"package",
        r"deal.?summary", r"investment.?summary", r"executive.?summary",
    ]),
    (FileCategory.LEASE, 0.85, [
        r"\blease\b", r"lease.?abstract", r"tenant.?lease",
        r"lease.?agreement", r"nnn.?lease", r"ground.?lease",
    ]),
    (FileCategory.TAX, 0.90, [
        r"property.?tax", r"tax.?bill", r"tax.?assessment",
        r"assessor", r"parcel", r"\btax\b",
    ]),
    (FileCategory.INSURANCE, 0.90, [
        r"insurance", r"hazard", r"liability", r"coverage",
        r"premium", r"binder",
    ]),
    (FileCategory.DEBT, 0.90, [
        r"debt.?quote", r"loan.?quote", r"loan.?terms?",
        r"mortgage", r"lender", r"term.?sheet", r"financing",
        r"debt.?service", r"loan.?summary",
    ]),
    (FileCategory.SALES_COMPS, 0.85, [
        r"sales?.?comp", r"sale.?comparable", r"sold.?comp",
        r"comparable.?sales?",
    ]),
    (FileCategory.LEASE_COMPS, 0.85, [
        r"lease.?comp", r"rent.?comp", r"comparable.?lease",
        r"market.?rent",
    ]),
    (FileCategory.APPRAISAL, 0.90, [
        r"appraisal", r"appraise", r"bpo", r"broker.?opinion",
        r"valuation",
    ]),
    (FileCategory.SURVEY, 0.90, [
        r"survey", r"alta", r"site.?plan", r"boundary",
        r"plat",
    ]),
    (FileCategory.ZONING, 0.85, [
        r"zoning", r"entitlement", r"land.?use", r"variance",
        r"permit",
    ]),
    (FileCategory.PHOTOS, 0.95, [
        r"photo", r"image", r"picture", r"aerial", r"interior",
        r"exterior",
    ]),
    (FileCategory.NOTES, 0.80, [
        r"notes?", r"memo", r"summary", r"overview", r"comments?",
        r"scratch",
    ]),
]

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic"}


def classify_files(files: List[Path]) -> List[ClassifiedFile]:
    return [_classify_one(f) for f in files]


def _classify_one(path: Path) -> ClassifiedFile:
    ext = path.suffix.lower()
    name_lower = path.stem.lower()

    if ext in PHOTO_EXTENSIONS:
        return ClassifiedFile(
            path=str(path),
            filename=path.name,
            extension=ext,
            size_bytes=path.stat().st_size,
            category=FileCategory.PHOTOS,
            confidence=0.99,
            notes="Image file",
        )

    best_category = FileCategory.UNKNOWN
    best_confidence = 0.0

    for category, base_confidence, patterns in CATEGORY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, name_lower):
                if base_confidence > best_confidence:
                    best_confidence = base_confidence
                    best_category = category
                break

    if best_category == FileCategory.UNKNOWN:
        best_confidence = 0.3

    return ClassifiedFile(
        path=str(path),
        filename=path.name,
        extension=ext,
        size_bytes=path.stat().st_size,
        category=best_category,
        confidence=best_confidence,
        notes="",
    )


def get_category_color(category: FileCategory) -> str:
    colors = {
        FileCategory.RENT_ROLL: "green",
        FileCategory.T12: "cyan",
        FileCategory.PRO_FORMA: "blue",
        FileCategory.OFFERING_MEMO: "magenta",
        FileCategory.LEASE: "yellow",
        FileCategory.TAX: "red",
        FileCategory.INSURANCE: "orange3",
        FileCategory.DEBT: "bright_blue",
        FileCategory.SALES_COMPS: "bright_cyan",
        FileCategory.LEASE_COMPS: "bright_green",
        FileCategory.APPRAISAL: "bright_magenta",
        FileCategory.PHOTOS: "dim",
        FileCategory.NOTES: "white",
        FileCategory.UNKNOWN: "dim white",
    }
    return colors.get(category, "white")
