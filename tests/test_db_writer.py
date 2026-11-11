# tests/test_db_writer.py - default_db_path_for_root and categorical TEXT columns

import sqlite3
from pathlib import Path

from dampf.db_writer import default_db_path_for_root, write_index_to_sqlite


def test_default_db_uses_folder_name(tmp_path: Path) -> None:
    root = tmp_path / "MyDataset"
    root.mkdir()
    assert default_db_path_for_root(root) == root / "MyDataset.db"


def test_default_db_reserved_com1(tmp_path: Path) -> None:
    root = tmp_path / "COM1"
    root.mkdir()
    assert default_db_path_for_root(root).name == "COM1_dataset.db"


def test_default_db_folder_already_db_suffix(tmp_path: Path) -> None:
    root = tmp_path / "archive.db"
    root.mkdir()
    assert default_db_path_for_root(root) == root / "archive.db"


def test_categorical_key_forced_text(tmp_path: Path) -> None:
    """Cat keys become TEXT so WOLKE treats them as filters; others keep numeric affinity."""
    root = tmp_path / "ds"
    root.mkdir()
    f1 = root / "a.png"
    f2 = root / "b.png"
    f1.write_bytes(b"x")
    f2.write_bytes(b"x")
    rows = [
        {"path": str(f1), "relpath": "a.png", "run": 1, "frame": 10},
        {"path": str(f2), "relpath": "b.png", "run": 2, "frame": 20},
    ]
    db_path = root / "ds.db"
    write_index_to_sqlite(rows, {}, db_path, categorical_keys=["run"])

    conn = sqlite3.connect(str(db_path))
    try:
        run_type = conn.execute(
            "SELECT typeof(run) FROM data WHERE relpath = ?", ("a.png",)
        ).fetchone()[0]
        frame_type = conn.execute(
            "SELECT typeof(frame) FROM data WHERE relpath = ?", ("a.png",)
        ).fetchone()[0]
        run_val = conn.execute(
            "SELECT run FROM data WHERE relpath = ?", ("a.png",)
        ).fetchone()[0]
        frame_val = conn.execute(
            "SELECT frame FROM data WHERE relpath = ?", ("a.png",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert run_type == "text"
    assert isinstance(run_val, str)
    assert run_val == "1"
    assert frame_type == "integer"
    assert isinstance(frame_val, int)
    assert frame_val == 10


def test_hyphen_in_column_name_becomes_underscore(tmp_path: Path) -> None:
    """A bound name uses '-' in the file. SQL cannot, so the column uses '_'."""
    root = tmp_path / "ds"
    root.mkdir()
    f1 = root / "a.png"
    f1.write_bytes(b"x")
    rows = [{"path": str(f1), "relpath": "a.png", "target-material": "glass"}]
    db_path = root / "ds.db"
    write_index_to_sqlite(rows, {}, db_path, categorical_keys=["target-material"])

    conn = sqlite3.connect(str(db_path))
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(data)").fetchall()]
        val = conn.execute("SELECT target_material FROM data").fetchone()[0]
    finally:
        conn.close()

    assert "target_material" in cols
    assert "target-material" not in cols
    assert val == "glass"
