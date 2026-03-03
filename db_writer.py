# db_writer.py - Write index to SQLite gemaess BLITZ_Receiver_Contract (WOLKE/DAMPF).
# Eine Datentabelle: id, relative_filepath_column (Pfad relativ zum DB-Verzeichnis), plus alle indexierten Felder.

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from key_lut import get_export_value_and_metadata, is_quantitative_val

# Keys die nicht als Daten-Spalten in die Contract-Tabelle kommen (nur Metadaten/Interna)
ROW_META_KEYS = {
    "path", "relpath", "ext", "stem", "tokens", "trace", "recognized",
    "total_tokens", "confidence",
    "_duplicate_keys", "_folder_tokens", "_file_tokens", "_folder_token_to_key", "_file_token_to_key",
}


def _serialize_value(
    v: Any,
    key: str | None = None,
    column_si_scale: Dict[str, int] | None = None,
) -> tuple[Any, str, str]:
    """
    Fuer data-Tabelle. Returns (val, unit, raw_unit).
    Bei column_si_scale.get(key)==0: Konvertierung zu SI.
    """
    if v is None:
        return (None, "", "")
    if is_quantitative_val(v) and key:
        return get_export_value_and_metadata(v, key, column_si_scale)
    if is_quantitative_val(v):
        return (v.get("val"), v.get("unit", ""), v.get("unit", ""))
    if isinstance(v, (list, dict)):
        return (json.dumps(v, ensure_ascii=False), "", "")
    return (v, "", "")


def _relpath_from_db(file_path: str | Path, db_path: Path) -> str:
    """
    Pfad der Datei relativ zum Verzeichnis der DB-Datei (= Root).
    Nur relative Berechnung gegen dieses Root, ohne Symlink-Aufloesung (kein resolve()).
    """
    db_dir = Path(db_path).absolute().parent
    try:
        rel = Path(file_path).absolute().relative_to(db_dir)
        return str(rel).replace("\\", "/")
    except ValueError:
        return str(Path(file_path).name)


