"""Scan a property folder and return all files with metadata."""
from pathlib import Path
from typing import List
import os


IGNORED_DIRS = {"output", "__pycache__", ".git", ".claude", "node_modules"}
IGNORED_EXTENSIONS = {".pyc", ".pyo", ".tmp", ".DS_Store"}
MAX_FILE_SIZE_MB = 200


def scan_folder(folder: Path) -> List[Path]:
    """Return all relevant files in folder, sorted by name."""
    files = []
    for item in sorted(folder.rglob("*")):
        if item.is_file():
            if any(part in IGNORED_DIRS for part in item.parts):
                continue
            if item.suffix.lower() in IGNORED_EXTENSIONS:
                continue
            size_mb = item.stat().st_size / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                continue
            files.append(item)
    return files


def get_file_size_str(path: Path) -> str:
    size = path.stat().st_size
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"
