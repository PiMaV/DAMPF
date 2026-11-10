# app_settings.py - GUI settings via INI, placed next to exe for portable deployment.

from __future__ import annotations

import configparser
import sys
from pathlib import Path


def _get_settings_path() -> Path:
    """Return path to dampf.ini - next to exe when frozen, else cwd."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "dampf.ini"
    return Path.cwd() / "dampf.ini"


# Portable defaults — keep in sync with config/dampf.ini (no machine paths, no OS-specific dirs).
DEFAULT_INI = """
[dampf]
; Window: target 800x1000 for laptop/Full HD with taskbar
width = 800
height = 1000
max_width = 800
max_height = 1000
; Outlier panel: flag rows with confidence below this (0–1)
confidence_threshold = 0.3

[paths]
; Leave empty in the shipped template. Paths are machine-local and filled by the GUI.
root_dir =
output_dir =
db_path =
""".strip()


def load_settings() -> dict:
    """Load dampf.ini. Returns dict with width, height, max_width, max_height, light_mode, paths."""
    p = _get_settings_path()
    out = {
        "width": 800,
        "height": 1000,
        "max_width": 800,
        "max_height": 1000,
        "light_mode": False,
        "splitter_sizes": "",
        "main_splitter_sizes": "",
        "outer_splitter_sizes": "",
        "confidence_threshold": 0.3,
        "root_dir": "",
        "output_dir": "",
        "db_path": "",
    }
    if not p.is_file():
        return out
    cfg = configparser.ConfigParser()
    try:
        cfg.read(p, encoding="utf-8")
        if cfg.has_section("dampf"):
            s = cfg["dampf"]
            for k in ("width", "height", "max_width", "max_height"):
                if k in s:
                    try:
                        out[k] = int(s[k])
                    except ValueError:
                        pass
            if "light_mode" in s:
                out["light_mode"] = s["light_mode"].lower() in ("1", "true", "yes")
            if "splitter_sizes" in s:
                out["splitter_sizes"] = s["splitter_sizes"].strip()
            if "main_splitter_sizes" in s:
                out["main_splitter_sizes"] = s["main_splitter_sizes"].strip()
            if "outer_splitter_sizes" in s:
                out["outer_splitter_sizes"] = s["outer_splitter_sizes"].strip()
            if "confidence_threshold" in s:
                try:
                    thr = float(s["confidence_threshold"])
                    if 0.0 <= thr <= 1.0:
                        out["confidence_threshold"] = thr
                except ValueError:
                    pass
        if cfg.has_section("paths"):
            for k in ("root_dir", "output_dir", "db_path"):
                if k in cfg["paths"]:
                    out[k] = cfg["paths"][k].strip()
    except (configparser.Error, OSError):
        pass
    return out


def save_settings(
    width: int,
    height: int,
    root_dir: str = "",
    output_dir: str = "",
    db_path: str = "",
    light_mode: bool = False,
    splitter_sizes: str = "",
    main_splitter_sizes: str = "",
    outer_splitter_sizes: str = "",
    confidence_threshold: float = 0.3,
) -> None:
    """Save window size, paths, theme, splitter sizes, and outlier threshold to dampf.ini."""
    p = _get_settings_path()
    cfg = configparser.ConfigParser()
    thr = max(0.0, min(1.0, float(confidence_threshold)))
    dampf = {
        "width": str(width),
        "height": str(height),
        "max_width": "800",
        "max_height": "1000",
        "light_mode": "true" if light_mode else "false",
        "confidence_threshold": f"{thr:.2f}",
    }
    if splitter_sizes:
        dampf["splitter_sizes"] = splitter_sizes
    if main_splitter_sizes:
        dampf["main_splitter_sizes"] = main_splitter_sizes
    if outer_splitter_sizes:
        dampf["outer_splitter_sizes"] = outer_splitter_sizes
    cfg["dampf"] = dampf
    cfg["paths"] = {
        "root_dir": root_dir or "",
        "output_dir": output_dir or "",
        "db_path": db_path or "",
    }
    try:
        with p.open("w", encoding="utf-8") as f:
            cfg.write(f)
    except OSError:
        pass
