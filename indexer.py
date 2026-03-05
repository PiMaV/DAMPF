# indexer.py - Config-driven semantic indexer (used by CLI and GUI).
# Naming conventions and recognized patterns: see Proper_file_naming_EN.md or Naming_Cheat_Sheet.md.

from __future__ import annotations

import csv
import json
import math
import os
import re
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from key_lut import GAS_KEYS, extract_val_for_export, format_val_unit, get_display_value, is_quantitative_val, unit_scale

# Default config (overridable via run_indexer config)
DEFAULT_ALLOWED_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp",
    ".csv", ".tsv", ".txt", ".dat", ".asc",
    ".npy", ".npz",
    ".h5", ".hdf5",
    ".json", ".yaml", ".yml",
}

DEFAULT_STOPWORDS = {
    "data", "dataset", "results", "export", "out", "output", "rawdata", "measurements",
    "misc", "temp", "test", "new", "old",
}

DEFAULT_MODALITY_MAP = {
    "rgb": "rgb",
    "ir": "ir",
    "thermal": "thermal",
    "th": "thermal",
    "depth": "depth",
    "tof": "tof",
    "oes": "oes",
    "spec": "spectroscopy",
    "spectra": "spectroscopy",
}

PROC_TAGS = {
    "raw", "dark", "flat", "cal", "calib", "ref", "reference", "bg", "background",
    "mean", "avg", "median", "sum", "diff", "sub", "subtract", "norm", "normalized",
    "aligned", "registered", "denoise", "filtered",
}

# Regexes (internal)
RE_DATE_ISO = re.compile(r"^(?P<y>20\d{2})[-_\.]?(?P<m>\d{2})[-_\.]?(?P<d>\d{2})$")
RE_DATE_ISO_DASH = re.compile(r"^(?P<y>20\d{2})-(?P<m>\d{2})-(?P<d>\d{2})$")
RE_DATE_COMPACT = re.compile(r"^(?P<y>20\d{2})(?P<m>\d{2})(?P<d>\d{2})$")
RE_DATE_EU = re.compile(r"^(?P<d>\d{1,2})[-\.](?P<m>\d{1,2})[-\.](?P<y>20\d{2})$")
RE_RUN = re.compile(r"^(?:run|r)(?P<n>\d{1,4})$")
RE_REP = re.compile(r"^(?:rep|repeat|repetition)(?P<n>\d{1,4})$")
RE_TRIAL = re.compile(r"^(?:trial|tr)(?P<n>\d{1,4})$")
RE_CAM = re.compile(r"^(?:cam|camera)(?P<n>\d{1,3})$")
RE_CH = re.compile(r"^(?:ch|chan|channel|c)(?P<n>\d{1,3})$", re.IGNORECASE)
RE_ROI = re.compile(r"^(?:roi)(?P<id>[a-z0-9]+)$")
RE_FRAME = re.compile(r"^(?:frame|f)(?P<n>\d{1,9})$")
RE_SEQ = re.compile(r"^(?P<n>\d{1,2})$")
# Val: allow . or p as decimal (e.g. 4p2 -> 4.2); optional exponent
_VAL = r"[-+]?\d+(?:[p.]\d+)?(?:e[-+]?\d+)?"
RE_EXPOSURE = re.compile(r"^(?:exp|exposure|texp|texp=)?(?P<val>" + _VAL + r")(?P<unit>ns|us|µs|ms|s)$")
RE_TEMP = re.compile(r"^(?:(?:t|temp|temperature)(?:=)?)?(?P<val>[-+]?\d+(?:[p.]\d+)?)(?P<unit>c|°c|k)$")
RE_FREQ = re.compile(r"^(?:(?:f|freq|frequency)(?:=)?)?(?P<val>" + _VAL + r")(?P<unit>hz|khz|mhz|ghz)$")
RE_VOLT = re.compile(r"^(?:(?:u|v|volt|voltage)(?:=)?)?(?P<val>" + _VAL + r")(?P<unit>uv|mv|v|kv)$")
RE_CURR = re.compile(r"^(?:(?:i|a|amp|current)(?:=)?)?(?P<val>" + _VAL + r")(?P<unit>ua|ma|a)$")
RE_LEN = re.compile(
    r"^(?:x|y|z|d|dist|distance|meas|measurement|px|um|µm|mm|nm)?"
    r"(?P<val>[-+]?\d+(?:[p.]\d+)?)(?P<unit>nm|um|µm|mm|cm|m|px)$"
)
RE_KV = re.compile(r"^(?P<k>[a-zA-Z][a-zA-Z0-9]{0,16})=(?P<v>.+)$")

