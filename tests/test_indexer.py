# test_indexer.py - Unit tests for indexer module

import pytest
from pathlib import Path

from indexer import (
    tokenize_string,
    parse_tokens,
    parse_number,
    run_indexer,
    suggest_nomenclature,
    split_transitions,
    detect_dominant_suffix,
)


def test_tokenize_string_basic():
    assert tokenize_string("500us_exp") == ["500us", "exp"]
    assert "run1" in tokenize_string("run1_rep2")
    assert "rep2" in tokenize_string("run1_rep2")


def test_tokenize_string_number_unit():
    assert "500us" in tokenize_string("500us")
    assert "10mm" in tokenize_string("10mm")
    assert "4p2kv" in tokenize_string("4p2kv")
    assert "4p2kv" in tokenize_string("4.2kv")  # decimal dot normalized to p


def test_parse_number():
    assert parse_number("500") == 500.0
    assert parse_number("4p2") == 4.2
    assert parse_number("1e-6") == 1e-6
    assert parse_number("") is None
    assert parse_number("abc") is None


def test_parse_tokens_exposure():
    r = parse_tokens(["500us"])
    assert r.data.get("exposure") == {"val": 500.0, "unit": "us"}
    assert any("exposure" in t for t in r.trace)


def test_parse_tokens_voltage_decimal_dot():
    """4.2kv (decimal dot) is normalized to 4p2kv and parsed as voltage."""
    r = parse_tokens(["4.2kv"])
    assert r.data.get("voltage") == {"val": 4.2, "unit": "kv"}


def test_parse_tokens_date_iso():
    r = parse_tokens(["2024-03-15"])
    assert r.data.get("date") == "2024-03-15"


def test_parse_tokens_date_eu():
    r = parse_tokens(["15.03.2024"])
    assert r.data.get("date") == "2024-03-15"


def test_parse_tokens_run_rep():
    r = parse_tokens(["run1", "rep2"])
    assert r.data.get("run") == 1
    assert r.data.get("rep") == 2


def test_parse_tokens_length():
    r = parse_tokens(["10mm"])
    assert "lengths" in r.data
    assert r.data["lengths"][0]["val"] == 10.0
    assert r.data["lengths"][0]["unit"] == "mm"


def test_lengths_export_numeric():
    """lengths: Spalte nur Numeric, Unit in Metadaten."""
    from key_lut import get_export_value_and_metadata
    v = [{"val": 1.0, "unit": "mm", "SI_m": 0.001}]
    val, unit, raw = get_export_value_and_metadata(v, "lengths", None)
    assert val == 1.0
    assert raw == "mm"
    val_si, unit_si, _ = get_export_value_and_metadata(v, "lengths", {"lengths": 0})
    assert val_si == 0.001
    assert unit_si == "m"


def test_suggest_nomenclature_empty():
    out = suggest_nomenclature([])
    assert out["detected_fields"] == []
    assert len(out["suggested_group_keys"]) > 0


def test_suggest_nomenclature_from_rows():
    rows = [
        {"path": "/a/b", "exposure": {"val": 500, "unit": "us"}, "run": 1},
        {"path": "/a/c", "exposure": {"val": 100, "unit": "us"}, "run": 2},
    ]
    out = suggest_nomenclature(rows)
    assert "exposure" in out["detected_fields"]
    assert "run" in out["detected_fields"]


def test_split_transitions():
    assert split_transitions("M25") == ["M", "25"]
    assert split_transitions("500us") == ["500", "us"]


def test_tokenize_and_parse_decimal_dot_in_path():
    """Decimal dot in path (4.2kv) is normalized and parsed correctly."""
    from indexer import tokenize_path, parse_tokens
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "run1_4.2kv_10us_001.png").touch()
        path = root / "run1_4.2kv_10us_001.png"
        tokens = tokenize_path(path, root, folder_depth=0)
        r = parse_tokens(tokens)
        assert r.data.get("voltage") == {"val": 4.2, "unit": "kv"}
        assert r.data.get("exposure") == {"val": 10.0, "unit": "us"}
        assert r.data.get("frame") == 1


def test_detect_dominant_suffix():
    """Majority vote: most frequent extension wins."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for i in range(5):
            (root / f"run{i}.tif").touch()
        (root / "one.csv").touch()
        (root / "two.csv").touch()
        assert detect_dominant_suffix(root) == ".tif"


def test_run_indexer_sequential():
    """run_indexer with few files uses sequential path."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "2024-01-15_run1_rep2_500us.tif").touch()
        (root / "2024-01-15_run1_rep3_100us.tif").touch()
        rows, groups = run_indexer(root, root / "_index")
        assert len(rows) == 2
        assert all("exposure" in r for r in rows)
        assert all(r.get("run") == 1 for r in rows)


def test_run_indexer_parallel():
    """run_indexer with parallel_threshold=2 uses multicore path."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for i in range(5):
            (root / f"2024-01-15_run1_rep{i}_500us.tif").touch()
        config = {"parallel_threshold": 2, "parallel_max_workers": 2}
        rows, groups = run_indexer(root, root / "_index", config)
        assert len(rows) == 5
        assert all(r.get("run") == 1 for r in rows)


def test_run_indexer_log_callback():
    """run_indexer calls log_callback with timing messages."""
    import tempfile
    logs: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "2024-01-15_run1_500us.tif").touch()
        config = {"log_callback": logs.append}
        run_indexer(root, root / "_index", config)
    assert any("iter_files" in L for L in logs)
    assert any("total" in L for L in logs)
