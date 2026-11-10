# test_indexer.py - Unit tests for indexer module

import pytest
from pathlib import Path

from dampf.indexer import (
    tokenize_string,
    parse_tokens,
    parse_number,
    run_indexer,
    suggest_nomenclature,
    split_transitions,
    detect_dominant_suffix,
    apply_majority_frame_logic,
    tokenize_path_parts,
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
    """lengths: column numeric only, unit in metadata."""
    from dampf.key_lut import get_export_value_and_metadata
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
    from dampf.indexer import tokenize_path, parse_tokens
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


def test_img_suffix_is_indexed():
    """Camera .img files are crawled by default (path metadata only)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "run1_500us_001.img").touch()
        rows, _ = run_indexer(root, root / "_index")
        assert len(rows) == 1
        assert rows[0].get("ext") == ".img"
        assert rows[0].get("run") == 1
        assert rows[0].get("exposure") == {"val": 500.0, "unit": "us"}


def test_confidence_uses_filename_tokens_only():
    """Deep Project/…/cache folders must not dilute confidence below the default outlier threshold."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        rel = Path("Project20250317_141710") / "data" / "20250317_141746" / "cache" / "frame_004_0000.img"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).touch()
        rows, _ = run_indexer(root, root / "_index")
        assert len(rows) == 1
        assert rows[0]["total_tokens"] == 3  # frame, 004, 0000 — not folder tokens
        assert rows[0]["recognized"] == 3
        assert rows[0]["confidence"] >= 0.3
        assert rows[0].get("channel") == 4
        assert rows[0].get("frame") == 0
        assert rows[0].get("date") == "2025-03-17"
        assert rows[0].get("time") == "14:17:10"
        # Folder clock must not steal frame from the filename pair
        assert rows[0].get("_folder_token_to_key", {}).get("141710") == "time"


def test_frame_channel_pair_pattern():
    """frame_<channel>_<frame> in the filename maps both numbers."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "frame_001_0011.img").touch()
        rows, _ = run_indexer(root, root / "_index")
        assert rows[0].get("channel") == 1
        assert rows[0].get("frame") == 11


def test_hhmmss_time_not_frame_in_folder():
    """Six-digit clock after a compact date becomes time, not frame."""
    from dampf.indexer import parse_tokens, tokenize_string

    toks = tokenize_string("20250317_141746")
    pr = parse_tokens(toks)
    assert pr.data.get("date") == "2025-03-17"
    assert pr.data.get("time") == "14:17:46"
    assert "frame" not in pr.data


def test_last_filename_digits_stay_frame_even_if_hhmmss_shaped():
    """Trailing filename number remains frame (camera index), not wall-clock time."""
    from dampf.indexer import parse_tokens, tokenize_string

    toks = tokenize_string("shot_120000")
    pr = parse_tokens(toks, only_last_plain_digits_as_frame=True)
    assert pr.data.get("frame") == 120000
    assert "time" not in pr.data


def test_tokenize_splits_img_compact_datetime():
    """IMG20220601093439 → img + 14-digit stamp (not param img=<huge>)."""
    assert tokenize_string("IMG20220601093439") == ["img", "20220601093439"]
    assert tokenize_string("run1") == ["run1"]


def test_compact_yyyymmddhhmmss_sets_date_and_time():
    """Bare or camera-prefixed YYYYMMDDHHMMSS → date + time, never frame."""
    from dampf.indexer import parse_tokens, tokenize_string

    bare = parse_tokens(tokenize_string("20220601093439"), only_last_plain_digits_as_frame=True)
    assert bare.data.get("date") == "2022-06-01"
    assert bare.data.get("time") == "09:34:39"
    assert "frame" not in bare.data

    glued = parse_tokens(tokenize_string("IMG20220601093439"), only_last_plain_digits_as_frame=True)
    assert glued.data.get("date") == "2022-06-01"
    assert glued.data.get("time") == "09:34:39"
    assert "frame" not in glued.data


def test_img_compact_datetime_file_indexed():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "Training" / "Compressed").mkdir(parents=True)
        (root / "Training" / "Compressed" / "IMG20220601093439.jpg").touch()
        rows, _ = run_indexer(root, root / "_index")
        assert len(rows) == 1
        assert rows[0].get("date") == "2022-06-01"
        assert rows[0].get("time") == "09:34:39"
        assert "frame" not in rows[0] or rows[0].get("frame") is None


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


def test_parse_tokens_user_patterns():
    """User token_patterns (regex -> key) are applied after built-in. Tokens are lowercased in pipeline."""
    patterns = [
        {"key": "gain", "regex": r"^gain(?P<n>\d+)$", "extract": "int", "capture_group": "n"},
    ]
    r = parse_tokens(["gain150"], token_patterns=patterns)
    assert r.data.get("gain") == 150
    assert r.token_to_key.get("gain150") == "gain"


def test_parse_tokens_custom_token_map():
    """custom_token_map exact token -> key applied when no built-in match."""
    r = parse_tokens(["SyncK"], custom_token_map={"SyncK": "sync_id"})
    assert r.data.get("sync_id") == "SyncK"
    assert r.token_to_key.get("SyncK") == "sync_id"


def test_parse_tokens_short_date_via_token_pattern_yy():
    """Short date 22_01_26 via token_pattern with date_short_YY -> 2022-01-26."""
    patterns = [
        {"key": "date", "regex": r"^(?P<a>\d{2})[-_\.](?P<b>\d{2})[-_\.](?P<c>\d{2})$", "extract": "date_short_YY"},
    ]
    r = parse_tokens(["22_01_26"], token_patterns=patterns)
    assert r.data.get("date") == "2022-01-26"


def test_parse_tokens_short_date_via_token_pattern_dm():
    """Short date 22_01_26 via token_pattern with date_short_DM -> 2026-01-22 (22=day, 26=year)."""
    patterns = [
        {"key": "date", "regex": r"^(?P<a>\d{2})[-_\.](?P<b>\d{2})[-_\.](?P<c>\d{2})$", "extract": "date_short_DM"},
    ]
    r = parse_tokens(["22_01_26"], token_patterns=patterns)
    assert r.data.get("date") == "2026-01-22"


def test_parse_tokens_m10_frame():
    """M10_0: M10 = measurement (m), trailing 0 = frame. Only last plain digits as frame."""
    r = parse_tokens(["m10", "0"], only_last_plain_digits_as_frame=True)
    assert r.data.get("m") == 10
    assert r.data.get("frame") == 0


def test_parse_tokens_m14_14():
    """M14_14: M14 = m, last 14 = frame."""
    r = parse_tokens(["m14", "14"], only_last_plain_digits_as_frame=True)
    assert r.data.get("m") == 14
    assert r.data.get("frame") == 14


def test_parse_tokens_m_10_0_split():
    """When M and 10 and 0 are separate tokens (M10 split), m=10 from '10' after 'm', frame=0 from last."""
    r = parse_tokens(["m", "10", "0"], only_last_plain_digits_as_frame=True)
    assert r.data.get("m") == 10
    assert r.data.get("frame") == 0


def test_m10_0_and_m14_14_regression():
    """Regression test for M10_13mm\\M10_0.png and M14_9mm\\M14_14.png: m and frame must be correct."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "M10_13mm").mkdir()
        (root / "M10_13mm" / "M10_0.png").touch()
        (root / "M14_9mm").mkdir()
        (root / "M14_9mm" / "M14_14.png").touch()
        rows, _ = run_indexer(root, root / "_out", config={"parallel_threshold": 1000})
        by_rel = {r["relpath"].replace("\\", "/"): r for r in rows}
        r10 = by_rel.get("M10_13mm/M10_0.png")
        r14 = by_rel.get("M14_9mm/M14_14.png")
        assert r10 is not None and r10.get("m") == 10 and r10.get("frame") == 0, f"M10_0: got m={r10.get('m') if r10 else None}, frame={r10.get('frame') if r10 else None}"
        assert r14 is not None and r14.get("m") == 14 and r14.get("frame") == 14, f"M14_14: got m={r14.get('m') if r14 else None}, frame={r14.get('frame') if r14 else None}"


def test_m10_0_with_stopword_m():
    """Single 'm' must not be filtered even if in stopwords (M 10_0 -> m,10,0 -> m=10, frame=0)."""
    tokens = tokenize_string("M 10_0", stopwords={"m"})
    assert "m" in tokens, "m must be kept for measurement; got tokens: %s" % tokens
    pr = parse_tokens(tokens, only_last_plain_digits_as_frame=True)
    assert pr.data.get("m") == 10 and pr.data.get("frame") == 0


def test_three_examples_m10_m20_m14_paths():
    """
    Directly the three examples: M10_13mm\\M10_0.png, M20_3mm\\M20_0.png, M14_9mm\\M14_14.png, plus M18_5mm\\M18_18.png.
    Expectation: M10/M20 = measurement (m), _0 = Frame; M14/M18 = measurement, last number = Frame (same number may appear twice).
    """
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        cases = [
            ("M10_13mm", "M10_0.png", 10, 0),
            ("M20_3mm", "M20_0.png", 20, 0),
            ("M14_9mm", "M14_14.png", 14, 14),
            ("M18_5mm", "M18_18.png", 18, 18),
        ]
        for folder, filename, expected_m, expected_frame in cases:
            (root / folder).mkdir(parents=True, exist_ok=True)
            (root / folder / filename).touch()
            path = root / folder / filename
            folder_tokens, file_tokens, _ = tokenize_path_parts(path, root, 99)
            pr = parse_tokens(file_tokens, only_last_plain_digits_as_frame=True)
            assert pr.data.get("m") == expected_m, f"{folder}/{filename}: expected m={expected_m}, got {pr.data.get('m')}"
            assert pr.data.get("frame") == expected_frame, f"{folder}/{filename}: expected frame={expected_frame}, got {pr.data.get('frame')}"


def test_three_examples_via_run_indexer():
    """Like test_three_examples_*, but with run_indexer incl. apply_majority_frame_logic – final row state must have m and frame correct."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        cases = [
            ("M10_13mm", "M10_0.png", 10, 0),
            ("M20_3mm", "M20_0.png", 20, 0),
            ("M14_9mm", "M14_14.png", 14, 14),
            ("M18_5mm", "M18_18.png", 18, 18),
        ]
        for folder, filename, expected_m, expected_frame in cases:
            (root / folder).mkdir(parents=True, exist_ok=True)
            (root / folder / filename).touch()
        rows, _ = run_indexer(root, root / "_out", config={"parallel_threshold": 1000})
        by_path = {r["relpath"].replace("\\", "/"): r for r in rows}
        for folder, filename, expected_m, expected_frame in cases:
            rel = f"{folder}/{filename}"
            r = by_path.get(rel)
            assert r is not None, f"Row missing for {rel}"
            assert r.get("m") == expected_m, f"{rel}: expected m={expected_m}, got {r.get('m')}"
            assert r.get("frame") == expected_frame, f"{rel}: expected frame={expected_frame}, got {r.get('frame')}"


def test_apply_majority_frame_logic():
    """Minority rows with last numeric token as 'seq' get reassigned to 'frame' when majority is 'frame'."""
    rows = [
        {"_file_tokens": ["a", "100"], "_file_token_to_key": {"a": "run", "100": "frame"}, "run": 1, "frame": 100},
        {"_file_tokens": ["a", "101"], "_file_token_to_key": {"a": "run", "101": "frame"}, "run": 1, "frame": 101},
        {"_file_tokens": ["a", "18"], "_file_token_to_key": {"a": "run", "18": "seq"}, "run": 1, "seq": 18},
    ]
    apply_majority_frame_logic(rows)
    assert rows[0].get("frame") == 100 and "seq" not in rows[0]
    assert rows[1].get("frame") == 101
    assert rows[2].get("frame") == 18 and rows[2].get("seq") is None
    assert rows[2]["_file_token_to_key"]["18"] == "frame"