# One token = number (optional p decimal) + unit; keep as single token so parser sees e.g. 4p2kv, 500us
RE_NUMBER_UNIT = re.compile(
    r"^[-+]?\d+(?:p\d+)?(?:\.\d+)?(?:e[-+]?\d+)?"
    r"(?:ns|us|µs|ms|s|hz|khz|mhz|ghz|uv|mv|v|kv|ua|ma|a|nm|um|mm|cm|m|px)$",
    re.IGNORECASE,
)

# Letter(s) + number as one token (e.g. M25, S4, T250) -> param key=value
RE_PARAM_TOKEN = re.compile(r"^[A-Za-z]{1,3}\d+$", re.IGNORECASE)
RE_PARAM = re.compile(r"^([a-z]{1,3})(\d+)$")
# Number + letter(s) as one token (e.g. 300He, 300N2); letter part may contain digits (N2)
RE_NUM_LETTERS_TOKEN = re.compile(r"^\d+(?:p\d+)?[A-Za-z][A-Za-z0-9]{0,2}$", re.IGNORECASE)
RE_NUM_LETTERS = re.compile(r"^(\d+(?:p\d+)?)([a-z][a-z0-9]{0,2})$")
# 2-4 letters only (e.g. FF, KPSc) -> string param key=value
RE_LETTERS_ONLY_TOKEN = re.compile(r"^[A-Za-z]{2,4}$", re.IGNORECASE)
# Flow: Zahl + slm + Gas (e.g. 5slmAr, 10slmN2) -> gas_flow
RE_SLM_FLOW_TOKEN = re.compile(r"^\d+(?:p\d+)?slm[a-zA-Z][a-zA-Z0-9]{0,2}$", re.IGNORECASE)
RE_SLM_FLOW = re.compile(r"^(\d+(?:p\d+)?)slm([a-zA-Z][a-zA-Z0-9]{0,2})$", re.IGNORECASE)


def is_hidden(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    return False


def split_transitions(s: str) -> List[str]:
    if not s:
        return []
    s2 = re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)
    s2 = re.sub(r"(\d)([A-Za-z])", r"\1 \2", s2)
    s2 = s2.replace("µ", "u")
    parts = s2.split()
    return parts if parts else [s]


