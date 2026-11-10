# schema_io.py - Load/save project schema (project.json or project.ini) for "Load root according to schema".

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from dampf.indexer import DEFAULT_ALLOWED_SUFFIXES

# Keys that must be lists in JSON (stored as list, converted to set when building indexer config)
LIST_KEYS = ("allowed_suffixes", "stopwords")
SET_KEYS = ("allowed_suffixes", "stopwords")

# Default schema keys and types for validation
DEFAULT_SCHEMA = {
    "root_dir": "",
    "output_dir": "",
    "allowed_suffixes": sorted(DEFAULT_ALLOWED_SUFFIXES),
    "folder_token_depth": 99,
    "recursive": True,
    "include_hidden": False,
    "db_path": "",
    "table_name": "data",
    "relative_filepath_column": "relpath",
    "key_is_categorical": {},
    "column_si_scale": {},
    "modality_map": None,
    "stopwords": None,
    "custom_token_map": {},
    "token_patterns": [],
}


def config_to_schema(config: Dict[str, Any]) -> Dict[str, Any]:
    """Convert indexer config (may have sets/tuples) to JSON-serializable schema."""
    out: Dict[str, Any] = {}
    for k, v in config.items():
        if k in ("allowed_suffixes", "stopwords") and isinstance(v, (set, frozenset)):
            out[k] = sorted(v)
        elif isinstance(v, (set, frozenset)):
            out[k] = sorted(v)
        elif isinstance(v, tuple):
            out[k] = list(v)
        else:
            out[k] = v
    return out


def schema_to_config(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Convert loaded schema (lists) to indexer config (sets/tuples where needed)."""
    from dampf.indexer import DEFAULT_ALLOWED_SUFFIXES, DEFAULT_STOPWORDS

    cfg: Dict[str, Any] = dict(schema)
    if "allowed_suffixes" in cfg and isinstance(cfg["allowed_suffixes"], list):
        cfg["allowed_suffixes"] = set(cfg["allowed_suffixes"]) or DEFAULT_ALLOWED_SUFFIXES
    if "stopwords" in cfg and isinstance(cfg["stopwords"], list):
        cfg["stopwords"] = set(cfg["stopwords"]) if cfg["stopwords"] else DEFAULT_STOPWORDS
    return cfg


def load_project_json(path: str | Path) -> Optional[Dict[str, Any]]:
    """Load project schema from project.json. Returns config dict for run_indexer or None."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return schema_to_config(data)
    except (json.JSONDecodeError, OSError):
        return None


def save_project_json(path: str | Path, config: Dict[str, Any]) -> None:
    """Save project schema to project.json."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config_to_schema(config)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_project_ini(path: str | Path) -> Optional[Dict[str, Any]]:
    """Load project schema from project.ini. Returns config dict for run_indexer or None."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        config: Dict[str, Any] = {}
        with path.open("r", encoding="utf-8") as f:
            section = ""
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip().lower()
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip().lower(), v.strip()
                    if section:
                        key = f"{section}.{k}"
                    else:
                        key = k
                    if key in ("indexer.allowed_suffixes", "allowed_suffixes"):
                        config["allowed_suffixes"] = [x.strip() for x in v.split(",") if x.strip()]
                    elif key in ("indexer.folder_token_depth", "folder_token_depth"):
                        try:
                            config["folder_token_depth"] = int(v)
                        except ValueError:
                            pass
                    elif key in ("paths.root_dir", "root_dir"):
                        config["root_dir"] = v
                    elif key in ("paths.output_dir", "output_dir"):
                        config["output_dir"] = v
                    elif key in ("paths.db_path", "db_path"):
                        config["db_path"] = v
                    elif key in ("indexer.recursive", "recursive"):
                        config["recursive"] = v.lower() in ("1", "true", "yes")
                    elif key in ("indexer.include_hidden", "include_hidden"):
                        config["include_hidden"] = v.lower() in ("1", "true", "yes")
        return schema_to_config(config) if config else None
    except OSError:
        return None


def save_project_ini(path: str | Path, config: Dict[str, Any]) -> None:
    """Save project schema to project.ini."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config_to_schema(config)
    lines = ["[paths]", f"root_dir = {data.get('root_dir', '')}", f"output_dir = {data.get('output_dir', '')}", f"db_path = {data.get('db_path', '')}", "", "[indexer]"]
    for k in ("allowed_suffixes", "folder_token_depth", "recursive", "include_hidden"):
        v = data.get(k)
        if v is None:
            continue
        if k == "allowed_suffixes":
            lines.append("allowed_suffixes = " + ", ".join(v))
        elif k == "folder_token_depth":
            lines.append(f"folder_token_depth = {v}")
        elif k in ("recursive", "include_hidden"):
            lines.append(f"{k} = {str(v).lower()}")
    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
