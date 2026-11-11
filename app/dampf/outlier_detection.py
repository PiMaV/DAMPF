# outlier_detection.py - Detect paths that deviate from schema or contain likely typos in folder names.

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Schema outliers (confidence / missing keys) ---

DEFAULT_CONFIDENCE_THRESHOLD = 0.3
DEFAULT_KEY_COVERAGE_PCT = 80.0


def detect_schema_outliers(
    rows: List[Dict[str, Any]],
    detected_keys: Optional[List[str]] = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    key_coverage_pct: float = DEFAULT_KEY_COVERAGE_PCT,
) -> List[Tuple[Dict[str, Any], str]]:
    """
    Return list of (row, reason) for rows that deviate from the majority schema.
    - Low confidence (below threshold).
    - Missing keys that appear in key_coverage_pct% of rows.
    """
    if not rows:
        return []
    result: List[Tuple[Dict[str, Any], str]] = []
    keys = detected_keys or []
    n = len(rows)

    # Count per-key coverage
    key_counts: Dict[str, int] = {}
    for r in rows:
        for k in keys:
            if k in _ROW_META_KEYS:
                continue
            if r.get(k) is not None:
                key_counts[k] = key_counts.get(k, 0) + 1

    # Keys that "most" rows have (>= key_coverage_pct%)
    majority_keys = [k for k in keys if (key_counts.get(k, 0) / max(1, n)) * 100 >= key_coverage_pct]

    for r in rows:
        reasons: List[str] = []
        conf = r.get("confidence")
        if conf is not None and isinstance(conf, (int, float)) and conf < confidence_threshold:
            reasons.append(f"confidence {conf:.2f} < {confidence_threshold}")
        missing = [k for k in majority_keys if r.get(k) is None]
        if missing:
            reasons.append(f"missing keys: {', '.join(missing)}")
        if reasons:
            result.append((r, "; ".join(reasons)))
    return result


# Meta keys to ignore when considering "detected" keys (align with indexer)
_ROW_META_KEYS = {
    "path", "relpath", "ext", "stem", "tokens", "trace", "recognized",
    "total_tokens", "confidence", "_duplicate_keys", "_folder_tokens", "_file_tokens",
    "_folder_token_to_key", "_file_token_to_key", "_token_original",
}


# --- Typo candidates (rare folder segment similar to frequent one) ---

def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (stdlib only)."""
    a, b = a.lower(), b.lower()
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    # dp[i][j] = cost to turn a[:i] into b[:j]
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i]
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr.append(min(prev[j - 1] + cost, prev[j] + 1, curr[j - 1] + 1))
        prev = curr
    return prev[m]


TypoCandidate = Tuple[str, int, str, str, int, int]
# (relpath, depth_index, segment, suggested_segment, count_actual, count_suggested)


def detect_typo_candidates(
    rows: List[Dict[str, Any]],
    depth_counts: Optional[Dict[int, Dict[str, int]]] = None,
    min_freq_ratio: float = 2.0,
    max_edit_distance: int = 2,
    min_suggested_count: int = 2,
) -> List[TypoCandidate]:
    """
    Find folder segments at a given depth that appear rarely but are similar to a frequent segment.
    Returns list of (relpath, depth_index, segment, suggested_segment, count_actual, count_suggested).
    """
    if not rows:
        return []
    # Build per-depth segment counts from relpaths if not provided
    if depth_counts is None:
        depth_counts = defaultdict(lambda: defaultdict(int))
        for r in rows:
            rel = r.get("relpath") or ""
            if not rel:
                continue
            parts = Path(rel).parts
            folder_parts = parts[:-1] if len(parts) > 1 else []
            for d, seg in enumerate(folder_parts):
                depth_counts[d][seg] += 1

    result: List[TypoCandidate] = []
    relpaths_with_segment: Dict[Tuple[int, str], List[str]] = defaultdict(list)
    for r in rows:
        rel = r.get("relpath") or ""
        if not rel:
            continue
        parts = Path(rel).parts
        folder_parts = parts[:-1] if len(parts) > 1 else []
        for d, seg in enumerate(folder_parts):
            relpaths_with_segment[(d, seg)].append(rel)

    for (depth, segment), count_actual in _iter_segment_counts(depth_counts):
        if count_actual >= min_suggested_count:
            continue
        best: Optional[Tuple[str, int]] = None
        for other, count_suggested in depth_counts[depth].items():
            if other == segment or count_suggested < min_suggested_count:
                continue
            if count_suggested < count_actual * min_freq_ratio:
                continue
            dist = _edit_distance(segment, other)
            if dist <= max_edit_distance and dist >= 1:
                if best is None or count_suggested > best[1]:
                    best = (other, count_suggested)
        if best is not None:
            suggested_segment, count_suggested = best
            for rel in relpaths_with_segment[(depth, segment)]:
                result.append((rel, depth, segment, suggested_segment, count_actual, count_suggested))
    return result


def _iter_segment_counts(
    depth_counts: Dict[int, Dict[str, int]],
) -> List[Tuple[Tuple[int, str], int]]:
    out: List[Tuple[Tuple[int, str], int]] = []
    for d, counts in depth_counts.items():
        for seg, cnt in counts.items():
            out.append(((d, seg), cnt))
    return out
