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


DEFAULT_INI = """
[dampf]
; Window: max width 800px, fit Full HD (1080px) vertically
width = 780
height = 980
max_width = 800
max_height = 1080

[paths]
root_dir =
output_dir =
db_path =
""".strip()


def load_settings() -> dict:
    """Load dampf.ini. Returns dict with width, height, max_width, max_height, light_mode, paths."""
    p = _get_settings_path()
    out = {
        "width": 780,
        "height": 980,
        "max_width": 800,
        "max_height": 1080,
        "light_mode": True,
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
    light_mode: bool = True,
) -> None:
    """Save window size, paths, and theme to dampf.ini."""
    p = _get_settings_path()
    cfg = configparser.ConfigParser()
    cfg["dampf"] = {
        "width": str(width),
        "height": str(height),
        "max_width": "800",
        "max_height": "1080",
        "light_mode": "true" if light_mode else "false",
    }
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