def tokenize_string(
    s: str,
    stopwords: Optional[set] = None,
    norm_to_orig: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Return normalized tokens. If norm_to_orig given, fill with normalized->original mapping."""
    stopwords = stopwords or DEFAULT_STOPWORDS
    s = s.strip()
    if not s:
        return []
    if norm_to_orig is None:
        norm_to_orig = {}
    # Normalize decimal dot to p (e.g. 4.2kv -> 4p2kv) before split, since . is a delimiter
    s = re.sub(r"(\d)\.(\d)", r"\1p\2", s)
    s = re.sub(r"[\/\\\-\_\.\+\(\)\[\]\{\},;]+", " ", s)
    raw = [p for p in s.split() if p]
    out: List[str] = []
    for p in raw:
        pl = p.replace("µ", "u").lower()
        if RE_NUMBER_UNIT.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif RE_PARAM_TOKEN.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif RE_NUM_LETTERS_TOKEN.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif RE_LETTERS_ONLY_TOKEN.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif RE_SLM_FLOW_TOKEN.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        else:
            sub = split_transitions(p)
            for t in sub:
                tt = t.strip().lower()
                norm_to_orig.setdefault(tt, t)
            out.extend(sub)
    norm = []
    for t in out:
        tt = t.strip().lower()
        if not tt or tt in stopwords:
            continue
        norm.append(tt)
    return norm


def tokenize_path(path: Path, root: Path, folder_depth: int, stopwords: Optional[set] = None) -> List[str]:
    folder_tokens, file_tokens, _ = tokenize_path_parts(path, root, folder_depth, stopwords)
    return folder_tokens + file_tokens


def tokenize_path_parts(
    path: Path, root: Path, folder_depth: int, stopwords: Optional[set] = None
) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Return (folder_tokens, file_tokens, norm_to_orig)."""
    rel = path.relative_to(root)
    parts = list(rel.parts)
    norm_to_orig: Dict[str, str] = {}
    if not parts:
        return [], [], norm_to_orig
    filename = parts[-1]
    folders = parts[:-1]
    if folder_depth <= 0:
        folder_tokens: List[str] = []
    else:
        use_folders = folders[-folder_depth:] if folder_depth < 99 else folders
        folder_tokens = []
        for f in use_folders:
            folder_tokens.extend(tokenize_string(f, stopwords, norm_to_orig))
    stem = Path(filename).stem
    file_tokens = tokenize_string(stem, stopwords, norm_to_orig)
    return folder_tokens, file_tokens, norm_to_orig


def parse_number(s: str) -> Optional[float]:
    s = s.strip().lower()
    if not s:
        return None
    s = s.replace("p", ".") if re.fullmatch(r"\d+p\d+", s) else s
    try:
        return float(s)
    except ValueError:
        return None




@dataclass
class ParseResult:
    data: Dict[str, Any]
    trace: List[str]
    recognized: int
    total_tokens: int
    token_to_key: Dict[str, str]

    @property
    def confidence(self) -> float:
        if self.total_tokens <= 0:
            return 0.0
        ratio = self.recognized / max(1, self.total_tokens)
        return float(1.0 - math.exp(-3.0 * ratio))


def parse_tokens(tokens: List[str], modality_map: Optional[Dict[str, str]] = None) -> ParseResult:
    modality_map = modality_map or DEFAULT_MODALITY_MAP
    data: Dict[str, Any] = {}
    trace: List[str] = []
    token_to_key: Dict[str, str] = {}
    recognized = 0
    total = len(tokens)

    def set_field(k: str, v: Any, why: str, token: Optional[str] = None):
        nonlocal recognized
        if v is None:
            return
        if k not in data:
            data[k] = v
            trace.append(f"{k}:{why}")
            recognized += 1
            if token is not None:
                token_to_key[token] = k

    for tok in tokens:
        if not tok:
            continue
        m = (
            RE_DATE_ISO_DASH.match(tok)
            or RE_DATE_ISO.match(tok)
            or RE_DATE_COMPACT.match(tok)
            or RE_DATE_EU.match(tok)
        )
        if m and "date" not in data:
            y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                set_field("date", f"{y:04d}-{mo:02d}-{d:02d}", "date", tok)
                continue
        m = RE_KV.match(tok)
        if m:
            k, v = m.group("k").lower(), m.group("v").lower()
            if k not in data:
                data[k] = v
                trace.append(f"{k}:kv")
                recognized += 1
                token_to_key[tok] = k
            continue
        m = RE_RUN.match(tok)
        if m:
            set_field("run", int(m.group("n")), "run", tok)
            continue
        m = RE_REP.match(tok)
        if m:
            set_field("rep", int(m.group("n")), "rep", tok)
            continue
        m = RE_TRIAL.match(tok)
        if m:
            set_field("trial", int(m.group("n")), "trial", tok)
            continue
        m = RE_CAM.match(tok)
        if m:
            set_field("camera", int(m.group("n")), "cam", tok)
            continue
        m = RE_CH.match(tok)
        if m:
            set_field("channel", int(m.group("n")), "ch", tok)
            continue
        m = RE_ROI.match(tok)
        if m:
            set_field("roi", m.group("id"), "roi", tok)
            continue
        m = RE_FRAME.match(tok)
        if m:
            set_field("frame", int(m.group("n")), "frame", tok)
            continue
        m = RE_PARAM.match(tok)
        if m:
            key, val = m.group(1), m.group(2)
            if key not in data:
                data[key] = int(val)
                trace.append(f"{key}:param")
                recognized += 1
                token_to_key[tok] = key
            continue
        m = RE_SEQ.match(tok)
        if m and "seq" not in data:
            set_field("seq", int(m.group("n")), "seq", tok)
            continue
        if re.fullmatch(r"\d+", tok) and "frame" not in data:
            set_field("frame", int(tok), "frame", tok)
            continue
        if tok in modality_map:
            set_field("modality", modality_map[tok], "modality", tok)
            continue
        if tok in PROC_TAGS:
            if "processing" not in data:
                data["processing"] = [tok]
                trace.append("processing:tag")
                recognized += 1
                token_to_key[tok] = "processing"
            elif isinstance(data["processing"], list) and tok not in data["processing"]:
                data["processing"].append(tok)
            continue
        m = RE_EXPOSURE.match(tok)
        if m:
            val = parse_number(m.group("val"))
            unit = m.group("unit").replace("µ", "u")
            if val is not None:
                # Val in gecrawlter Einheit (500 bei "500us"); unit fuer Rueckfuehrbarkeit
                set_field("exposure", {"val": val, "unit": unit}, "exposure", tok)
            continue
        m = RE_TEMP.match(tok)
        if m:
            val = parse_number(m.group("val"))
            unit = m.group("unit").replace("°", "").lower()
            if val is not None:
                set_field("temp", {"val": val, "unit": unit}, "temp", tok)
            continue
        m = RE_FREQ.match(tok)
        if m:
            val = parse_number(m.group("val"))
            unit = m.group("unit").lower()
            if val is not None:
                set_field("freq", {"val": val, "unit": unit}, "freq", tok)
            continue
        m = RE_VOLT.match(tok)
        if m:
            val = parse_number(m.group("val"))
            unit = m.group("unit").lower()
            if val is not None:
                set_field("voltage", {"val": val, "unit": unit}, "volt", tok)
            continue
        m = RE_CURR.match(tok)
        if m:
            val = parse_number(m.group("val"))
            unit = m.group("unit").lower()
            if val is not None:
                set_field("current", {"val": val, "unit": unit}, "curr", tok)
            continue
        m = RE_LEN.match(tok)
        if m and any(ch.isdigit() for ch in tok):
            val = parse_number(m.group("val"))
            unit = m.group("unit").replace("µ", "u")
            if val is not None:
                entry = {"val": val, "unit": unit, "SI_m": (val * unit_scale(unit)) if unit != "px" else None}
                if "lengths" not in data:
                    data["lengths"] = [entry]
                    trace.append("lengths:len")
                    recognized += 1
                    token_to_key[tok] = "lengths"
                elif isinstance(data.get("lengths"), list):
                    data["lengths"].append(entry)
            continue
        m = RE_NUM_LETTERS.match(tok)
        if m:
            num_part, letters = m.group(1), m.group(2).lower()
            val = parse_number(num_part)
            if val is not None:
                if letters in GAS_KEYS:
                    set_field(letters, {"val": int(val) if val == int(val) else val, "unit": "%"}, "gas_pct", tok)
                else:
                    set_field(letters, int(val) if val == int(val) else val, "num_letters", tok)
            continue
        m = RE_SLM_FLOW.match(tok)
        if m:
            val = parse_number(m.group(1))
            gas = m.group(2)  # preserve case (Ar, N2)
            if val is not None:
                set_field("gas_flow", {"val": val, "unit": "slm", "gas": gas}, "gas_flow", tok)
            continue
        if RE_LETTERS_ONLY_TOKEN.match(tok) and tok not in modality_map and tok not in PROC_TAGS and tok not in data:
            set_field(tok, tok, "letters_param", tok)
            continue
        if re.fullmatch(r"(?:exp|experiment)\d{1,4}", tok):
            set_field("experiment", tok.replace("experiment", "exp"), "experiment", tok)
            continue
        if re.fullmatch(r"(?:sample|smp|specimen)[a-z0-9]{1,6}", tok):
            set_field("sample", tok, "sample", tok)
            continue

    return ParseResult(data=data, trace=trace, recognized=recognized, total_tokens=total, token_to_key=token_to_key)


def detect_dominant_suffix(
    root: Path,
    allowed_suffixes: Optional[set] = None,
    recursive: bool = True,
    include_hidden: bool = False,
) -> Optional[str]:
    """
    Quick scan of root + subfolders; return the most frequent file extension.
    Used for majority-vote: focus on the dominant file type.
    """
    allowed_suffixes = allowed_suffixes or DEFAULT_ALLOWED_SUFFIXES
    candidates = root.rglob("*") if recursive else root.glob("*")
    counts: Counter[str] = Counter()
    for p in candidates:
        if not p.is_file():
            continue
        if not include_hidden and (is_hidden(p) or any(is_hidden(x) for x in p.parents)):
            continue
        ext = p.suffix.lower()
        if ext in allowed_suffixes:
            counts[ext] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def iter_files(
    root: Path,
    allowed_suffixes: Optional[set] = None,
    recursive: bool = True,
    include_hidden: bool = False,
) -> List[Path]:
    allowed_suffixes = allowed_suffixes or DEFAULT_ALLOWED_SUFFIXES
    candidates = root.rglob("*") if recursive else root.glob("*")
    out: List[Path] = []
    for p in candidates:
        if not p.is_file():
            continue
        if not include_hidden and (is_hidden(p) or any(is_hidden(x) for x in p.parents)):
            continue
        if p.suffix.lower() not in allowed_suffixes:
            continue
        out.append(p)
    return out


def _fmt_group_val(v: Any) -> str:
    """Format Wert fuer Gruppen-Key; val+unit Dict -> '500 us'."""
    if is_quantitative_val(v):
        return format_val_unit(v)
    return str(v) if v is not None else ""


def group_rows(rows: List[Dict[str, Any]], keys: Tuple[str, ...]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for r in rows:
        gk = " | ".join(f"{k}={_fmt_group_val(r.get(k))}" for k in keys)
        groups.setdefault(gk, []).append(r["path"])
    return groups


# Keys we never suggest for grouping (internal/metadata)
_ROW_META_KEYS = {"path", "relpath", "ext", "stem", "tokens", "trace", "recognized", "total_tokens", "confidence", "_duplicate_keys", "_folder_tokens", "_file_tokens", "_folder_token_to_key", "_file_token_to_key", "_token_original"}

# Preferred order for group keys when they appear in data
_PREFERRED_GROUP_ORDER = ("date", "experiment", "sample", "run", "rep", "trial", "exposure", "modality", "camera", "channel")


def suggest_nomenclature(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    From indexed rows, derive detected fields and suggested GROUP_KEYS.
    Returns {"detected_fields": [...], "suggested_group_keys": [...]}.
    """
    if not rows:
        return {"detected_fields": [], "suggested_group_keys": list(_PREFERRED_GROUP_ORDER)[:5]}

    all_keys: Dict[str, int] = {}
    for r in rows:
        for k in r.keys():
            if k in _ROW_META_KEYS:
                continue
            all_keys[k] = all_keys.get(k, 0) + 1

    detected_fields = sorted(all_keys.keys(), key=lambda x: (-all_keys[x], x))

    from key_lut import _normalize_key
    suggested = [k for k in _PREFERRED_GROUP_ORDER if k in all_keys]
    for k in detected_fields:
        if k not in suggested:
            suggested.append(k)
    suggested = list(dict.fromkeys(_normalize_key(k) for k in suggested))
    return {"detected_fields": detected_fields, "suggested_group_keys": suggested}


def suggest_categorical_keys(
    rows: List[Dict[str, Any]], threshold: int = 10
) -> Dict[str, bool]:
    """
    Suggest which keys to treat as categorical for WOLKE (container/filter instead of histogram).
    Rule of thumb: fewer than `threshold` distinct values -> suggest categorical.
    Returns dict: key -> True (categorical) or False (numeric). Only keys that appear in data.
    """
    if not rows:
        return {}
    distinct: Dict[str, set] = {}
    for r in rows:
        for k in r:
            if k in _ROW_META_KEYS:
                continue
            v = r.get(k)
            if v is None:
                continue
            # Normalise for distinct count (hashable string)
            if isinstance(v, (list, dict)):
                norm = json.dumps(v, sort_keys=True, default=str)
            else:
                norm = str(v)
            distinct.setdefault(k, set()).add(norm)
    out: Dict[str, bool] = {}
    for k, vals in distinct.items():
        out[k] = len(vals) < threshold
    return out


# Min. files to use multicore (below: process spawn overhead > gain)
_PARALLEL_THRESHOLD = 100


def _index_single_file(
    args: Tuple[Path, Path, int, frozenset, Dict[str, str]]
) -> Dict[str, Any]:
    """Worker for ProcessPoolExecutor: index one file. Top-level for picklability."""
    p, root, folder_depth, stopwords, modality_map = args
    folder_tokens, file_tokens, norm_to_orig = tokenize_path_parts(p, root, folder_depth, stopwords=stopwords)
    tokens = folder_tokens + file_tokens
    pr_folder = parse_tokens(folder_tokens, modality_map=modality_map)
    pr_file = parse_tokens(file_tokens, modality_map=modality_map)
    row: Dict[str, Any] = {}
    row.update(pr_folder.data)
    row.update(pr_file.data)
    dup = set(pr_folder.data.keys()) & set(pr_file.data.keys())
    if dup:
        row["_duplicate_keys"] = sorted(dup)
    row["_folder_tokens"] = folder_tokens
    row["_file_tokens"] = file_tokens
    row["_token_original"] = norm_to_orig
    row["_folder_token_to_key"] = getattr(pr_folder, "token_to_key", {})
    row["_file_token_to_key"] = getattr(pr_file, "token_to_key", {})
    row["path"] = str(p)
    row["relpath"] = str(p.relative_to(root))
    row["ext"] = p.suffix.lower()
    row["stem"] = p.stem
    row["tokens"] = tokens
    row["trace"] = pr_file.trace
    row["recognized"] = pr_file.recognized
    row["total_tokens"] = len(tokens)
    row["confidence"] = round(
        (1.0 - math.exp(-3.0 * pr_file.recognized / max(1, len(tokens)))), 4
    )
    return row


def run_indexer(
    root_dir: str | Path,
    output_dir: str | Path,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """
    Run full index pipeline. Config can override:
    allowed_suffixes (set or list), folder_token_depth (int), group_keys (tuple or list),
    recursive (bool), include_hidden (bool), stopwords (set or list), modality_map (dict),
    parallel_threshold (int, default 100: min files to use multicore),
    parallel_max_workers (int, default cpu_count-1),
    log_callback (callable[str] for timing/log messages).
    Returns (rows, groups).
    """
    cfg = config or {}
    root = Path(root_dir).expanduser().resolve()
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    allowed = cfg.get("allowed_suffixes")
    if allowed is not None and not isinstance(allowed, set):
        allowed = set(allowed)
    allowed = allowed or DEFAULT_ALLOWED_SUFFIXES

    recursive = cfg.get("recursive", True)
    include_hidden = cfg.get("include_hidden", False)

    folder_depth = cfg.get("folder_token_depth", 99)
    group_keys = cfg.get("group_keys")
    if group_keys is not None and not isinstance(group_keys, tuple):
        group_keys = tuple(group_keys) if group_keys else ("date", "experiment", "sample", "run", "rep")
    else:
        group_keys = group_keys or ("date", "experiment", "sample", "run", "rep")
    # Legacy: exposure_s/exposure_us -> exposure; deduplizieren
    from key_lut import _normalize_key
    seen: set[str] = set()
    normalized: list[str] = []
    for k in group_keys:
        nk = _normalize_key(k)
        if nk not in seen:
            seen.add(nk)
            normalized.append(nk)
    group_keys = tuple(normalized)

    stopwords = cfg.get("stopwords")
    if stopwords is not None and not isinstance(stopwords, set):
        stopwords = set(stopwords)
    stopwords = stopwords or DEFAULT_STOPWORDS
    modality_map = cfg.get("modality_map") or DEFAULT_MODALITY_MAP
    log_cb: Optional[Callable[[str], None]] = cfg.get("log_callback")

    def _log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    t0 = time.perf_counter()
    _log(f"[{0:.3f}s] iter_files start")
    files = iter_files(root, allowed_suffixes=allowed, recursive=recursive, include_hidden=include_hidden)
    file_list = list(files)
    t1 = time.perf_counter()
    _log(f"[{t1 - t0:.3f}s] iter_files done: {len(file_list)} files")

    stopwords_frozen = frozenset(stopwords)
    modality_map_copy = dict(modality_map)

    parallel_threshold = cfg.get("parallel_threshold", _PARALLEL_THRESHOLD)
    max_workers = cfg.get("parallel_max_workers")
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 1) - 1)

    use_parallel = len(file_list) >= parallel_threshold and max_workers > 1
    _log(f"[{t1 - t0:.3f}s] index: {'parallel' if use_parallel else 'sequential'} (workers={max_workers})")

    t2 = time.perf_counter()
    if use_parallel:
        args_list = [
            (p, root, folder_depth, stopwords_frozen, modality_map_copy)
            for p in file_list
        ]
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            rows = list(ex.map(_index_single_file, args_list))
    else:
        rows = [
            _index_single_file((p, root, folder_depth, stopwords_frozen, modality_map_copy))
            for p in file_list
        ]
    t3 = time.perf_counter()
    _log(f"[{t3 - t0:.3f}s] index done: {t3 - t2:.3f}s for {len(rows)} files ({len(rows) / max(0.001, t3 - t2):.0f} files/s)")

    t4 = time.perf_counter()
    groups = group_rows(rows, group_keys)
    t5 = time.perf_counter()
    _log(f"[{t5 - t0:.3f}s] group_rows: {t5 - t4:.3f}s, {len(groups)} groups")
    _log(f"[{t5 - t0:.3f}s] total")
    return rows, groups


def write_jsonl(
    rows: List[Dict[str, Any]],
    out_path: Path,
    used_keys: List[str] | None = None,
    column_si_scale: Dict[str, int] | None = None,
) -> None:
    """Export JSONL: numerische Werte; bei column_si_scale.get(k)==0 Konvertierung zu SI."""
    from key_lut import get_export_value_and_metadata
    keep = set(used_keys) | {"path", "relpath"} if used_keys else None
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            out = {k: v for k, v in r.items() if (keep is None or k in keep) and not k.startswith("_")}
            out = {k: get_export_value_and_metadata(get_display_value(v, r), k, column_si_scale)[0] for k, v in out.items()}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


def write_csv(
    rows: List[Dict[str, Any]],
    out_path: Path,
    used_keys: List[str] | None = None,
    column_si_scale: Dict[str, int] | None = None,
) -> None:
    """Export CSV: numerische Werte; bei column_si_scale.get(k)==0 Konvertierung zu SI."""
    from key_lut import get_export_value_and_metadata
    keep = set(used_keys) | {"path", "relpath"} if used_keys else None
    flat_rows: List[Dict[str, Any]] = []
    for r in rows:
        rr = {k: v for k, v in r.items() if (keep is None or k in keep) and not k.startswith("_")}
        for k in list(rr.keys()):
            rr[k] = get_export_value_and_metadata(get_display_value(rr[k], r), k, column_si_scale)[0]
        if isinstance(rr.get("processing"), list):
            rr["processing"] = ",".join(rr["processing"])
        if isinstance(rr.get("trace"), list):
            rr["trace"] = " | ".join(rr["trace"])
        if isinstance(rr.get("tokens"), list):
            rr["tokens"] = " ".join(rr["tokens"])
        flat_rows.append(rr)
    keys = sorted({k for r in flat_rows for k in r.keys()})
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in flat_rows:
            w.writerow(r)


def build_column_metadata(
    rows: List[Dict[str, Any]],
    keys: List[str] | None = None,
    column_si_scale: Dict[str, int] | None = None,
) -> Dict[str, Dict[str, str]]:
    """Column -> {unit, raw_unit}. Bei si_scale=0: unit=SI-Basis, raw_unit=Original."""
    from key_lut import SI_BASE_UNIT, get_export_value_and_metadata
    out: Dict[str, Dict[str, str]] = {}
    key_set: set[str] | None = set(keys) if keys else None
    if key_set is None:
        key_set = set()
        for r in rows:
            key_set.update(k for k in r if not k.startswith("_"))
    for k in key_set:
        if k in out:
            continue
        for r in rows:
            v = r.get(k)
            if v is None:
                continue
            if is_quantitative_val(v):
                _, u, raw_u = get_export_value_and_metadata(v, k, column_si_scale)
                out[k] = {"unit": u, "raw_unit": raw_u}
                break
            if isinstance(v, list) and v and is_quantitative_val(v[0]):
                _, u, raw_u = get_export_value_and_metadata(v, k, column_si_scale)
                out[k] = {"unit": u, "raw_unit": raw_u}
                break
    return out


def write_index_meta(meta: Dict[str, Dict[str, str]], out_path: Path) -> None:
    """Schreibt column_metadata als index_meta.json (unit, raw_unit pro Spalte)."""
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
