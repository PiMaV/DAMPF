# tests/test_db_writer.py - default_db_path_for_root

from pathlib import Path

from dampf.db_writer import default_db_path_for_root


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
