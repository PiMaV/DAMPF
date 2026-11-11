# naming_docs.py - the naming pages the GUI shows. Same files as docs/naming/.

from __future__ import annotations

import sys
from pathlib import Path

CHEAT_SHEET = "cheat_sheet_v2.md"
FULL = "file_names_explained_v2.md"


def bundle_root() -> Path:
    """Repo root in a checkout, extraction dir in a frozen build."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def naming_doc_path(filename: str) -> Path:
    return bundle_root() / "docs" / "naming" / filename


def load_naming_doc(filename: str) -> str:
    path = naming_doc_path(filename)
    if not path.is_file():
        return f"Naming page not found:\n{path}"
    return path.read_text(encoding="utf-8")
