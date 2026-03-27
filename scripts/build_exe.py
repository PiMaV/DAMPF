"""Build DAMPF GUI as a standalone .exe using PyInstaller. Run from repo root with: uv run python scripts/build_exe.py"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    spec = REPO_ROOT / "build" / "DAMPF.spec"
    if not spec.is_file():
        print("build/DAMPF.spec not found")
        sys.exit(1)
    icon_ico = REPO_ROOT / "icon" / "icon.ico"
    if not icon_ico.is_file():
        print("icon/icon.ico not found")
        sys.exit(1)
    args = [sys.executable, "-m", "PyInstaller", str(spec)]
    subprocess.run(args, cwd=REPO_ROOT)


if __name__ == "__main__":
    main()
