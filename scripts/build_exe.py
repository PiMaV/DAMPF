"""Build DAMPF GUI as a standalone binary using PyInstaller.

Local output: dist/DAMPF.exe (Windows) or dist/DAMPF (Linux).
GitHub Releases rename to DAMPF-vX.Y.Z.exe / DAMPF-vX.Y.Z-linux-x86_64.
Run from repo root with: uv run python scripts/build_exe.py
"""
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
    icon_png = REPO_ROOT / "icon" / "icon_256.png"
    if sys.platform == "win32":
        if not icon_ico.is_file():
            print("icon/icon.ico not found")
            sys.exit(1)
    elif not icon_png.is_file() and not icon_ico.is_file():
        print("icon/icon_256.png (or icon/icon.ico) not found")
        sys.exit(1)
    args = [sys.executable, "-m", "PyInstaller", str(spec)]
    subprocess.run(args, cwd=REPO_ROOT, check=True)


if __name__ == "__main__":
    main()
