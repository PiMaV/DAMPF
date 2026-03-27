# test_outlier_detection.py - Unit tests for outlier_detection module

import pytest

from dampf.outlier_detection import detect_schema_outliers, detect_typo_candidates


def _row(relpath: str, confidence: float = 0.8, **kwargs) -> dict:
    r = {"relpath": relpath, "confidence": confidence}
    r.update(kwargs)
    return r


def test_detect_schema_outliers_empty():
    assert detect_schema_outliers([]) == []
    assert detect_schema_outliers([], detected_keys=["run"]) == []


def test_detect_schema_outliers_low_confidence():
    # 9 rows with high confidence, 1 with low -> that one is outlier
    rows = [_row(f"p{i}", 0.85 if i != 5 else 0.2) for i in range(10)]
    result = detect_schema_outliers(rows, detected_keys=[], confidence_threshold=0.3)
    assert len(result) == 1
    r, reason = result[0]
    assert r["relpath"] == "p5"
    assert "confidence" in reason and "0.20" in reason


def test_detect_schema_outliers_missing_majority_key():
    # Key "run" in 9/10 rows -> row without "run" is outlier
    rows = []
    for i in range(10):
        r = _row(f"p{i}", 0.8)
        if i != 3:
            r["run"] = 1
        rows.append(r)
    result = detect_schema_outliers(rows, detected_keys=["run"], key_coverage_pct=80.0)
    assert len(result) == 1
    r, reason = result[0]
    assert r["relpath"] == "p3"
    assert "missing keys" in reason and "run" in reason


def test_detect_schema_outliers_no_outliers():
    rows = [_row(f"p{i}", 0.9, run=1) for i in range(5)]
    result = detect_schema_outliers(rows, detected_keys=["run"], confidence_threshold=0.3)
    assert len(result) == 0


def test_detect_typo_candidates_empty():
    assert detect_typo_candidates([]) == []


def test_detect_typo_candidates_typo_in_folder_name():
    # 9 paths with folder "Measurement", 1 with "Measuremint" (typo) -> typo candidate
    # (MultFilI vs MultFiLI lower to same string so no candidate; use names that differ when lowercased)
    rows = [{"relpath": f"Measurement/file{i}.asc"} for i in range(9)]
    rows.append({"relpath": "Measuremint/file9.asc"})
    result = detect_typo_candidates(rows, max_edit_distance=2, min_freq_ratio=2.0)
    assert len(result) >= 1
    relpath, depth, segment, suggested, cnt_a, cnt_s = result[0]
    assert depth == 0
    assert (segment == "Measuremint" and suggested == "Measurement") or (
        segment == "Measurement" and suggested == "Measuremint"
    )
    assert (cnt_a, cnt_s) == (1, 9) or (cnt_a, cnt_s) == (9, 1)


def test_detect_typo_candidates_single_folder_level():
    # Two folder levels: depth 0 = "A", depth 1 = "B" or "Bx" (typo)
    rows = [{"relpath": "A/B/file1.asc"} for _ in range(5)]
    rows += [{"relpath": "A/Bx/file2.asc"}]
    result = detect_typo_candidates(rows, max_edit_distance=2, min_suggested_count=2)
    # Bx (1x) vs B (5x) at depth 1
    typo_at_1 = [t for t in result if t[1] == 1]
    assert len(typo_at_1) >= 1
    relpath, depth, segment, suggested, cnt_a, cnt_s = typo_at_1[0]
    assert depth == 1
    assert (segment == "Bx" and suggested == "B") or (segment == "B" and suggested == "Bx")
