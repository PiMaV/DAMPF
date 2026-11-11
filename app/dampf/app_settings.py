# app_settings.py - GUI settings via INI, placed next to exe for portable deployment.

from __future__ import annotations

import configparser
import io
import os
import re
import sys
from pathlib import Path

from dampf.naming_rules import PREDEFINED_MODALITY, PREDEFINED_PROCESSING, PREDEFINED_UNITS

# Windows drive path, e.g. C:\DATEN\... or C:/DATEN/...
_WIN_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


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


def stored_path_for_this_os(path: str) -> str:
    """Keep a persisted path only when this OS can use it as a real path.

    On Linux a saved Windows path is one filename (backslashes are not
    separators). Returning it unchanged makes mkdir create that name in cwd.
    """
    text = (path or "").strip().strip('"')
    if not text:
        return ""
    if os.name != "nt" and ("\\" in text or _WIN_DRIVE.match(text)):
        return ""
    return text


def _parser() -> configparser.ConfigParser:
    return configparser.ConfigParser(interpolation=None)


def _read_parser() -> configparser.ConfigParser:
    cfg = _parser()
    p = _get_settings_path()
    if p.is_file():
        cfg.read(p, encoding="utf-8")
    return cfg


def _write_parser(cfg: configparser.ConfigParser) -> None:
    p = _get_settings_path()
    body = []
    # configparser writes sections; keep one line so the file explains the two blocks.
    note = (
        "; *.predefined is restored from the program on save and shows the shipped lists.\n"
        "; *.user is the block the crawl uses. Delete a line there to drop that rule.\n"
    )
    buf = io.StringIO()
    cfg.write(buf)
    body.append(note)
    body.append(buf.getvalue())
    try:
        p.write_text("".join(body), encoding="utf-8")
    except OSError:
        pass


def _section_dict(cfg: configparser.ConfigParser, name: str) -> dict[str, str] | None:
    if not cfg.has_section(name):
        return None
    return {k.strip().lower(): (v or "").strip() for k, v in cfg[name].items()}


def _put_map(cfg: configparser.ConfigParser, name: str, rows: dict[str, str]) -> None:
    if cfg.has_section(name):
        cfg.remove_section(name)
    cfg[name] = {str(k).strip().lower(): str(v).strip() for k, v in rows.items() if str(k).strip()}


def _put_words(cfg: configparser.ConfigParser, name: str, words: list[str] | tuple[str, ...]) -> None:
    rows = {w.strip().lower(): w.strip().lower() for w in words if w and w.strip()}
    _put_map(cfg, name, rows)


def _seed_user_sections(cfg: configparser.ConfigParser) -> bool:
    """Write predefined blocks. Seed a missing user block from them. Return True if a user block was created."""
    seeded = False
    _put_map(cfg, "units.predefined", PREDEFINED_UNITS)
    if _section_dict(cfg, "units.user") is None:
        _put_map(cfg, "units.user", PREDEFINED_UNITS)
        seeded = True
    _put_map(cfg, "modality.predefined", PREDEFINED_MODALITY)
    if _section_dict(cfg, "modality.user") is None:
        _put_map(cfg, "modality.user", PREDEFINED_MODALITY)
        seeded = True
    _put_words(cfg, "processing.predefined", PREDEFINED_PROCESSING)
    if _section_dict(cfg, "processing.user") is None:
        _put_words(cfg, "processing.user", PREDEFINED_PROCESSING)
        seeded = True
    return seeded


def load_naming_rules() -> dict:
    """Active rules: the *.user sections. A missing section is the shipped list (not yet saved)."""
    cfg = _read_parser()
    units = _section_dict(cfg, "units.user")
    modality = _section_dict(cfg, "modality.user")
    processing = _section_dict(cfg, "processing.user")
    return {
        "units": dict(PREDEFINED_UNITS) if units is None else units,
        "modality": dict(PREDEFINED_MODALITY) if modality is None else modality,
        "processing": list(PREDEFINED_PROCESSING) if processing is None else list(processing.keys()),
    }


def save_naming_rules(units: dict[str, str], modality: dict[str, str], processing: list[str]) -> None:
    """Write user blocks and refresh the predefined blocks. Other sections stay."""
    cfg = _read_parser()
    _put_map(cfg, "units.predefined", PREDEFINED_UNITS)
    _put_map(cfg, "units.user", units)
    _put_map(cfg, "modality.predefined", PREDEFINED_MODALITY)
    _put_map(cfg, "modality.user", modality)
    _put_words(cfg, "processing.predefined", PREDEFINED_PROCESSING)
    _put_words(cfg, "processing.user", processing)
    _write_parser(cfg)


def ensure_naming_rules() -> None:
    """Create dampf.ini rule sections when a user block is not there yet."""
    cfg = _read_parser()
    if _seed_user_sections(cfg):
        _write_parser(cfg)
    elif not cfg.has_section("units.predefined"):
        _seed_user_sections(cfg)
        _write_parser(cfg)


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
                    out[k] = stored_path_for_this_os(cfg["paths"][k])
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
    """Save window size, paths, theme, splitter sizes, and outlier threshold to dampf.ini.

    Naming rule sections already in the file are kept. Missing user blocks are
    seeded from the shipped lists. Predefined blocks are rewritten from the program.
    """
    cfg = _read_parser()
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
        "root_dir": stored_path_for_this_os(root_dir),
        "output_dir": stored_path_for_this_os(output_dir),
        "db_path": stored_path_for_this_os(db_path),
    }
    _seed_user_sections(cfg)
    _write_parser(cfg)