def write_index_to_sqlite(
    rows: List[Dict[str, Any]],
    groups: Dict[str, List[str]],
    db_path: str | Path,
    *,
    schema_config: Optional[Dict[str, Any]] = None,
    used_keys: Optional[List[str]] = None,
) -> None:
    """
    Erzeugt SQLite-DB gemaess BLITZ_Receiver_Contract:
    - Eine Tabelle (Name aus schema_config["table_name"], Default "data") mit:
      id INTEGER PRIMARY KEY,
      <relative_filepath_column> TEXT NOT NULL (Pfad relativ zum DB-Verzeichnis),
      plus alle indexierten Felder als Spalten (REAL/INTEGER/TEXT).
    - Optionale Tabelle "config" fuer DAMPF-Schema (load from DB).
    groups wird nicht mehr in die DB geschrieben (Contract verlangt nur die eine Datentabelle).
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = schema_config or {}
    table_name = _quote_table(str(cfg.get("table_name") or "data"))
    relpath_col = _quote_id(str(cfg.get("relative_filepath_column") or "relpath"))

    # Daten-Keys: bei used_keys nur diese; sonst alle (ohne Meta)
    data_keys_set: set[str] = set()
    for r in rows:
        for k in r:
            if k not in ROW_META_KEYS:
                data_keys_set.add(k)
    data_keys = [k for k in sorted(used_keys) if k in data_keys_set] if used_keys else sorted(data_keys_set)
    # Spaltennamen fuer SQL: nur alphanumerisch/Unterstrich (vermeidet "unrecognized token" z.B. "{")
    col_names: List[str] = []
    seen: set[str] = set()
    for k in data_keys:
        base = _quote_id(k)
        name = base
        n = 0
        while name in seen:
            n += 1
            name = f"{base}_{n}"
        seen.add(name)
        col_names.append(name)

    column_si_scale: Dict[str, int] = cfg.get("column_si_scale") or {}

    from key_lut import get_export_value_and_metadata
    column_metadata: List[tuple] = []
    for i, k in enumerate(data_keys):
        unit_val = raw_unit_val = ""
        value_type = "scalar"
        for r in rows:
            v = r.get(k)
            if v is None:
                continue
            if isinstance(v, list) and v and isinstance(v[0], dict):
                value_type = "list"
                break
            if is_quantitative_val(v):
                _, unit_val, raw_unit_val = get_export_value_and_metadata(v, k, column_si_scale)
                break
        column_metadata.append((col_names[i], unit_val, raw_unit_val, value_type))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS " + table_name)
        conn.execute("DROP TABLE IF EXISTS config")
        conn.execute("DROP TABLE IF EXISTS column_metadata")

        # Spalten: id, relpath_col, dann col_names; Typen: int->INTEGER, float->REAL, sonst TEXT
        col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT", relpath_col + " TEXT NOT NULL"]
        for i, cname in enumerate(col_names):
            col_defs.append(cname + " " + _sql_type_for_key(rows, data_keys[i], use_extracted_val=True))
        create_sql = "CREATE TABLE " + table_name + " (\n    " + ",\n    ".join(col_defs) + "\n)"
        if "{" in create_sql or "}" in create_sql:
            raise ValueError("Invalid character in SQL (schema_config keys may contain braces)")
        conn.execute(create_sql)

        conn.execute(
            "CREATE TABLE column_metadata (column_name TEXT PRIMARY KEY, unit TEXT, raw_unit TEXT, value_type TEXT)"
        )
        for m in column_metadata:
            col_name, u, raw_u = m[0], m[1], m[2]
            vt = m[3] if len(m) > 3 else "scalar"
            conn.execute(
                "INSERT INTO column_metadata (column_name, unit, raw_unit, value_type) VALUES (?, ?, ?, ?)",
                (col_name, u, raw_u, vt),
            )

        placeholders = ", ".join(["?"] * (1 + len(data_keys)))
        insert_sql = "INSERT INTO " + table_name + " (" + relpath_col + ", " + ", ".join(col_names) + ") VALUES (" + placeholders + ")"
        if "{" in insert_sql or "}" in insert_sql:
            raise ValueError("Invalid character in SQL")
        for r in rows:
            rel_path_str = _relpath_from_db(r.get("path", ""), db_path)
            vals: List[Any] = [rel_path_str]
            for k in data_keys:
                v, _u, _ru = _serialize_value(r.get(k), key=k, column_si_scale=column_si_scale)
                vals.append(v)
            conn.execute(insert_sql, vals)

        if schema_config is not None:
            conn.execute('CREATE TABLE config ( "key" TEXT PRIMARY KEY, "value" TEXT )')
            schema_json = json.dumps(schema_config, ensure_ascii=False)
            conn.execute('INSERT INTO config ("key", "value") VALUES (?, ?)', ("schema", schema_json))

        conn.commit()
    finally:
        conn.close()


def _safe_identifier(name: str, default: str) -> str:
    """Nur alphanumerisch und Unterstrich; sonst default. Verhindert Token-Fehler (z.B. '{' in Namen)."""
    if not name or not isinstance(name, str):
        return default
    s = "".join(c for c in name if c.isalnum() or c == "_")
    return s if s else default


def _quote_table(name: str) -> str:
    """Tabellenname: nur alphanumerisch/Unterstrich."""
    return _safe_identifier(str(name), "data")


def _quote_id(name: str) -> str:
    """Spaltenname fuer SQL: nur alphanumerisch/Unterstrich, dann unquoted (kein '{' etc.)."""
    return _safe_identifier(str(name), "col")


def _sql_type_for_key(rows: List[Dict[str, Any]], key: str, use_extracted_val: bool = False) -> str:
    """INTEGER, REAL oder TEXT je nach Vorkommen in rows."""
    has_int = has_float = has_other = False
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        if use_extracted_val and is_quantitative_val(v):
            v = v.get("val")
        if isinstance(v, (list, dict)):
            has_other = True
        elif isinstance(v, bool):
            has_int = True
        elif isinstance(v, int):
            has_int = True
        elif isinstance(v, float):
            has_float = True
        else:
            has_other = True
    if has_other:
        return "TEXT"
    if has_float:
        return "REAL"
    if has_int:
        return "INTEGER"
    return "TEXT"


def load_schema_from_db(db_path: str | Path) -> Optional[Dict[str, Any]]:
    """Load schema/project config from DB config table. Returns None if not present."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("SELECT value FROM config WHERE key = ?", ("schema",))
        row = cur.fetchone()
        if row:
            return json.loads(row[0])
        return None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
