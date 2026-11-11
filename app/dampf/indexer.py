# indexer.py - Config-driven semantic indexer (used by CLI and GUI).
# Naming conventions: see docs/naming/cheat_sheet_v2.md and docs/naming/file_names_explained_v2.md.

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

from dampf.key_lut import GAS_KEYS, extract_val_for_export, format_val_unit, get_display_value, is_quantitative_val, unit_scale
from dampf.naming_rules import PREDEFINED_MODALITY, PREDEFINED_PROCESSING, PREDEFINED_UNITS

# Default config (overridable via run_indexer config)
DEFAULT_ALLOWED_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".img",
    ".csv", ".tsv", ".txt", ".dat", ".asc",
    ".npy", ".npz",
    ".h5", ".hdf5",
    ".json", ".yaml", ".yml",
}

DEFAULT_STOPWORDS = {
    "data", "dataset", "results", "export", "out", "output", "rawdata", "measurements",
    "misc", "temp", "test", "new", "old",
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
# name=value inside one parameter. The name may contain '-' (it binds a name).
# No length cap: '_' already ended the parameter, and the path limit covers the rest.
RE_KV = re.compile(r"^(?P<k>[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)=(?P<v>.+)$")

_NUMBER_HEAD = r"[-+]?\d+(?:p\d+|\.\d+)?(?:e[-+]?\d+)?"

# Letter(s) + number as one token (e.g. M25, S4, T250) -> param key=value
RE_PARAM_TOKEN = re.compile(r"^[A-Za-z]{1,3}\d+$", re.IGNORECASE)
RE_PARAM = re.compile(r"^([a-z]{1,3})(\d+)$")
# Number + letter(s) as one token (e.g. 300He, 300N2); letter part may contain digits (N2)
RE_NUM_LETTERS_TOKEN = re.compile(r"^\d+(?:p\d+)?[A-Za-z][A-Za-z0-9]{0,2}$", re.IGNORECASE)
RE_NUM_LETTERS = re.compile(r"^(\d+(?:p\d+)?)([a-z][a-z0-9]{0,2})$")
# Flow: Zahl + slm + Gas (e.g. 5slmAr, 10slmN2) -> gas_flow
RE_SLM_FLOW_TOKEN = re.compile(r"^\d+(?:p\d+)?slm[a-zA-Z][a-zA-Z0-9]{0,2}$", re.IGNORECASE)
RE_SLM_FLOW = re.compile(r"^(\d+(?:p\d+)?)slm([a-zA-Z][a-zA-Z0-9]{0,2})$", re.IGNORECASE)


def _unit_map_or_default(unit_map: Optional[Dict[str, str]]) -> Dict[str, str]:
    return PREDEFINED_UNITS if unit_map is None else unit_map


def _number_unit_token_re(unit_map: Dict[str, str]) -> re.Pattern:
    """Keep number+known-suffix as one token (4p2kv, 500us). Empty map matches nothing."""
    if not unit_map:
        return re.compile(r"(?!)")
    alts = "|".join(re.escape(s) for s in sorted(unit_map, key=len, reverse=True))
    return re.compile(rf"^{_NUMBER_HEAD}(?:{alts})$", re.IGNORECASE)


def match_number_unit(piece: str, unit_map: Optional[Dict[str, str]] = None) -> Optional[Tuple[str, Any, str]]:
    """Number plus a suffix from the unit list. The suffix names the column."""
    units = _unit_map_or_default(unit_map)
    if not units or not piece:
        return None
    text = piece.lower().replace("µ", "u").replace("°", "")
    m = re.fullmatch(rf"({_NUMBER_HEAD})([a-z]+)", text)
    if not m:
        return None
    suffix = m.group(2)
    if suffix not in units:
        return None
    val = parse_number(m.group(1))
    if val is None:
        return None
    column = units[suffix].strip().lower()
    if not column:
        return None
    if column == "lengths":
        entry = {"val": val, "unit": suffix, "SI_m": (val * unit_scale(suffix)) if suffix != "px" else None}
        return column, entry, "lengths"
    return column, {"val": val, "unit": suffix}, column


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


def parse_compact_datetime(tok: str) -> Optional[Tuple[str, str]]:
    """If tok is YYYYMMDDHHMMSS with a plausible calendar+clock, return (date ISO, HH:MM:SS)."""
    if not re.fullmatch(r"\d{14}", tok):
        return None
    y, mo, d = int(tok[0:4]), int(tok[4:6]), int(tok[6:8])
    hh, mm, ss = int(tok[8:10]), int(tok[10:12]), int(tok[12:14])
    if not (2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}", f"{hh:02d}:{mm:02d}:{ss:02d}"


def _param_digit_part_is_datetime_or_date(digit_part: str) -> bool:
    """True when a glued letter+digits token should split (camera IMG… timestamps)."""
    if parse_compact_datetime(digit_part) is not None:
        return True
    if re.fullmatch(r"20\d{6}", digit_part):
        mo, d = int(digit_part[4:6]), int(digit_part[6:8])
        return 1 <= mo <= 12 and 1 <= d <= 31
    return False


def tokenize_string(
    s: str,
    stopwords: Optional[set] = None,
    norm_to_orig: Optional[Dict[str, str]] = None,
    unit_map: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Return normalized tokens. If norm_to_orig given, fill with normalized->original mapping."""
    stopwords = stopwords or DEFAULT_STOPWORDS
    units = _unit_map_or_default(unit_map)
    number_unit = _number_unit_token_re(units)
    s = s.strip()
    if not s:
        return []
    if norm_to_orig is None:
        norm_to_orig = {}
    # Parameter split is '_' and path punctuation. '-' stays inside one name.
    s = re.sub(r"(\d)\.(\d)", r"\1p\2", s)
    s = re.sub(r"[\/\\_\.\+\(\)\[\]\{\},;]+", " ", s)
    raw = [p for p in s.split() if p]
    out: List[str] = []
    for p in raw:
        pl = p.replace("µ", "u").lower()
        # '=' is one parameter. '-' is one name. Do not split either on letter/digit boundaries.
        if "=" in pl or "-" in pl:
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif number_unit.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif RE_PARAM_TOKEN.match(pl):
            m = RE_PARAM.match(pl)
            # IMG20220601093439 → img + 20220601093439 (not param img=<huge>)
            if m and _param_digit_part_is_datetime_or_date(m.group(2)):
                letter_part, digit_part = m.group(1), m.group(2)
                for piece, orig_piece in ((letter_part, p[: len(letter_part)]), (digit_part, p[len(letter_part) :])):
                    out.append(piece)
                    norm_to_orig.setdefault(piece, orig_piece)
            else:
                out.append(pl)
                norm_to_orig.setdefault(pl, p)
        elif RE_NUM_LETTERS_TOKEN.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif RE_SLM_FLOW_TOKEN.match(pl):
            out.append(pl)
            norm_to_orig.setdefault(pl, p)
        elif re.match(r"^m\d{1,4}$", pl):
            # M + digits (e.g. M10, M14) = measurement ID; keep as one token so it is not split to M + 10
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
        if not tt:
            continue
        if tt in stopwords and tt != "m":
            # Never filter single "m" so M+digits (M10, M14) works when tokenized as ["m","10","0"]
            continue
        norm.append(tt)
    return norm


def tokenize_path(path: Path, root: Path, folder_depth: int, stopwords: Optional[set] = None, unit_map: Optional[Dict[str, str]] = None) -> List[str]:
    folder_tokens, file_tokens, _ = tokenize_path_parts(path, root, folder_depth, stopwords, unit_map=unit_map)
    return folder_tokens + file_tokens


def tokenize_path_parts(
    path: Path, root: Path, folder_depth: int, stopwords: Optional[set] = None,
    unit_map: Optional[Dict[str, str]] = None,
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
            folder_tokens.extend(tokenize_string(f, stopwords, norm_to_orig, unit_map=unit_map))
    stem = Path(filename).stem
    file_tokens = tokenize_string(stem, stopwords, norm_to_orig, unit_map=unit_map)
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


def format_hhmmss(tok: str) -> Optional[str]:
    """If tok is six digits and a plausible clock time, return HH:MM:SS; else None."""
    if not re.fullmatch(r"\d{6}", tok):
        return None
    hh, mm, ss = int(tok[0:2]), int(tok[2:4]), int(tok[4:6])
    if 0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59:
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return None


def _token_looks_like_date(tok: str) -> bool:
    m = (
        RE_DATE_ISO_DASH.match(tok)
        or RE_DATE_ISO.match(tok)
        or RE_DATE_COMPACT.match(tok)
        or RE_DATE_EU.match(tok)
    )
    if not m:
        return False
    y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
    return 1 <= mo <= 12 and 1 <= d <= 31


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


def _apply_user_pattern(
    tok: str, pattern: Dict[str, Any], m: re.Match
) -> Tuple[Optional[str], Optional[Any]]:
    """Given a matched user pattern, return (key, value) for set_field, or (None, None)."""
    key = pattern.get("key")
    extract = pattern.get("extract", "str")
    cg = pattern.get("capture_group") or "n"
    if not key:
        return None, None
    try:
        if extract == "int":
            if cg in m.groupdict():
                return key, int(m.group(cg))
            return None, None
        if extract == "str":
            return key, (m.group(cg) if cg in m.groupdict() else m.group(0))
        if extract == "val_unit":
            val = None
            if "val" in m.groupdict():
                val = parse_number(m.group("val"))
            elif cg in m.groupdict():
                val = parse_number(m.group(cg))
            if val is None:
                return None, None
            unit = pattern.get("unit") or (m.group("unit") if "unit" in m.groupdict() else "")
            return key, {"val": val, "unit": (unit or "").replace("µ", "u")}
        if extract == "date_short_YY" and "a" in m.groupdict() and "b" in m.groupdict() and "c" in m.groupdict():
            a, b, c = int(m.group("a")), int(m.group("b")), int(m.group("c"))
            y, mo, d = 2000 + a, b, c
            if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099:
                return key, f"{y:04d}-{mo:02d}-{d:02d}"
            return None, None
        if extract == "date_short_DM" and "a" in m.groupdict() and "b" in m.groupdict() and "c" in m.groupdict():
            a, b, c = int(m.group("a")), int(m.group("b")), int(m.group("c"))
            d, mo, y = a, b, 2000 + c
            if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099:
                return key, f"{y:04d}-{mo:02d}-{d:02d}"
            return None, None
    except (ValueError, IndexError, KeyError):
        return None, None
    return None, None


def _hyphen_binds_name(tok: str) -> bool:
    """True when '-' joins a label to the rest of one name, not a minus or an exponent."""
    if "-" not in tok:
        return False
    body = tok[1:] if tok.startswith("-") else tok
    body = re.sub(r"e-\d+", "", body, flags=re.IGNORECASE)
    return "-" in body


def _quantitative_from_piece(piece: str, unit_map: Optional[Dict[str, str]] = None) -> Optional[Tuple[str, Any, str]]:
    """Number+unit from the unit list, slm, or gas% in one hyphen segment."""
    hit = match_number_unit(piece, unit_map)
    if hit is not None:
        return hit
    m = RE_SLM_FLOW.match(piece)
    if m:
        val = parse_number(m.group(1))
        if val is not None:
            return "gas_flow", {"val": val, "unit": "slm", "gas": m.group(2)}, "gas_flow"
    m = RE_NUM_LETTERS.match(piece)
    # 22p5 is the decimal 22.5. Do not read the 'p' as a letter suffix (key p5).
    if m and not re.fullmatch(r"\d+p\d+", piece):
        num_part, letters = m.group(1), m.group(2).lower()
        val = parse_number(num_part)
        if val is not None and letters in GAS_KEYS:
            return letters, {"val": int(val) if val == int(val) else val, "unit": "%"}, "gas_pct"
    return None


def _plain_number(v: str) -> Any:
    """Bare number (22, 22p5, 1e-6). Not a number+unit."""
    if not re.fullmatch(r"[-+]?\d+(?:p\d+)?(?:e[-+]?\d+)?", v):
        return None
    sign = -1 if v.startswith("-") else 1
    body = v[1:] if v[:1] in "+-" else v
    n = parse_number(body)
    if n is None:
        return None
    n *= sign
    if n == int(n) and "e" not in v and "p" not in v:
        return int(n)
    return n


def parse_tokens(
    tokens: List[str],
    modality_map: Optional[Dict[str, str]] = None,
    token_patterns: Optional[List[Dict[str, Any]]] = None,
    custom_token_map: Optional[Dict[str, str]] = None,
    only_last_plain_digits_as_frame: bool = False,
    unit_map: Optional[Dict[str, str]] = None,
    processing_tags: Optional[set] = None,
) -> ParseResult:
    modality_map = PREDEFINED_MODALITY if modality_map is None else modality_map
    units = _unit_map_or_default(unit_map)
    tags = set(PREDEFINED_PROCESSING) if processing_tags is None else set(processing_tags)
    data: Dict[str, Any] = {}
    trace: List[str] = []
    token_to_key: Dict[str, str] = {}
    recognized = 0
    total = len(tokens)
    # Precompile user patterns (priority desc); skip invalid regexes
    compiled_patterns: List[Tuple[re.Pattern, Dict[str, Any]]] = []
    for p in sorted(token_patterns or [], key=lambda x: -(x.get("priority") or 0)):
        rx = p.get("regex")
        if not rx or not p.get("key"):
            continue
        try:
            compiled_patterns.append((re.compile(rx), p))
        except re.error:
            continue

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

    n_tokens = len(tokens)
    skip_indices: set[int] = set()
    for idx, tok in enumerate(tokens):
        if not tok or idx in skip_indices:
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
        # Compact camera timestamp: YYYYMMDDHHMMSS → date + time (one token)
        dt14 = parse_compact_datetime(tok)
        if dt14 is not None:
            date_s, time_s = dt14
            if "date" not in data:
                data["date"] = date_s
                trace.append("date:datetime14")
            if "time" not in data:
                data["time"] = time_s
                trace.append("time:datetime14")
            if tok not in token_to_key:
                token_to_key[tok] = "date"
                recognized += 1
            continue
        m = RE_KV.match(tok)
        if m:
            k, v = m.group("k").lower(), m.group("v").lower()
            hit = _quantitative_from_piece(v, units)
            if hit is not None:
                _inferred, val, _why = hit
                set_field(k, val, "kv", tok)
            else:
                num = _plain_number(v)
                set_field(k, num if num is not None else v, "kv", tok)
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
        # Camera cache style: frame_<channel>_<frame> (e.g. frame_004_0000)
        if tok == "frame" and idx + 2 < n_tokens:
            a, b = tokens[idx + 1], tokens[idx + 2]
            if re.fullmatch(r"\d+", a) and re.fullmatch(r"\d+", b):
                set_field("channel", int(a), "frame_pair", a)
                set_field("frame", int(b), "frame_pair", b)
                if tok not in token_to_key:
                    token_to_key[tok] = "frame"
                    recognized += 1
                    trace.append("frame:label")
                skip_indices.add(idx + 1)
                skip_indices.add(idx + 2)
                continue
        m = RE_FRAME.match(tok)
        if m:
            set_field("frame", int(m.group("n")), "frame", tok)
            continue
        m = RE_PARAM.match(tok)
        if m:
            key, val = m.group(1), m.group(2)
            # Defensive: glued IMG20220601093439 if tokenize did not split
            dt_param = parse_compact_datetime(val)
            if dt_param is not None:
                date_s, time_s = dt_param
                if "date" not in data:
                    data["date"] = date_s
                    trace.append("date:datetime14")
                if "time" not in data:
                    data["time"] = time_s
                    trace.append("time:datetime14")
                if tok not in token_to_key:
                    token_to_key[tok] = "date"
                    recognized += 1
                continue
            if key not in data:
                data[key] = int(val)
                trace.append(f"{key}:param")
                recognized += 1
                token_to_key[tok] = key
            continue
        # Plain digits: HHMMSS → time (plausible clock, stronger if next to a date);
        # last filename number stays frame. Otherwise frame/seq as before.
        if re.fullmatch(r"\d+", tok):
            time_str = format_hhmmss(tok)
            as_last_file_frame = only_last_plain_digits_as_frame and idx == n_tokens - 1
            if time_str is not None and not as_last_file_frame:
                # Plausible HHMMSS → time (not frame). Trace notes date adjacency when present.
                near_date = "date" in data or (
                    (idx > 0 and _token_looks_like_date(tokens[idx - 1]))
                    or (idx + 1 < n_tokens and _token_looks_like_date(tokens[idx + 1]))
                )
                why = "time_after_date" if near_date else "time_hhmmss"
                set_field("time", time_str, why, tok)
                continue
            if only_last_plain_digits_as_frame:
                if idx == n_tokens - 1:
                    if "frame" not in data:
                        set_field("frame", int(tok), "frame", tok)
                    continue
                if idx > 0 and tokens[idx - 1].lower() == "m" and "m" not in data:
                    set_field("m", int(tok), "m_after_M", tok)
                    continue
                continue
            if "frame" not in data:
                set_field("frame", int(tok), "frame", tok)
            continue
        m = RE_SEQ.match(tok)
        if m and "seq" not in data:
            set_field("seq", int(m.group("n")), "seq", tok)
            continue
        if tok in modality_map:
            set_field("modality", modality_map[tok], "modality", tok)
            continue
        if tok in tags:
            if "processing" not in data:
                data["processing"] = [tok]
                trace.append("processing:tag")
                recognized += 1
                token_to_key[tok] = "processing"
            elif isinstance(data["processing"], list) and tok not in data["processing"]:
                data["processing"].append(tok)
            continue
        hit = match_number_unit(tok, units) if not _hyphen_binds_name(tok) else None
        if hit is not None:
            key, val, why = hit
            if key == "lengths":
                if "lengths" not in data:
                    data["lengths"] = [val]
                    trace.append("lengths:len")
                    recognized += 1
                    token_to_key[tok] = "lengths"
                elif isinstance(data.get("lengths"), list):
                    data["lengths"].append(val)
            else:
                set_field(key, val, why, tok)
            continue
        m = RE_NUM_LETTERS.match(tok)
        if m and not _hyphen_binds_name(tok) and not re.fullmatch(r"\d+p\d+", tok):
            num_part, letters = m.group(1), m.group(2).lower()
            val = parse_number(num_part)
            if val is not None and letters in GAS_KEYS:
                set_field(letters, {"val": int(val) if val == int(val) else val, "unit": "%"}, "gas_pct", tok)
            continue
        m = RE_SLM_FLOW.match(tok)
        if m and not _hyphen_binds_name(tok):
            val = parse_number(m.group(1))
            gas = m.group(2)  # preserve case (Ar, N2)
            if val is not None:
                set_field("gas_flow", {"val": val, "unit": "slm", "gas": gas}, "gas_flow", tok)
            continue
        # '-' binds one name. Read a number+unit inside it; do not promote the words to keys.
        if "-" in tok:
            hits = [h for h in (_quantitative_from_piece(p, units) for p in tok.split("-") if p) if h]
            if hits:
                linked = False
                for key, val, why in hits:
                    if key == "lengths":
                        if "lengths" not in data:
                            data["lengths"] = [val]
                            trace.append("lengths:len")
                        elif isinstance(data.get("lengths"), list):
                            data["lengths"].append(val)
                    elif key not in data:
                        data[key] = val
                        trace.append(f"{key}:{why}")
                    if not linked:
                        token_to_key[tok] = key
                        recognized += 1
                        linked = True
                continue
        if re.fullmatch(r"(?:exp|experiment)\d{1,4}", tok):
            set_field("experiment", tok.replace("experiment", "exp"), "experiment", tok)
            continue
        if re.fullmatch(r"(?:sample|smp|specimen)[a-z0-9]{1,6}", tok):
            set_field("sample", tok, "sample", tok)
            continue
        # User token_patterns (after built-in, before custom_token_map)
        for rec, pat in compiled_patterns:
            m = rec.match(tok)
            if not m:
                continue
            k, v = _apply_user_pattern(tok, pat, m)
            if k is not None and v is not None and k not in data:
                set_field(k, v, "user_pattern", tok)
                break
        else:
            # custom_token_map: exact token -> key
            if custom_token_map and tok in custom_token_map:
                set_field(custom_token_map[tok], tok, "custom", tok)

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


def apply_majority_frame_logic(rows: List[Dict[str, Any]]) -> None:
    """
    In-place: if most rows have the last numeric token in the filename assigned to key K
    (e.g. 'frame'), reassign the minority that have it as something else (e.g. 'seq') to K.
    So 500 files with 'frame' + 100 with 'seq' at the same position -> all 600 get 'frame'.
    """
    if not rows:
        return
    key_counts: Counter[str] = Counter()
    row_info: List[Tuple[Dict[str, Any], str, str, int]] = []
    for r in rows:
        file_tokens = r.get("_file_tokens") or []
        file_ttk = r.get("_file_token_to_key") or {}
        if not file_tokens:
            continue
        last_tok = file_tokens[-1]
        if not re.fullmatch(r"\d+", last_tok):
            continue
        key = file_ttk.get(last_tok)
        if not key:
            continue
        key_counts[key] += 1
        try:
            val = int(last_tok)
        except ValueError:
            continue
        row_info.append((r, last_tok, key, val))
    if not key_counts:
        return
    majority_key = key_counts.most_common(1)[0][0]
    for r, tok, current_key, val in row_info:
        if current_key == majority_key:
            continue
        if current_key == "m":
            # Last token was assigned to measurement (e.g. ["m","18"] -> m=18). Keep m, add frame with same value (M18_18 -> m=18, frame=18).
            r[majority_key] = val
            ttk = dict(r.get("_file_token_to_key") or {})
            ttk[tok] = majority_key
            r["_file_token_to_key"] = ttk
            continue
        if r.get(current_key) == val:
            del r[current_key]
        r[majority_key] = val
        ttk = dict(r.get("_file_token_to_key") or {})
        ttk[tok] = majority_key
        r["_file_token_to_key"] = ttk


# Keys we never suggest for grouping (internal/metadata)
_ROW_META_KEYS = {"path", "relpath", "ext", "stem", "tokens", "trace", "recognized", "total_tokens", "confidence", "_duplicate_keys", "_folder_tokens", "_file_tokens", "_folder_token_to_key", "_file_token_to_key", "_token_original"}


def suggest_nomenclature(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    From indexed rows, derive detected fields.
    Returns {"detected_fields": [...]}.
    """
    if not rows:
        return {"detected_fields": []}

    all_keys: Dict[str, int] = {}
    for r in rows:
        for k in r.keys():
            if k in _ROW_META_KEYS:
                continue
            all_keys[k] = all_keys.get(k, 0) + 1

    detected_fields = sorted(all_keys.keys(), key=lambda x: (-all_keys[x], x))
    return {"detected_fields": detected_fields}


def _as_plain_number(v: Any) -> Optional[float]:
    """int/float or a number+unit value. None for text, lists, and bools."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if is_quantitative_val(v):
        val = v.get("val")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return None
        return float(val)
    return None


def suggest_categorical_keys(
    rows: List[Dict[str, Any]], threshold: int = 10
) -> Dict[str, bool]:
    """
    Suggest Category (True) or Numeric (False) for WOLKE.

    A key is Numeric only when every value is a number and there are more than
    `threshold` distinct values. Text, and shorter number lists, stay Category.
    """
    if not rows:
        return {}
    distinct: Dict[str, set] = {}
    numeric_only: Dict[str, bool] = {}
    for r in rows:
        for k in r:
            if k in _ROW_META_KEYS:
                continue
            v = r.get(k)
            if v is None:
                continue
            number = _as_plain_number(v)
            numeric_only[k] = numeric_only.get(k, True) and number is not None
            if isinstance(v, (list, dict)) and number is None:
                norm = json.dumps(v, sort_keys=True, default=str)
            else:
                norm = str(v)
            distinct.setdefault(k, set()).add(norm)
    out: Dict[str, bool] = {}
    for k, vals in distinct.items():
        # More than `threshold` distinct numbers → Numeric. Text stays Category.
        # A single repeated value is still Category when the caller keeps the column.
        many_numbers = numeric_only.get(k, False) and len(vals) > threshold
        out[k] = not many_numbers
    return out


_COLUMN_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def normalize_column_key(name: str) -> Optional[str]:
    """Column name for a user-picked path position. None when it cannot be a key."""
    s = name.strip().lower().replace("-", "_")
    s = re.sub(r"\s+", "_", s)
    if not _COLUMN_KEY_RE.fullmatch(s):
        return None
    return s


def _path_sep(relpath: str) -> str:
    return "\\" if "\\" in relpath else "/"


def _folder_and_file(relpath: str) -> Tuple[List[str], str]:
    if not relpath:
        return [], ""
    parts = relpath.split(_path_sep(relpath))
    if not parts:
        return [], ""
    return parts[:-1], parts[-1]


def file_underscore_fields(filename: str) -> List[str]:
    """Filename stem split on `_`. The extension is not a field."""
    if "." in filename:
        stem = filename.rsplit(".", 1)[0]
    else:
        stem = filename
    if stem == "":
        return []
    return stem.split("_")


def slot_span(relpath: str, kind: str, index: int) -> Optional[Tuple[int, int]]:
    """Character span of one folder part or one `_` field in a relative path. None if missing."""
    if index < 0:
        return None
    sep = _path_sep(relpath)
    folders, filename = _folder_and_file(relpath)
    if kind == "folder":
        if index >= len(folders):
            return None
        pos = 0
        for i, part in enumerate(folders):
            if i == index:
                return pos, pos + len(part)
            pos += len(part) + len(sep)
        return None
    if kind != "file":
        return None
    fields = file_underscore_fields(filename)
    if index >= len(fields):
        return None
    pos = sum(len(p) + len(sep) for p in folders)
    for i, field in enumerate(fields):
        if i == index:
            return pos, pos + len(field)
        pos += len(field) + 1
    return None


def slot_at(relpath: str, offset: int) -> Optional[Tuple[str, int]]:
    """Folder part or filename `_` field containing this character. Separators and the extension are None."""
    folders, filename = _folder_and_file(relpath)
    for i in range(len(folders)):
        span = slot_span(relpath, "folder", i)
        if span and span[0] <= offset < span[1]:
            return ("folder", i)
    for i in range(len(file_underscore_fields(filename))):
        span = slot_span(relpath, "file", i)
        if span and span[0] <= offset < span[1]:
            return ("file", i)
    return None


def coerce_slot_value(raw: str) -> Any:
    """Plain number → int/float so Numeric export keeps a number. Anything else stays the path text."""
    num = _plain_number(raw)
    if num is not None:
        return num
    return raw


def apply_slot_keys(rows: List[Dict[str, Any]], slot_keys: Dict[Tuple[str, int], str]) -> None:
    """Write one column per path position. Same `_` field or folder part across every row.

    Does not replace a token that already belongs to a parsed key (for example `frame`).
    """
    if not slot_keys:
        return
    for row in rows:
        rel = str(row.get("relpath") or "")
        for (kind, index), key in slot_keys.items():
            span = slot_span(rel, kind, index)
            if span is None:
                continue
            raw = rel[span[0] : span[1]]
            if raw == "":
                continue
            row[key] = coerce_slot_value(raw)
            if kind == "folder":
                ttk = row.setdefault("_folder_token_to_key", {})
            else:
                ttk = row.setdefault("_file_token_to_key", {})
            if not isinstance(ttk, dict):
                continue
            for tok in tokenize_string(raw):
                if tok not in ttk:
                    ttk[tok] = key


def remove_slot_keys(rows: List[Dict[str, Any]], slot_keys: Dict[Tuple[str, int], str]) -> None:
    """Drop columns previously added by apply_slot_keys."""
    keys = {k for k in slot_keys.values() if k}
    if not keys:
        return
    for row in rows:
        for key in keys:
            row.pop(key, None)
        for name in ("_folder_token_to_key", "_file_token_to_key"):
            ttk = row.get(name)
            if not isinstance(ttk, dict):
                continue
            for tok, key in list(ttk.items()):
                if key in keys:
                    del ttk[tok]


def slot_keys_to_schema(slot_keys: Dict[Tuple[str, int], str]) -> List[Dict[str, Any]]:
    return [
        {"kind": kind, "index": index, "key": key}
        for (kind, index), key in sorted(slot_keys.items(), key=lambda item: (item[0][0], item[0][1], item[1]))
    ]


def slot_keys_from_schema(data: Any) -> Dict[Tuple[str, int], str]:
    out: Dict[Tuple[str, int], str] = {}
    if not isinstance(data, list):
        return out
    for item in data:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        index = item.get("index")
        key = item.get("key")
        if kind in ("folder", "file") and isinstance(index, int) and index >= 0 and isinstance(key, str) and key:
            out[(kind, index)] = key
    return out


def suggest_block_columns(
    rows: List[Dict[str, Any]],
    ignore_keys: Optional[set] = None,
) -> Dict[Tuple[str, int], str]:
    """One column per folder part or filename `_` field that is not already parsed and not constant.

    Constant blocks stay unrecognized (gray). A block the parser already owns
    (`dgm025` → `dgm`, trailing year → `frame`) is left alone.
    `ignore_keys` are columns this function added earlier, so a second pass keeps the same names.
    Names are `folder_1`, `field_3`, counted from 1 in path order.
    """
    ignore = set(ignore_keys or ())
    values: Dict[Tuple[str, int], set] = {}
    owned: Dict[Tuple[str, int], bool] = {}
    for row in rows:
        rel = str(row.get("relpath") or "")
        folders, filename = _folder_and_file(rel)
        specs: List[Tuple[str, int, str, Dict[str, str]]] = []
        folder_ttk = row.get("_folder_token_to_key") or {}
        file_ttk = row.get("_file_token_to_key") or {}
        for index, raw in enumerate(folders):
            specs.append(("folder", index, raw, folder_ttk if isinstance(folder_ttk, dict) else {}))
        for index, raw in enumerate(file_underscore_fields(filename)):
            specs.append(("file", index, raw, file_ttk if isinstance(file_ttk, dict) else {}))
        for kind, index, raw, ttk in specs:
            if raw == "":
                continue
            slot = (kind, index)
            values.setdefault(slot, set()).add(raw)
            tokens = tokenize_string(raw)
            is_owned = bool(tokens) and all(
                ttk.get(tok) is not None and ttk.get(tok) not in ignore for tok in tokens
            )
            owned[slot] = owned.get(slot, True) and is_owned
    occupied = {
        k
        for row in rows
        for k in row
        if isinstance(k, str) and k not in _ROW_META_KEYS and not k.startswith("_") and k not in ignore
    }
    out: Dict[Tuple[str, int], str] = {}
    for slot in sorted(values, key=lambda item: (0 if item[0] == "folder" else 1, item[1])):
        if owned.get(slot, False):
            continue
        if len(values[slot]) <= 1:
            continue
        kind, index = slot
        base = f"folder_{index + 1}" if kind == "folder" else f"field_{index + 1}"
        name = base
        n = 2
        while name in occupied or name in out.values():
            name = f"{base}_{n}"
            n += 1
        out[slot] = name
        occupied.add(name)
    return out


# Min. files to use multicore (below: process spawn overhead > gain)
_PARALLEL_THRESHOLD = 100


def _index_single_file(args: Tuple) -> Dict[str, Any]:
    """Worker for ProcessPoolExecutor: index one file. Top-level for picklability."""
    (
        p, root, folder_depth, stopwords, modality_map, token_patterns, custom_token_map,
        unit_map, processing_tags,
    ) = args
    folder_tokens, file_tokens, norm_to_orig = tokenize_path_parts(
        p, root, folder_depth, stopwords=stopwords, unit_map=unit_map,
    )
    tokens = folder_tokens + file_tokens
    pr_folder = parse_tokens(
        folder_tokens,
        modality_map=modality_map,
        token_patterns=token_patterns,
        custom_token_map=custom_token_map,
        unit_map=unit_map,
        processing_tags=processing_tags,
    )
    pr_file = parse_tokens(
        file_tokens,
        modality_map=modality_map,
        token_patterns=token_patterns,
        custom_token_map=custom_token_map,
        only_last_plain_digits_as_frame=True,
        unit_map=unit_map,
        processing_tags=processing_tags,
    )
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
    # Confidence / recognized counts use the filename only so deep folder trees
    # (Project…/cache/…) do not dilute the score. Folder keys still populate the row.
    n_file = len(file_tokens)
    row["recognized"] = pr_file.recognized
    row["total_tokens"] = n_file
    row["confidence"] = round(
        (1.0 - math.exp(-3.0 * pr_file.recognized / max(1, n_file))), 4
    )
    return row


def run_indexer(
    root_dir: str | Path,
    output_dir: str | Path,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """
    Run full index pipeline. Config can override:
    allowed_suffixes (set or list), folder_token_depth (int),
    recursive (bool), include_hidden (bool), stopwords (set or list), modality_map (dict),
    parallel_threshold (int, default 100: min files to use multicore),
    parallel_max_workers (int, default cpu_count-1),
    log_callback (callable[str] for timing/log messages).
    output_dir is accepted for existing callers and ignored. Crawl only reads
    root_dir; it does not create or write the output folder. Export creates
    that folder when it writes JSONL/CSV.
    Returns (rows, {}). Second value is empty dict for backward compatibility.
    """
    _ = output_dir  # callers still pass it; crawl must not create the folder
    cfg = config or {}
    root = Path(root_dir).expanduser().resolve()

    allowed = cfg.get("allowed_suffixes")
    if allowed is not None and not isinstance(allowed, set):
        allowed = set(allowed)
    allowed = allowed or DEFAULT_ALLOWED_SUFFIXES

    recursive = cfg.get("recursive", True)
    include_hidden = cfg.get("include_hidden", False)

    folder_depth = cfg.get("folder_token_depth", 99)

    stopwords = cfg.get("stopwords")
    if stopwords is not None and not isinstance(stopwords, set):
        stopwords = set(stopwords)
    stopwords = stopwords or DEFAULT_STOPWORDS
    if "modality_map" in cfg and cfg.get("modality_map") is not None:
        modality_map = dict(cfg["modality_map"])
    else:
        modality_map = dict(PREDEFINED_MODALITY)
    if "unit_map" in cfg and cfg.get("unit_map") is not None:
        unit_map = {str(k).lower(): str(v).strip().lower() for k, v in dict(cfg["unit_map"]).items()}
    else:
        unit_map = dict(PREDEFINED_UNITS)
    if "processing_tags" in cfg and cfg.get("processing_tags") is not None:
        processing_tags = {str(t).strip().lower() for t in cfg["processing_tags"] if str(t).strip()}
    else:
        processing_tags = set(PREDEFINED_PROCESSING)
    token_patterns = list(cfg.get("token_patterns") or [])
    custom_token_map = dict(cfg.get("custom_token_map") or {})
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
    unit_map_copy = dict(unit_map)
    processing_frozen = frozenset(processing_tags)

    parallel_threshold = cfg.get("parallel_threshold", _PARALLEL_THRESHOLD)
    max_workers = cfg.get("parallel_max_workers")
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 1) - 1)

    use_parallel = len(file_list) >= parallel_threshold and max_workers > 1
    _log(f"[{t1 - t0:.3f}s] index: {'parallel' if use_parallel else 'sequential'} (workers={max_workers})")

    t2 = time.perf_counter()
    if use_parallel:
        args_list = [
            (p, root, folder_depth, stopwords_frozen, modality_map_copy, token_patterns, custom_token_map, unit_map_copy, processing_frozen)
            for p in file_list
        ]
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            rows = list(ex.map(_index_single_file, args_list))
    else:
        rows = [
            _index_single_file((p, root, folder_depth, stopwords_frozen, modality_map_copy, token_patterns, custom_token_map, unit_map_copy, processing_frozen))
            for p in file_list
        ]
    t3 = time.perf_counter()
    _log(f"[{t3 - t0:.3f}s] index done: {t3 - t2:.3f}s for {len(rows)} files ({len(rows) / max(0.001, t3 - t2):.0f} files/s)")

    apply_majority_frame_logic(rows)

    _log(f"[{time.perf_counter() - t0:.3f}s] total")
    return rows, {}


def write_jsonl(
    rows: List[Dict[str, Any]],
    out_path: Path,
    used_keys: List[str] | None = None,
    column_si_scale: Dict[str, int] | None = None,
) -> None:
    """Export JSONL: numeric values; when column_si_scale.get(k)==0 convert to SI."""
    from dampf.key_lut import get_export_value_and_metadata
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
    """Export CSV: numeric values; when column_si_scale.get(k)==0 convert to SI."""
    from dampf.key_lut import get_export_value_and_metadata
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
    """Column -> {unit, raw_unit}. When si_scale=0: unit=SI base, raw_unit=original."""
    from dampf.key_lut import SI_BASE_UNIT, get_export_value_and_metadata
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
    """Write column_metadata as index_meta.json (unit, raw_unit per column)."""
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
