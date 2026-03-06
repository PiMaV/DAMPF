"""Build DAMPF GUI as a standalone .exe using PyInstaller. Run from repo root with: uv run python scripts/build_exe.py"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Windows uses ";" for PyInstaller --add-data, Unix ":"
DATA_SEP = ";" if os.name == "nt" else ":"


def main() -> None:
    icon_dir = REPO_ROOT / "icon"
    icon_ico = icon_dir / "icon.ico"
    if not icon_ico.exists():
        print("icon/icon.ico not found")
        sys.exit(1)
    gui = REPO_ROOT / "gui.py"
    # Bundle whole icon dir so _icon_path() finds icon/icon.ico in MEIPASS
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "DAMPF",
        f"--icon={icon_ico}",
        f"--add-data={icon_dir}{DATA_SEP}icon",
        "--paths",
        str(REPO_ROOT),
        "--hidden-import",
        "indexer",
        "--hidden-import",
        "db_writer",
        "--hidden-import",
        "outlier_detection",
        "--hidden-import",
        "key_lut",
        "--hidden-import",
        "app_settings",
        "--hidden-import",
        "schema_io",
        "--collect-all",
        "PyQt6",
        str(gui),
    ]
    subprocess.run(args, cwd=REPO_ROOT)


if __name__ == "__main__":
    main()
