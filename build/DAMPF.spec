# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# SPECPATH is set by PyInstaller; resolve repo root via pyproject.toml (parent.parent is unreliable).
_spec = Path(SPECPATH).resolve()
_repo_root = _spec.parent
while _repo_root != _repo_root.parent:
    if (_repo_root / "pyproject.toml").is_file():
        break
    _repo_root = _repo_root.parent
else:
    raise RuntimeError("Could not find repo root (pyproject.toml) from spec path")
_icon_dir = _repo_root / "icon"
_gui_script = _repo_root / "app" / "dampf" / "gui.py"
# Windows prefers .ico; Linux desktop icon embedding works better with PNG.
_icon_path = _icon_dir / ("icon.ico" if sys.platform == "win32" else "icon_256.png")

datas = [
    (str(_icon_dir), "icon"),
    (str(_repo_root / "docs" / "naming" / "cheat_sheet_v2.md"), "docs/naming"),
    (str(_repo_root / "docs" / "naming" / "file_names_explained_v2.md"), "docs/naming"),
]
binaries = []
hiddenimports = [
    "dampf.indexer",
    "dampf.db_writer",
    "dampf.outlier_detection",
    "dampf.key_lut",
    "dampf.app_settings",
    "dampf.naming_rules",
    "dampf.naming_docs",
]
tmp_ret = collect_all("PyQt6")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    [str(_gui_script)],
    pathex=[str(_repo_root / "app")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DAMPF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(_icon_path)] if _icon_path.is_file() else None,
)
