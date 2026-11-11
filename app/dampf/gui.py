# gui.py - DAMPF GUI (PyQt6): responsive, 800px max, fits Full HD, INI settings.

from __future__ import annotations

import json
import queue
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from dampf.indexer import (
    DEFAULT_ALLOWED_SUFFIXES,
    run_indexer,
    suggest_nomenclature,
    suggest_categorical_keys,
    build_column_metadata,
    write_csv,
    write_index_meta,
    write_jsonl,
)
from dampf.db_writer import default_db_path_for_root, write_index_to_sqlite, load_schema_from_db
from dampf.outlier_detection import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    detect_schema_outliers,
    detect_typo_candidates,
)
from dampf.key_lut import (
    build_key_tree,
    exponent_to_unit,
    format_val_unit,
    get_category,
    get_display_name,
    get_display_value,
    get_unit_info,
    is_quantitative_val,
    SI_BASE_UNIT,
    unit_to_exponent,
)
from dampf.app_settings import load_settings, save_settings

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QTextBlockFormat, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox,
    QComboBox, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, QTextEdit, QPlainTextEdit,
    QSplitter, QScrollArea, QFrame, QSizePolicy, QInputDialog, QMessageBox,
    QFileDialog, QProgressDialog, QMenu,
)

# At least 20 distinct colors – no duplicates for different parameters
_KEY_COLORS_LIGHT = [
    "#b3d9ff", "#c8e6c9", "#fff9c4", "#e1bee7", "#ffcdd2", "#b2ebf2", "#d7ccc8", "#cfd8dc",
    "#ffccbc", "#d1c4e9", "#b2dfdb", "#ffecb3", "#c5e1a5", "#f8bbd0", "#b3e5fc", "#dcedc8",
    "#f0f4c3", "#ffab91", "#b39ddb",
]
_KEY_COLORS_DARK = [
    "#4a90d9", "#2e7d32", "#f9a825", "#7b1fa2", "#c62828", "#00838f", "#795548", "#546e7a",
    "#d84315", "#5e35b1", "#00695c", "#f57f17", "#558b2f", "#ad1457", "#0277bd", "#7cb342",
    "#afb42b", "#e64a19", "#4527a0",
]

STYLESHEET_LIGHT = """
    QWidget { background-color: #e8eaed; color: #202124; }
    QGroupBox { font-weight: bold; }
    QLineEdit, QTextEdit, QComboBox, QSpinBox { background-color: #ffffff; color: #202124; border: 1px solid #dadce0; }
    QTreeWidget { background-color: #ffffff; color: #202124; }
    QFrame#workflow_header { background-color: #f5f5f5; border-radius: 4px; }
    QLabel#drag_drop_hint { color: #1976d2; font-size: 11px; }
    QGroupBox#root_folder_g { border: 2px dashed #90caf9; border-radius: 4px; padding: 8px; }
"""
STYLESHEET_DARK = """
    QWidget { background-color: #2d323b; color: #e6edf3; }
    QGroupBox { font-weight: bold; }
    QLineEdit, QTextEdit, QComboBox, QSpinBox { background-color: #1e2127; color: #e6edf3; border: 1px solid #444c56; }
    QTreeWidget { background-color: #1e2127; color: #e6edf3; }
    QFrame#workflow_header { background-color: #252a33; border-radius: 4px; }
    QLabel#drag_drop_hint { color: #64b5f6; font-size: 11px; }
    QGroupBox#root_folder_g { border: 2px dashed #1976d2; border-radius: 4px; padding: 8px; }
"""


def _row_folder(r: dict) -> str:
    """Folder path for row (dirname of relpath)."""
    rel = r.get("relpath", "")
    folder = str(Path(rel).parent).replace("\\", "/") if rel else ""
    return folder if folder != "." else ""


def _build_folder_tree(rows: list) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Build per-folder counts and per-folder per-extension counts. path uses /.
    Returns (by_folder, by_folder_ext) with by_folder_ext[path][ext] = count."""
    by_folder: dict[str, int] = {}
    by_folder_ext: dict[str, dict[str, int]] = {}
    for r in rows:
        rel = r.get("relpath", "")
        folder = str(Path(rel).parent).replace("\\", "/") if rel else ""
        if folder == ".":
            folder = ""
        ext = r.get("ext") or ""
        if ext and not ext.startswith("."):
            ext = "." + ext
        by_folder[folder] = by_folder.get(folder, 0) + 1
        if folder not in by_folder_ext:
            by_folder_ext[folder] = {}
        by_folder_ext[folder][ext] = by_folder_ext[folder].get(ext, 0) + 1
    return by_folder, by_folder_ext


def filter_rows_by_folder_includes(rows: list, included: set[str] | None) -> list:
    """Filter rows by included folder paths.

    None = no folder filter (all rows). Empty set = nothing selected.
    Non-empty = row folder equals an included path or is under one.
    """
    if included is None:
        return list(rows)
    if not included:
        return []
    out = []
    for r in rows:
        folder = str(Path(r.get("relpath", "")).parent).replace("\\", "/") if r.get("relpath") else ""
        if folder == ".":
            folder = ""
        if any(folder == p or folder.startswith(p + "/") for p in included):
            out.append(r)
    return out


_ROW_META_KEYS = frozenset(
    {"path", "relpath", "ext", "stem", "tokens", "trace", "recognized", "total_tokens",
     "confidence", "_duplicate_keys", "_folder_tokens", "_file_tokens", "_folder_token_to_key", "_file_token_to_key"}
)


def _key_stats(rows: list, keys: list) -> dict:
    """Per key: uniques, numeric -> min/max/mean, else None. Returns {key: {"uniques": N, "min": x, "max": y, "mean": z}}."""
    import json as _json
    stats: dict = {}
    for k in keys:
        vals: list = []
        nums: list = []
        for r in rows:
            v = r.get(k)
            if v is None:
                continue
            if is_quantitative_val(v):
                vn = format_val_unit(v)
                nums.append(float(v.get("val", 0)))
            elif isinstance(v, list) and v and is_quantitative_val(v[0]):
                # lengths etc.: list of val+unit -> all values for min/max/mean
                vn = ", ".join(format_val_unit(x) for x in v[:5])
                if len(v) > 5:
                    vn += " ..."
                for entry in v:
                    if is_quantitative_val(entry):
                        nums.append(float(entry.get("val", 0)))
            elif isinstance(v, (list, dict)):
                vn = _json.dumps(v, sort_keys=True, default=str)
            else:
                vn = str(v)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    nums.append(float(v))
            vals.append(vn)
        mn = min(nums) if nums else None
        mx = max(nums) if nums else None
        mean = (sum(nums) / len(nums)) if nums else None
        stats[k] = {"uniques": len(set(vals)), "min": mn, "max": mx, "mean": mean}
    return stats


def _schema_consistency(rows: list, keys: list) -> tuple[int, dict[str, int]]:
    """Count rows per key. Returns (total_rows, {key: count_with_key})."""
    if not rows:
        return 0, {}
    total = len(rows)
    per_key: dict[str, int] = {}
    for r in rows:
        for k in keys:
            if r.get(k) is not None:
                per_key[k] = per_key.get(k, 0) + 1
    return total, per_key


def _fmt_count(n: int) -> str:
    """Format integer counts for UI (apostrophe thousands, period unused here)."""
    return f"{n:,}".replace(",", "'")


def _build_pseudopath_from_rows(
    rows: list,
    root_dir: str | None,
    legend_order: list,
    sep: str,
    key_to_color: dict,
    neutral_color: str,
    unrec_color: str,
) -> str:
    """Build one pseudo-path from actual paths: key names, (key) where key is not in all paths. Return HTML."""
    if not rows or not legend_order:
        return ""
    keys_ordered = [k for k in legend_order if k not in ("filetype", "separator", "rest")]
    if not keys_ordered:
        return ""

    rows_with_key: dict[str, int] = {}
    rows_with_key_in_folder: dict[str, int] = {}
    rows_with_key_in_file: dict[str, int] = {}
    folder_positions: dict[str, list[float]] = {}
    file_positions: dict[str, list[float]] = {}
    file_has_space_before: dict[str, bool] = {}

    for r in rows:
        _, folder_str, file_str, folder_seg, file_seg, _ = _build_path_segments(r, root_dir)
        folder_len = max(1, len(folder_str))
        file_len = max(1, len(file_str))
        keys_in_row = set()
        for _s, _e, k in folder_seg:
            keys_in_row.add(k)
            rows_with_key_in_folder[k] = rows_with_key_in_folder.get(k, 0) + 1
            folder_positions.setdefault(k, []).append(_s / folder_len)
        for _s, _e, k in file_seg:
            keys_in_row.add(k)
            rows_with_key_in_file[k] = rows_with_key_in_file.get(k, 0) + 1
            file_positions.setdefault(k, []).append(_s / file_len)
            if _s > 0 and file_str[_s - 1 : _s].isspace():
                file_has_space_before[k] = True
        for k in keys_in_row:
            rows_with_key[k] = rows_with_key.get(k, 0) + 1

    keys_in_folder = set(folder_positions.keys())
    keys_in_file = set(file_positions.keys())
    order_idx = {k: i for i, k in enumerate(keys_ordered)}
    folder_key_order = sorted(
        keys_in_folder,
        key=lambda k: (sum(folder_positions[k]) / len(folder_positions[k]), order_idx.get(k, 999), k),
    )
    file_key_order = sorted(
        keys_in_file,
        key=lambda k: (sum(file_positions[k]) / len(file_positions[k]), order_idx.get(k, 999), k),
    )

    n_rows = len(rows)
    def label(key: str, in_folder: bool) -> str:
        count_here = rows_with_key_in_folder.get(key, 0) if in_folder else rows_with_key_in_file.get(key, 0)
        return f"({key})" if count_here < n_rows else key

    segs: list[tuple[str, str | None]] = []
    for i, k in enumerate(folder_key_order):
        if i > 0:
            segs.append(("_", None))
        segs.append((label(k, True), k))
    if folder_key_order:
        segs.append((sep, None))
    for i, k in enumerate(file_key_order):
        if i > 0:
            segs.append((" " if file_has_space_before.get(k) else "_", None))
        segs.append((label(k, False), k))
    segs.append((".filetype", None))

    out = []
    for text, key in segs:
        if key is None or key == "filetype":
            out.append(f'<span style="background-color:{neutral_color}; padding:0 1px;">{text}</span>')
        else:
            c = key_to_color.get(key, unrec_color)
            out.append(f'<span style="background-color:{c}; padding:0 1px;">{text}</span>')
    return "".join(out)


def _compute_legend_key_order(rows: list, detected_keys: list, root_dir: str | None) -> list:
    """Stable order by rightmost position in path (left-to-right). Position only, no value logic."""
    if not rows or not detected_keys:
        return list(detected_keys)
    sep = "\\" if any("\\" in str(r.get("relpath", "")) for r in rows) else "/"
    sample_size = 500
    use_rows = rows if len(rows) <= sample_size else [rows[i * len(rows) // sample_size] for i in range(sample_size)]
    def keys_in_row(r):
        all_ttk = {**(r.get("_folder_token_to_key") or {}), **(r.get("_file_token_to_key") or {})}
        return set(all_ttk.values())
    max_keys = max(len(keys_in_row(r)) for r in use_rows) if use_rows else 0
    use_for_order = [r for r in use_rows if len(keys_in_row(r)) >= max_keys] if max_keys else use_rows
    key_positions: dict[str, list[float]] = {}
    for r in use_for_order:
        rel = r.get("relpath", "")
        if not rel:
            _, folder_str, file_str, _, _, _ = _build_path_segments(r, root_dir)
            rel = (folder_str + sep + file_str) if folder_str else file_str
        rel = rel.replace("/", sep).replace("\\", sep)
        line_len = max(1, len(rel))
        all_ttk = {**(r.get("_folder_token_to_key") or {}), **(r.get("_file_token_to_key") or {})}
        for token, key in all_ttk.items():
            for m in re.finditer(re.escape(token), rel, re.IGNORECASE):
                key_positions.setdefault(key, []).append(m.end() / line_len)
    order = sorted(key_positions.keys(), key=lambda k: (max(key_positions[k]), k))
    return order + [k for k in detected_keys if k not in order]


def _key_order_for_colors(detected_keys: list, all_keys: set) -> list:
    """Stable order: detected_keys first (filename order), then extras sorted."""
    order = [k for k in detected_keys if k in all_keys]
    order += sorted(k for k in all_keys if k not in detected_keys)
    return order


def _gaps_from_segments(segs: list, line_len: int) -> list[tuple[int, int]]:
    """Return (start, end) ranges not covered by segs. segs = [(start, end, key, in_folder), ...]."""
    if not segs:
        return [(0, line_len)] if line_len > 0 else []
    sorted_segs = sorted(segs, key=lambda x: (x[0], x[1]))
    gaps = []
    prev_end = 0
    for start, end, *_ in sorted_segs:
        if start > prev_end:
            gaps.append((prev_end, start))
        prev_end = max(prev_end, end)
    if prev_end < line_len:
        gaps.append((prev_end, line_len))
    return gaps


def _split_gap_into_segment_types(line: str, gap_start: int, gap_end: int) -> list[tuple[int, int, str]]:
    """Split gap into (start, end, type) where type is 'filetype', 'separator', 'rest'.
    filetype: extension at end of line. separator: runs of -, _, /, \\. rest: everything else (grey).
    """
    text = line[gap_start:gap_end]
    line_len = len(line)
    result: list[tuple[int, int, str]] = []

    # filetype: only if gap reaches end of line and ends with .ext
    if gap_end == line_len:
        ext_match = re.search(r"(\.[a-zA-Z0-9]+)$", text)
        if ext_match:
            ext_start = gap_start + ext_match.start(1)
            if ext_match.start(1) > 0:
                result.extend(_split_gap_into_segment_types(line, gap_start, ext_start))
            result.append((ext_start, gap_end, "filetype"))
            return result

    # Split into separator runs and rest (separators: - _ / \ space)
    sep_pat = r"[-_/\\\s]+"
    i = 0
    while i < len(text):
        m = re.match(sep_pat, text[i:])
        if m:
            run_len = len(m.group())
            result.append((gap_start + i, gap_start + i + run_len, "separator"))
            i += run_len
        else:
            m_next = re.search(sep_pat, text[i:])
            if m_next:
                j = i + m_next.start()
                result.append((gap_start + i, gap_start + j, "rest"))
                i = j
            else:
                result.append((gap_start + i, gap_end, "rest"))
                break
    return result


def _apply_custom_token_map(rows: list, custom_token_map: dict) -> None:
    """In-place: add custom_token_map entries to row data and token_to_key."""
    if not custom_token_map:
        return
    for row in rows:
        folder_ttk = row.get("_folder_token_to_key") or {}
        file_ttk = row.get("_file_token_to_key") or {}
        folder_tokens = row.get("_folder_tokens") or []
        file_tokens = row.get("_file_tokens") or []
        for tok in folder_tokens:
            if tok not in folder_ttk and tok in custom_token_map:
                key = custom_token_map[tok]
                row[key] = tok
                folder_ttk[tok] = key
        for tok in file_tokens:
            if tok not in file_ttk and tok in custom_token_map:
                key = custom_token_map[tok]
                row[key] = tok
                file_ttk[tok] = key
        row["_folder_token_to_key"] = folder_ttk
        row["_file_token_to_key"] = file_ttk


def _token_to_pattern(mapped_token: str) -> str | None:
    """Generate regex pattern from mapped token to match similar tokens. Returns None if no pattern."""
    t = mapped_token.lower().strip()
    if not t:
        return None
    # All digits: 00000 -> ^\d{5}$
    if re.fullmatch(r"\d+", t):
        return f"^\\d{{{len(t)}}}$"
    # Letters + digits: c1, gain150 -> ^c\d+$, ^gain\d+$
    m = re.match(r"^([a-z]+)(\d+)$", t)
    if m:
        return f"^{re.escape(m.group(1))}\\d+$"
    # Digits + letters: 5slmar -> ^\d+slmar$
    m = re.match(r"^(\d+)([a-z][a-z0-9]*)$", t)
    if m:
        return f"^\\d+{re.escape(m.group(2))}$"
    # Letters only, len>=4: synck, syncaa -> ^sync[a-z]*$
    if len(t) >= 4 and t.isalpha():
        return f"^{re.escape(t[:4])}[a-z]*$"
    # Letters only, len 2-3: ff, sf -> exact only, no pattern (too broad)
    return None


def suggest_key_for_token(token: str, custom_token_map: dict) -> str | None:
    """Suggest key for unrecognized token based on custom_token_map patterns. Returns first match."""
    if not token or not custom_token_map:
        return None
    t = token.lower().strip()
    for mapped_tok, key in custom_token_map.items():
        pat = _token_to_pattern(mapped_tok)
        if pat and re.fullmatch(pat, t):
            return key
    return None


def get_batch_suggestions(
    unrec_tokens: list[tuple[str, int]], custom_token_map: dict
) -> list[tuple[str, str]]:
    """Return [(token, suggested_key), ...] for tokens that have a suggestion."""
    out: list[tuple[str, str]] = []
    for tok, _cnt in unrec_tokens:
        key = suggest_key_for_token(tok, custom_token_map)
        if key:
            out.append((tok, key))
    return out


def _collect_unrecognized_tokens(rows: list) -> list[tuple[str, int]]:
    """Return [(token, count), ...] for tokens not in token_to_key, sorted by count desc."""
    counts: Counter[str] = Counter()
    for row in rows:
        folder_ttk = row.get("_folder_token_to_key") or {}
        file_ttk = row.get("_file_token_to_key") or {}
        for tok in row.get("_folder_tokens") or []:
            if tok not in folder_ttk:
                counts[tok] += 1
        for tok in row.get("_file_tokens") or []:
            if tok not in file_ttk:
                counts[tok] += 1
    return counts.most_common()


def _build_path_segments(row: dict, root_dir: str | None = None):
    path = row.get("path", "")
    if not path:
        return "", "", "", [], [], []
    path_obj = Path(path).resolve()
    sep = "\\" if "\\" in path else "/"
    parts = path.split(sep)
    folder_to_key = row.get("_folder_token_to_key") or {}
    file_to_key = row.get("_file_token_to_key") or {}
    if root_dir and str(path_obj).startswith(str(Path(root_dir).resolve())):
        try:
            rel = path_obj.relative_to(Path(root_dir).resolve())
            rel_parts = rel.parts
            root_str = str(Path(root_dir).resolve())
            folder_str = sep.join(rel_parts[:-1]) if len(rel_parts) > 1 else ""
            file_str = rel_parts[-1] if rel_parts else ""
        except ValueError:
            root_str = ""
            folder_str = sep.join(parts[:-1]) if len(parts) > 1 else ""
            file_str = parts[-1] if parts else ""
    else:
        root_str = ""
        folder_str = sep.join(parts[:-1]) if len(parts) > 1 else ""
        file_str = parts[-1] if parts else ""
    folder_seg, file_seg = [], []
    keys_in_folder, keys_in_file = set(), set()

    def segments_from_tokens_in_order(text: str, tokens: list, token_to_key: dict, keys_out: set):
        """Match tokens in order so duplicate tokens (e.g. 14_14) get correct key each time."""
        segs = []
        pos = 0
        for token in tokens:
            key = token_to_key.get(token)
            if key is None:
                continue
            m = re.search(re.escape(token), text[pos:], re.IGNORECASE)
            if m:
                start = pos + m.start()
                end = pos + m.end()
                segs.append((start, end, key))
                keys_out.add(key)
                pos = end
        return segs

    folder_tokens = row.get("_folder_tokens") or []
    file_tokens = row.get("_file_tokens") or []
    folder_seg = segments_from_tokens_in_order(folder_str, folder_tokens, folder_to_key, keys_in_folder)
    file_seg = segments_from_tokens_in_order(file_str, file_tokens, file_to_key, keys_in_file)
    keys_dup = sorted(keys_in_folder & keys_in_file)
    return root_str, folder_str, file_str, folder_seg, file_seg, keys_dup


def _run_indexer_worker(
    root_dir: str,
    output_dir: str,
    config: dict,
    result_queue: queue.Queue,
    log_queue: queue.Queue | None = None,
) -> None:
    try:
        if log_queue is not None:
            config = dict(config)
            config["log_callback"] = lambda msg: log_queue.put(msg)
        rows, groups = run_indexer(root_dir, output_dir, config)
        result_queue.put(("ok", (rows, groups)))
    except Exception as e:
        result_queue.put(("err", str(e)))


def _icon_path() -> Path:
    """Path to icon/icon.ico (works when run from repo or from frozen exe)."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        # Repo root is two levels above app/dampf/gui.py
        base = Path(__file__).resolve().parents[2]
    return base / "icon" / "icon.ico"


class DampfGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DAMPF — Data Aggregation & Modular Processing Framework")
        p = _icon_path()
        if p.exists():
            self.setWindowIcon(QIcon(str(p)))
        settings = load_settings()
        # Default 800x1000 for laptop/Full HD; saved size from INI is used when present
        self.resize(settings["width"], settings["height"])
        self.setMinimumSize(640, 600)

        self.root_dir = settings.get("root_dir", "")
        self.output_dir = settings.get("output_dir", "")
        self.db_path = settings.get("db_path", "")
        self.folder_depth = 99
        self.recursive = True
        self.include_hidden = False

        self.rows: list = []
        self._all_rows: list = []  # all crawled files (all types)
        self._ext_filter: str | None = None  # None = all, ".tif" = only tif
        self._folder_includes: set[str] | None = None  # None = all; empty set = none; else selected paths
        self._folder_check_updating = False
        self.current_config: dict = {}
        self.key_display_names: dict = {}
        self.key_categories: dict = {}
        self.key_is_categorical: dict = {}
        self.key_si_scale: dict = {}
        self.key_is_used: dict = {}
        self._suggested_categorical: dict = {}
        self._last_detected_keys: list = []
        self._crawl_queue: queue.Queue | None = None
        self._crawl_done = True
        self._folder_tree_ready = False
        self._effective_rows: list = []
        self._last_sample_rows: list = []
        self._legend_key_order: list = []
        self.custom_token_map: dict[str, str] = {}
        self.token_patterns: list[dict] = []
        self._refreshing_unrec_panel = False

        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setSpacing(6)
        main.setContentsMargins(8, 8, 8, 8)

        # Top section (1-3): root, crawl, include folders (collapsible)
        top_section = QWidget()
        top_section.setMinimumHeight(40)
        self._top_section = top_section
        top_section_l = QVBoxLayout(top_section)
        top_section_l.setSpacing(3)
        top_section_l.setContentsMargins(0, 0, 0, 0)
        self._top_section_content = QWidget()
        top_content_l = QVBoxLayout(self._top_section_content)
        top_content_l.setContentsMargins(0, 0, 0, 0)
        top_content_l.setSpacing(3)

        # Root (compact: one row)
        root_g = QGroupBox("1. Root Folder")
        root_g.setObjectName("root_folder_g")
        root_g.setToolTip("Folder containing your files. Drag & drop a folder here or use Browse. DAMPF scans filenames and paths for parameters.")
        root_l = QHBoxLayout(root_g)
        root_l.setSpacing(6)
        self.root_edit = QLineEdit()
        self.root_edit.setObjectName("root_edit")
        self.root_edit.setPlaceholderText("Select or drop folder")
        self.root_edit.setText(self.root_dir)
        self.root_edit.setMinimumWidth(140)
        self.root_edit.setToolTip("Path to data folder. You can also drag and drop a folder here.")
        root_l.addWidget(self.root_edit)
        browse_root_btn = QPushButton("Browse...", clicked=self._browse_root)
        browse_root_btn.setToolTip("Select root folder in file dialog.")
        root_l.addWidget(browse_root_btn)
        self.light_mode_cb = QCheckBox("Light mode")
        self.light_mode_cb.setToolTip("Light theme when checked, dark theme when unchecked.")
        self.light_mode_cb.setChecked(settings.get("light_mode", False))
        self.light_mode_cb.toggled.connect(self._apply_theme)
        root_l.addWidget(self.light_mode_cb)
        self.advanced_check = QCheckBox("Show output & DB")
        self.advanced_check.setToolTip("Show Output folder and Database path (for export and SQLite).")
        self.advanced_check.toggled.connect(self._toggle_advanced)
        root_l.addWidget(self.advanced_check)
        top_content_l.addWidget(root_g)

        # Advanced (hidden by default)
        self.advanced_w = QWidget()
        adv_l = QGridLayout(self.advanced_w)
        adv_l.addWidget(QLabel("Output:"), 0, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setText(self.output_dir)
        self.output_edit.setToolTip("Folder for index.jsonl, index.csv. Default: root/_index")
        adv_l.addWidget(self.output_edit, 0, 1)
        browse_out_btn = QPushButton("Browse", clicked=self._browse_output)
        browse_out_btn.setToolTip("Select output folder for export files.")
        adv_l.addWidget(browse_out_btn, 0, 2)
        adv_l.addWidget(QLabel("Database:"), 1, 0)
        self.db_edit = QLineEdit()
        self.db_edit.setText(self.db_path)
        self.db_edit.setToolTip("SQLite database file path. Default: root/<root_folder_name>.db")
        adv_l.addWidget(self.db_edit, 1, 1)
        browse_db_btn = QPushButton("Browse", clicked=self._browse_db)
        browse_db_btn.setToolTip("Choose where to save the SQLite database.")
        adv_l.addWidget(browse_db_btn, 1, 2)
        top_content_l.addWidget(self.advanced_w)
        self.advanced_w.hide()

        # Crawl (one row: button, progress, checkboxes, depth spinner; then group keys with explanation)
        crawl_g = QGroupBox("2. Crawl")
        crawl_g.setToolTip("Scan folder, extract parameters from filenames (e.g. 4kV, 10us, run1).")
        crawl_l = QVBoxLayout(crawl_g)
        crawl_l.setSpacing(4)
        row1 = QHBoxLayout()
        self.crawl_btn = QPushButton("Start Crawl", clicked=self._start_crawl)
        self.crawl_btn.setToolTip("Scan root folder and detect parameters in paths/filenames.")
        self.progress_label = QLabel("")
        row1.addWidget(self.crawl_btn)
        row1.addWidget(self.progress_label)
        row1.addWidget(QLabel(" "))
        self.recursive_cb = QCheckBox("Recursive")
        self.recursive_cb.setChecked(True)
        self.recursive_cb.setToolTip("Scan subfolders. Uncheck to index only root folder.")
        self.include_hidden_cb = QCheckBox("Include hidden")
        self.include_hidden_cb.setToolTip("Include files/folders with hidden attribute.")
        row1.addWidget(self.recursive_cb)
        row1.addWidget(self.include_hidden_cb)
        depth_label = QLabel("Depth:")
        depth_label.setToolTip("Max folder depth for tokenization. 0=root only, 99=all levels.")
        row1.addWidget(depth_label)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 99)
        self.depth_spin.setValue(99)
        self.depth_spin.setToolTip("Max folder depth for parameter extraction. 99 = no limit.")
        row1.addWidget(self.depth_spin)
        row1.addStretch()
        crawl_l.addLayout(row1)
        top_content_l.addWidget(crawl_g)
        ext_filter_row = QHBoxLayout()
        ext_filter_lbl = QLabel("Filter by type:")
        ext_filter_lbl.setToolTip(
            "Crawl indexes every allowed type. This view defaults to the most common type so sidecars "
            "do not flood step 4; click another button (e.g. .img) or All to switch. No re-crawl."
        )
        ext_filter_row.addWidget(ext_filter_lbl)
        self.ext_filter_buttons_w = QWidget()
        self.ext_filter_buttons_l = QHBoxLayout(self.ext_filter_buttons_w)
        self.ext_filter_buttons_l.setContentsMargins(0, 0, 0, 0)
        self.ext_filter_buttons_l.setSpacing(4)
        ext_filter_row.addWidget(self.ext_filter_buttons_w)
        ext_filter_row.addStretch()
        crawl_l.addLayout(ext_filter_row)

        # Folder inclusion tree (after crawl)
        self.folder_tree_g = QGroupBox("3. Include folders (uncheck to exclude, changes apply immediately)")
        self.folder_tree_g.setToolTip("After crawl: choose which folders to include. Unchecked = excluded from index.")
        self.folder_tree_g.setMinimumHeight(250)  # Tree + gap + buttons: scrollbar and list never overlap
        folder_tree_l = QVBoxLayout(self.folder_tree_g)
        folder_tree_l.setSpacing(2)
        folder_tree_l.setContentsMargins(4, 8, 4, 4)
        self.folder_tree_w = QTreeWidget()
        self.folder_tree_w.setHeaderLabels(["Idx", "Include", "Folder", "Files"])
        self.folder_tree_w.setToolTip("Uncheck folders to exclude from index (e.g. RESULTS, output). Changes apply immediately.")
        self.folder_tree_w.setMinimumHeight(150)  # enough for scrollbar to show cleanly
        self.folder_tree_w.setMaximumHeight(280)  # cap so layout stays stable; scroll when more folders
        self.folder_tree_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.folder_tree_w.itemChanged.connect(self._on_folder_check_changed)
        folder_tree_l.addWidget(self.folder_tree_w, 1)  # stretch 1 = 80%+
        tree_btn_gap = QFrame()
        tree_btn_gap.setFixedHeight(10)
        tree_btn_gap.setFrameShape(QFrame.Shape.NoFrame)
        tree_btn_gap.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        folder_tree_l.addWidget(tree_btn_gap, 0)
        folder_btn_bar = QWidget()
        folder_btn_bar.setMinimumHeight(56)
        folder_btn_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        folder_btn_l = QVBoxLayout(folder_btn_bar)
        folder_btn_l.setContentsMargins(0, 2, 0, 0)
        folder_btn_l.setSpacing(4)
        suggest_btn = QPushButton("Suggest exclude (RESULTS, output, ...)", clicked=self._suggest_exclude)
        suggest_btn.setToolTip("Auto-uncheck folders with names like results, output, processed, temp, etc.")
        folder_btn_l.addWidget(suggest_btn)
        self._collapse_top_btn = QPushButton("\u25B2 Collapse 1-3 for better view", clicked=self._toggle_top_section)
        self._collapse_top_btn.setToolTip("Collapse Root, Crawl, Include folders to get more space for keys and results.")
        self._collapse_top_btn.setMinimumWidth(260)
        self._collapse_top_btn.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        folder_btn_l.addWidget(self._collapse_top_btn)
        folder_tree_l.addWidget(folder_btn_bar, 0)
        top_content_l.addWidget(self.folder_tree_g, 1)
        self._expand_bar = QFrame()
        self._expand_bar.setFrameShape(QFrame.Shape.NoFrame)
        expand_l = QHBoxLayout(self._expand_bar)
        expand_l.setContentsMargins(0, 0, 0, 0)
        expand_l.setSpacing(0)
        expand_btn = QPushButton("\u25BC Expand 1-3", clicked=self._toggle_top_section)
        expand_btn.setToolTip("Show Root, Crawl, Include folders again.")
        expand_btn.setMinimumWidth(260)
        expand_btn.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        expand_l.addWidget(expand_btn)
        self._expand_bar.hide()
        top_section_l.addWidget(self._top_section_content, 1)
        top_section_l.addWidget(self._expand_bar, 0)

        # 4. Detected keys (title updated with file count)
        struct_g = QGroupBox("4. Detected keys (0 files)")
        self.struct_g = struct_g
        struct_g.setToolTip(
            "Parameters from filenames. Used = export column; Cat = store as TEXT for WOLKE filters; "
            "Uniques/Full = coverage; SI exp scales units. Hover column headers for details."
        )
        struct_g.setStyleSheet("QGroupBox { font-size: 12px; padding-top: 8px; }")
        struct_l = QVBoxLayout(struct_g)

        # Detected keys table
        keys_top = QWidget()
        keys_top_ll = QVBoxLayout(keys_top)
        keys_top_ll.setContentsMargins(0, 0, 0, 0)
        # One compact row: checkbox, warning/info, file count (dominant)
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        self.include_incomplete_cb = QCheckBox("Include incomplete (fill with empty)")
        self.include_incomplete_cb.setChecked(True)
        self.include_incomplete_cb.setToolTip("Checked: include all files, fill missing params with empty. Unchecked: only files with all parameters.")
        self.include_incomplete_cb.toggled.connect(self._on_include_incomplete_toggled)
        info_row.addWidget(self.include_incomplete_cb)
        self.dup_label = QLabel("")
        self.dup_label.setStyleSheet("font-size: 10px; padding: 0 4px 0 0;")
        self.dup_label.setWordWrap(False)
        info_row.addWidget(self.dup_label)
        self.schema_summary_label = QLabel("")
        self.schema_summary_label.setStyleSheet("font-size: 11px; font-weight: bold; padding: 0 8px 0 0;")
        self.schema_summary_label.setToolTip("Number of files. Per key: Full column = how many have the key, (−X) = how many are missing.")
        info_row.addWidget(self.schema_summary_label, 1)
        keys_top_ll.addLayout(info_row)
        detected_keys_label = QLabel("Detected keys (double-click Display name to edit):")
        detected_keys_label.setToolTip(
            "Parameters from filenames. Display name = label in exports (double-click to edit). Key = internal name (read-only). "
            "Hover column headers for Used, Cat, Uniques, Full, and unit columns."
        )
        keys_top_ll.addWidget(detected_keys_label)
        self.key_tree = QTreeWidget()
        self.key_tree.setHeaderLabels(
            ["Used", "Cat", "Uniques", "Full", "Display name", "Key", "SI exp", "Unit", "Min", "Max", "Mean"]
        )
        self.key_tree.setMinimumHeight(150)
        self.key_tree.setMaximumHeight(380)  # cap so layout stays stable; scroll when more keys
        self.key_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.key_tree.setColumnWidth(0, 50)
        self.key_tree.setColumnWidth(1, 50)
        self.key_tree.setColumnWidth(4, 180)
        self.key_tree.setColumnWidth(5, 80)
        self.key_tree.setStyleSheet("font-size: 11px;")
        _key_header_tips = [
            "Include this key as a column in SQLite / CSV / JSONL. None checked: export all keys. One or more checked: only those.",
            "Checked: write column as TEXT so WOLKE shows a filter (not a histogram). Default on when fewer than 10 distinct values. WOLKE sorts TEXT as text (1, 10, 2).",
            "Number of distinct values in the current file set. Drives defaults: Used when >1, Cat when <10.",
            "How many files have this key. (−N) = files missing it.",
            "Label used in exports. Double-click to edit.",
            "Internal key name (read-only).",
            "SI exponent for unit scaling (e.g. -3 for milli). Clear to keep raw unit.",
            "Unit after SI scaling, or raw unit from the filename.",
            "Minimum numeric value (if any).",
            "Maximum numeric value (if any).",
            "Mean numeric value (if any).",
        ]
        header_item = self.key_tree.headerItem()
        for col, tip in enumerate(_key_header_tips):
            header_item.setToolTip(col, tip)
        self.key_tree.setToolTip(
            "Used = include in export. Cat = TEXT for WOLKE filters. Uniques / Full = coverage. "
            "Hover a column header for details."
        )
        self.key_tree.itemSelectionChanged.connect(self._on_tree_select)
        self.key_tree.itemChanged.connect(self._on_key_tree_item_changed)
        keys_top_ll.addWidget(self.key_tree, 1)
        struct_l.addWidget(keys_top, 1)

        # Bottom splitter: 4. Detected keys | 5. Results (vertical, resizable)
        bottom_split = QSplitter(Qt.Orientation.Vertical)
        bottom_split.setMinimumWidth(200)  # keep scrollbars visible when window is narrow
        bottom_split.addWidget(struct_g)

        # 5. Results (path samples, extraction preview)
        results_g = QGroupBox("5. Results")
        results_g.setToolTip("Sample paths with extracted parameters colored. Verify extraction before saving.")
        results_g.setStyleSheet("QGroupBox { font-size: 12px; padding-top: 8px; }")
        results_l = QVBoxLayout(results_g)
        results_l.setSpacing(4)
        path_header = QHBoxLayout()
        path_samples_label = QLabel("Path samples:")
        path_samples_label.setToolTip("Number of paths shown below to verify extraction.")
        path_header.addWidget(path_samples_label)
        self.path_sample_spin = QSpinBox()
        self.path_sample_spin.setRange(3, 50)
        self.path_sample_spin.setValue(13)
        self.path_sample_spin.setToolTip("How many sample paths to show (equidistant from first to last).")
        self.path_sample_spin.valueChanged.connect(self._refresh_path_overview)
        path_header.addWidget(self.path_sample_spin)
        path_header.addWidget(QLabel("samples"))
        folder_idx_label = QLabel("Folder (0=random; >0=idx):")
        folder_idx_label.setToolTip("0=random mix; 1,2,3...=only paths from that folder.")
        path_header.addWidget(folder_idx_label)
        self.folder_idx_spin = QSpinBox()
        self.folder_idx_spin.setRange(0, 0)
        self.folder_idx_spin.setToolTip("0=random paths from all folders; 1,2,3...=paths from folder at that index.")
        self.folder_idx_spin.valueChanged.connect(self._refresh_path_overview)
        path_header.addWidget(self.folder_idx_spin)
        path_header.addStretch()
        results_l.addLayout(path_header)
        self.color_legend = QLabel("")
        self.color_legend.setWordWrap(True)
        self.color_legend.setStyleSheet("font-size: 11px; padding: 2px 0;")
        results_l.addWidget(self.color_legend)
        self.path_overview = QTextEdit()
        self.path_overview.setReadOnly(True)
        self.path_overview.setMinimumHeight(50)
        self.path_overview.setFontFamily("Consolas")
        self.path_overview.setStyleSheet("font-size: 10px; padding: 4px;")
        self.path_overview.setToolTip(
            "Full path: recognized (colored) + unrecognized (gray). Complete information space visible. Verify extraction before saving."
        )
        results_l.addWidget(self.path_overview, 1)
        self.key_samples_label = QLabel("")
        self.key_samples_label.setWordWrap(True)
        self.key_samples_label.setStyleSheet("font-size: 10px; padding: 2px 0; font-style: italic;")
        self.key_samples_label.setToolTip("Sample values for selected parameter. Click a key in the tree above.")
        results_l.addWidget(self.key_samples_label)

        # Outliers (directly after Results – see if we have dataset problems; 0 = green, else count + expand to see why)
        outlier_g = QGroupBox("Outliers")
        outlier_g.setToolTip(
            "Paths that deviate from the schema (low recognition) or likely typos in folder names. "
            "Typo: rare name similar to a frequent one (e.g. MultFiLI -> MultFilI?)."
        )
        outlier_l = QVBoxLayout(outlier_g)
        conf_row = QHBoxLayout()
        conf_lbl = QLabel("Min confidence:")
        conf_lbl.setToolTip(
            "Flag paths whose recognition score is below this value (0–1). "
            "Deep messy folders often land near 0.28; raise the threshold only if you want stricter checks, "
            "or lower it (e.g. 0.25) to quiet borderline camera caches."
        )
        conf_row.addWidget(conf_lbl)
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.setValue(float(settings.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)))
        self.confidence_spin.setToolTip(conf_lbl.toolTip())
        self.confidence_spin.valueChanged.connect(self._on_confidence_threshold_changed)
        conf_row.addWidget(self.confidence_spin)
        conf_row.addStretch()
        outlier_l.addLayout(conf_row)
        self.outlier_table = QTableWidget()
        self.outlier_table.setColumnCount(3)
        self.outlier_table.setHorizontalHeaderLabels(["Path", "Type", "Detail"])
        self.outlier_table.setMinimumHeight(120)
        self.outlier_table.setMaximumHeight(320)
        self.outlier_table.horizontalHeader().setStretchLastSection(True)
        self.outlier_table.setToolTip("Schema deviation or possible typo. Correct manually or via Unrecognized -> Parameters.")
        self.outlier_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.outlier_table.customContextMenuRequested.connect(self._outlier_table_context_menu)
        outlier_l.addWidget(self.outlier_table)
        outlier_container = QWidget()
        outlier_container_l = QVBoxLayout(outlier_container)
        outlier_container_l.setContentsMargins(0, 0, 0, 0)
        outlier_container_l.setSpacing(0)
        self._outlier_toggle_btn = QPushButton("Outliers: 0 \u25BC", clicked=self._toggle_outlier_section)
        self._outlier_toggle_btn.setToolTip("Paths with schema deviation or possible typos. Expand to see details. 0 = none (green).")
        self._outlier_toggle_btn.setStyleSheet("text-align: left; padding: 4px 8px;")
        outlier_container_l.addWidget(self._outlier_toggle_btn)
        outlier_container_l.addWidget(outlier_g)
        self._outlier_g = outlier_g
        self._outlier_section_visible = False
        self._outlier_relpaths: set = set()
        self._outlier_count = 0
        outlier_g.hide()
        results_l.addWidget(outlier_container)

        self.outlier_only_cb = QCheckBox("Path samples above: show only outlier paths")
        self.outlier_only_cb.setToolTip(
            "When checked: the path samples box shows only paths that are outliers (schema deviation or typo), "
            "instead of the normal spread. Use this to inspect problematic paths in context."
        )
        self.outlier_only_cb.stateChanged.connect(self._refresh_path_overview)
        results_l.addWidget(self.outlier_only_cb)

        # Token Patterns (collapsible): regex -> key, applied after built-in, before custom_token_map; incl. short date
        token_patterns_g = QGroupBox("Token Patterns")
        token_patterns_g.setToolTip(
            "Regex -> Key rules applied during crawl (after built-in, before exact token mappings). "
            "Short date (e.g. 22_01_26): Extract date_short_YY or date_short_DM."
        )
        tp_l = QVBoxLayout(token_patterns_g)
        self.token_patterns_table = QTableWidget()
        self.token_patterns_table.setColumnCount(4)
        self.token_patterns_table.setHorizontalHeaderLabels(["Key", "Regex", "Extract", "Priority"])
        self.token_patterns_table.horizontalHeader().setStretchLastSection(True)
        self.token_patterns_table.setMaximumHeight(100)
        self.token_patterns_table.cellChanged.connect(self._on_token_pattern_cell_changed)
        tp_l.addWidget(self.token_patterns_table)
        tp_btn_row = QHBoxLayout()
        tp_add_btn = QPushButton("Add", clicked=self._add_token_pattern)
        tp_rm_btn = QPushButton("Remove selected", clicked=self._remove_token_pattern)
        tp_btn_row.addWidget(tp_add_btn)
        tp_btn_row.addWidget(tp_rm_btn)
        tp_btn_row.addStretch()
        tp_l.addLayout(tp_btn_row)
        tp_container = QWidget()
        tp_container_l = QVBoxLayout(tp_container)
        tp_container_l.setContentsMargins(0, 0, 0, 0)
        tp_container_l.setSpacing(0)
        self._tp_toggle_btn = QPushButton("Token Patterns \u25BC", clicked=self._toggle_token_patterns_section)
        self._tp_toggle_btn.setToolTip("Regex rules for token recognition. Short date: Extract date_short_YY or date_short_DM.")
        self._tp_toggle_btn.setStyleSheet("text-align: left; padding: 4px 8px;")
        tp_container_l.addWidget(self._tp_toggle_btn)
        tp_container_l.addWidget(token_patterns_g)
        self._token_patterns_g = token_patterns_g
        self._token_patterns_section_visible = False
        self._syncing_token_patterns = False
        token_patterns_g.hide()

        # Unrecognized -> Parameters panel
        unrec_g = QGroupBox("Unrecognized \u2192 Parameters")
        unrec_g.setToolTip(
            "Gray = tokens the schema does not know. Promote them here: Token → Key. "
            "Example: SyncK, SyncAA → sync_mode. No re-crawl."
        )
        unrec_l = QVBoxLayout(unrec_g)
        unrec_l.setSpacing(4)
        unrec_row = QHBoxLayout()
        self.unrec_token_combo = QComboBox()
        self.unrec_token_combo.setEditable(False)
        self.unrec_token_combo.setMinimumWidth(140)
        self.unrec_token_combo.setToolTip("Unrecognized tokens from current data. Select one to map.")
        self.unrec_token_combo.currentIndexChanged.connect(self._on_unrec_token_selected)
        unrec_row.addWidget(QLabel("Token:"))
        unrec_row.addWidget(self.unrec_token_combo)
        self.unrec_key_edit = QLineEdit()
        self.unrec_key_edit.setPlaceholderText("key name")
        self.unrec_key_edit.setMinimumWidth(100)
        self.unrec_key_edit.setToolTip("Parameter key (e.g. result_type). Value = token.")
        unrec_row.addWidget(QLabel("→ Key:"))
        unrec_row.addWidget(self.unrec_key_edit)
        add_map_btn = QPushButton("Add", clicked=self._add_custom_token_mapping)
        add_map_btn.setToolTip("Add mapping: token → key. Applied immediately.")
        unrec_row.addWidget(add_map_btn)
        unrec_l.addLayout(unrec_row)
        self.unrec_mappings_list = QTreeWidget()
        self.unrec_mappings_list.setHeaderLabels(["Token", "Key"])
        self.unrec_mappings_list.setMaximumHeight(80)
        self.unrec_mappings_list.setToolTip("Current custom mappings. Right-click or use Remove to delete.")
        unrec_l.addWidget(self.unrec_mappings_list)
        unrec_btn_row = QHBoxLayout()
        rm_map_btn = QPushButton("Remove selected", clicked=self._remove_custom_token_mapping)
        rm_map_btn.setToolTip("Remove selected mapping.")
        batch_btn = QPushButton("Map all suggested", clicked=self._batch_map_suggested)
        batch_btn.setToolTip("Map all unrecognized tokens that match existing patterns (e.g. C2,C3 like C1->channel).")
        unrec_btn_row.addWidget(rm_map_btn)
        unrec_btn_row.addWidget(batch_btn)
        unrec_btn_row.addStretch()
        unrec_l.addLayout(unrec_btn_row)
        unrec_container = QWidget()
        unrec_container_l = QVBoxLayout(unrec_container)
        unrec_container_l.setContentsMargins(0, 0, 0, 0)
        unrec_container_l.setSpacing(0)
        self._unrec_toggle_btn = QPushButton("Unrecognized → Parameters \u25BC", clicked=self._toggle_unrec_section)
        self._unrec_toggle_btn.setToolTip("Expand to map unrecognized tokens to keys. Collapsed by default.")
        self._unrec_toggle_btn.setStyleSheet("text-align: left; padding: 4px 8px;")
        unrec_container_l.addWidget(self._unrec_toggle_btn)
        unrec_container_l.addWidget(unrec_g)
        self._unrec_g = unrec_g
        self._unrec_section_visible = False
        unrec_g.hide()

        # Advanced features (work in progress): Token Patterns + Unrecognized only; hidden by default, foldable
        advanced_g = QGroupBox("Advanced features (work in progress)")
        advanced_g.setToolTip("Token Patterns and Unrecognized → Parameters. Functional but still evolving.")
        advanced_l = QVBoxLayout(advanced_g)
        advanced_l.setSpacing(4)
        advanced_l.addWidget(tp_container)
        advanced_l.addWidget(unrec_container)
        advanced_container = QWidget()
        advanced_container_l = QVBoxLayout(advanced_container)
        advanced_container_l.setContentsMargins(0, 0, 0, 0)
        advanced_container_l.setSpacing(0)
        self._advanced_toggle_btn = QPushButton("Advanced features (work in progress) \u25BC", clicked=self._toggle_advanced_section)
        self._advanced_toggle_btn.setToolTip("Token Patterns and Unrecognized → Parameters. Expand when needed.")
        self._advanced_toggle_btn.setStyleSheet("text-align: left; padding: 4px 8px;")
        advanced_container_l.addWidget(self._advanced_toggle_btn)
        advanced_container_l.addWidget(advanced_g)
        self._advanced_g = advanced_g
        self._advanced_section_visible = False
        advanced_g.hide()
        results_l.addWidget(advanced_container)

        bottom_split.addWidget(results_g)
        bottom_split.setSizes([300, 300])  # Detected keys and Results initially similar height
        bottom_split.setStretchFactor(0, 2)
        bottom_split.setStretchFactor(1, 3)
        ms_sizes = settings.get("main_splitter_sizes", "")
        if ms_sizes:
            try:
                sizes = [int(x.strip()) for x in ms_sizes.split(",") if x.strip()]
                if len(sizes) >= 2:
                    bottom_split.setSizes(sizes)
            except ValueError:
                pass
        self.bottom_split = bottom_split

        # Minimum heights so panes don't collapse to one line at 800x1000
        struct_g.setMinimumHeight(200)
        results_g.setMinimumHeight(250)
        # Scrollable middle block (4. Keys + 5. Results) for 800x1000 laptop view
        middle_container = QWidget()
        middle_container.setMinimumHeight(650)
        middle_container.setMinimumWidth(200)  # so scrollbars stay visible when window is narrow
        middle_layout = QVBoxLayout(middle_container)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.addWidget(bottom_split)
        self._keys_results_scroll = QScrollArea()
        self._keys_results_scroll.setWidget(middle_container)
        self._keys_results_scroll.setWidgetResizable(True)
        self._keys_results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._keys_results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._keys_results_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._keys_results_scroll.setMinimumWidth(220)  # room for vertical scrollbar + content
        self._keys_results_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Resizable splitter between Include folders (1-3) and Detected Keys (4-5)
        self._top_middle_split = QSplitter(Qt.Orientation.Vertical)
        self._top_middle_split.setChildrenCollapsible(False)
        # Min height so Root + Crawl + Include-folders (250px) fit; scrollbar and list never overlap buttons
        top_section.setMinimumHeight(420)
        self._top_middle_split.addWidget(top_section)
        self._top_middle_split.addWidget(self._keys_results_scroll)
        self._top_middle_split.setStretchFactor(0, 0)
        self._top_middle_split.setStretchFactor(1, 1)
        self._top_middle_split.setSizes([420, 400])

        # Top (1-3) | scrollable middle (4-5) | save+log – fixed 800x1000 target
        main.addWidget(self._top_middle_split, 1)

        # 6. Save + Log: one mini bar (buttons + one-line log), no splitter
        save_log_bar = QWidget()
        save_log_bar.setFixedHeight(40)
        save_log_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar_l = QHBoxLayout(save_log_bar)
        bar_l.setContentsMargins(0, 2, 0, 2)
        bar_l.setSpacing(6)
        save_btn = QPushButton("Save to DB", clicked=self._save_to_db)
        save_btn.setStyleSheet("font-weight: bold; min-width: 100px;")
        save_btn.setToolTip("Write indexed data to SQLite database (path from Output & DB).")
        bar_l.addWidget(save_btn)
        export_btn = QPushButton("Export JSONL/CSV", clicked=self._export_files)
        export_btn.setToolTip("Export index.jsonl, index.csv to Output folder.")
        bar_l.addWidget(export_btn)
        bar_l.addSpacing(8)
        self.log_widget = QPlainTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setFixedHeight(26)
        self.log_widget.setFont(QFont("Consolas", 9))
        self.log_widget.setStyleSheet("font-size: 9px; padding: 2px 4px;")
        self.log_widget.setPlaceholderText("Log (crawl timings, files/s)")
        self.log_widget.setToolTip("Crawl progress and timing info. Last lines shown.")
        bar_l.addWidget(self.log_widget, 1)
        main.addWidget(save_log_bar, 0)

        self._log_queue: queue.Queue = queue.Queue()
        self.setAcceptDrops(True)
        self.dragEnterEvent = self._drag_enter
        self.dropEvent = self._drop

        self._apply_theme()
        QTimer.singleShot(0, self._poll_queue)

    def _drag_enter(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def _drop(self, e) -> None:
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                self._set_root(str(p.resolve()))
                QTimer.singleShot(0, self._start_crawl)
                break
            elif p.parent.is_dir():
                self._set_root(str(p.parent.resolve()))
                QTimer.singleShot(0, self._start_crawl)
                break

    def _set_root(self, path: str) -> None:
        self.root_edit.setText(path)
        if not self.output_edit.text().strip():
            self.output_edit.setText(str(Path(path) / "_index"))
        if not self.db_edit.text().strip():
            self.db_edit.setText(str(default_db_path_for_root(path)))

    def _toggle_advanced(self, on: bool) -> None:
        self.advanced_w.setVisible(on)

    def _toggle_top_section(self) -> None:
        """Collapse/expand sections 1-3 (Root, Crawl, Include folders). Collapsed = only button, no margin."""
        content = getattr(self, "_top_section_content", None)
        expand_bar = getattr(self, "_expand_bar", None)
        top_section = getattr(self, "_top_section", None)
        split = getattr(self, "_top_middle_split", None)
        if not content or not expand_bar:
            return
        visible = not content.isVisible()
        content.setVisible(visible)
        expand_bar.setVisible(not visible)
        if top_section:
            if visible:
                top_section.setMaximumHeight(16777215)
                top_section.setMinimumHeight(420)
                if split:
                    total = sum(split.sizes())
                    saved = getattr(self, "_saved_top_section_height", 420)
                    split.setSizes([min(saved, max(420, total - 100)), total - min(saved, max(420, total - 100))])
            else:
                top_section.setMaximumHeight(48)
                top_section.setMinimumHeight(40)
                if split:
                    total = sum(split.sizes())
                    self._saved_top_section_height = split.sizes()[0]
                    split.setSizes([48, max(100, total - 48)])

    def _toggle_unrec_section(self) -> None:
        """Expand/collapse Unrecognized -> Parameters panel (collapsed by default)."""
        self._unrec_section_visible = not getattr(self, "_unrec_section_visible", False)
        self._unrec_g.setVisible(self._unrec_section_visible)
        if self._unrec_section_visible:
            self._unrec_toggle_btn.setText("Unrecognized \u2192 Parameters \u25B2")
        else:
            self._unrec_toggle_btn.setText("Unrecognized \u2192 Parameters \u25BC")

    def _toggle_token_patterns_section(self) -> None:
        """Expand/collapse Token Patterns panel."""
        self._token_patterns_section_visible = not getattr(self, "_token_patterns_section_visible", False)
        self._token_patterns_g.setVisible(self._token_patterns_section_visible)
        n = len(getattr(self, "token_patterns", []) or [])
        if self._token_patterns_section_visible:
            self._tp_toggle_btn.setText(f"Token Patterns ({n}) \u25B2")
        else:
            self._tp_toggle_btn.setText(f"Token Patterns ({n}) \u25BC")

    def _sync_token_patterns_from_table(self) -> None:
        """Build self.token_patterns from table rows. Call before crawl/save."""
        if getattr(self, "_syncing_token_patterns", False):
            return
        tbl = getattr(self, "token_patterns_table", None)
        if not tbl:
            return
        import re as re_mod
        out: list[dict] = []
        for r in range(tbl.rowCount()):
            key_item = tbl.item(r, 0)
            regex_item = tbl.item(r, 1)
            extract_item = tbl.item(r, 2)
            prio_item = tbl.item(r, 3)
            key = (key_item.text() or "").strip() if key_item else ""
            regex = (regex_item.text() or "").strip() if regex_item else ""
            extract = (extract_item.text() or "str").strip() if extract_item else "str"
            try:
                prio = int((prio_item.text() or "0").strip()) if prio_item else 0
            except ValueError:
                prio = 0
            if not key and not regex:
                continue
            if regex:
                try:
                    re_mod.compile(regex)
                except re_mod.error:
                    continue
            out.append({"key": key or "param", "regex": regex, "extract": extract or "str", "priority": prio})
        self.token_patterns = out

    def _refresh_token_patterns_table(self) -> None:
        """Fill Token Patterns table from self.token_patterns."""
        tbl = getattr(self, "token_patterns_table", None)
        if not tbl:
            return
        self._syncing_token_patterns = True
        try:
            tbl.setRowCount(0)
            for p in getattr(self, "token_patterns", []) or []:
                row = tbl.rowCount()
                tbl.insertRow(row)
                tbl.setItem(row, 0, QTableWidgetItem(str(p.get("key", ""))))
                tbl.setItem(row, 1, QTableWidgetItem(str(p.get("regex", ""))))
                tbl.setItem(row, 2, QTableWidgetItem(str(p.get("extract", "str"))))
                tbl.setItem(row, 3, QTableWidgetItem(str(p.get("priority", 0))))
            n = len(self.token_patterns)
            if getattr(self, "_tp_toggle_btn", None):
                self._tp_toggle_btn.setText(
                    f"Token Patterns ({n}) \u25B2" if getattr(self, "_token_patterns_section_visible", False)
                    else f"Token Patterns ({n}) \u25BC"
                )
        finally:
            self._syncing_token_patterns = False

    def _add_token_pattern(self) -> None:
        """Append a new row to Token Patterns table."""
        tbl = getattr(self, "token_patterns_table", None)
        if not tbl:
            return
        row = tbl.rowCount()
        tbl.insertRow(row)
        tbl.setItem(row, 0, QTableWidgetItem(""))
        tbl.setItem(row, 1, QTableWidgetItem(""))
        tbl.setItem(row, 2, QTableWidgetItem("int"))
        tbl.setItem(row, 3, QTableWidgetItem("0"))

    def _remove_token_pattern(self) -> None:
        """Remove selected row(s) from Token Patterns table and sync to self.token_patterns."""
        tbl = getattr(self, "token_patterns_table", None)
        if not tbl:
            return
        rows = sorted(set(i.row() for i in tbl.selectedIndexes()), reverse=True)
        for r in rows:
            tbl.removeRow(r)
        self._sync_token_patterns_from_table()
        n = len(self.token_patterns)
        if getattr(self, "_tp_toggle_btn", None):
            self._tp_toggle_btn.setText(
                f"Token Patterns ({n}) \u25B2" if getattr(self, "_token_patterns_section_visible", False)
                else f"Token Patterns ({n}) \u25BC"
            )

    def _on_token_pattern_cell_changed(self, row: int, col: int) -> None:
        """After edit, sync table -> self.token_patterns and update toggle label."""
        if getattr(self, "_syncing_token_patterns", False):
            return
        self._sync_token_patterns_from_table()
        n = len(self.token_patterns)
        if getattr(self, "_tp_toggle_btn", None):
            self._tp_toggle_btn.setText(
                f"Token Patterns ({n}) \u25B2" if getattr(self, "_token_patterns_section_visible", False)
                else f"Token Patterns ({n}) \u25BC"
            )

    def _set_outlier_button_style(self, n: int) -> None:
        """Green when 0 outliers, default otherwise."""
        base = "text-align: left; padding: 4px 8px;"
        if n == 0:
            self._outlier_toggle_btn.setStyleSheet(base + " color: #0a0; font-weight: bold;")
        else:
            self._outlier_toggle_btn.setStyleSheet(base)

    def _toggle_advanced_section(self) -> None:
        """Expand/collapse Advanced features panel (Token Patterns + Unrecognized). Hidden by default."""
        self._advanced_section_visible = not getattr(self, "_advanced_section_visible", False)
        g = getattr(self, "_advanced_g", None)
        btn = getattr(self, "_advanced_toggle_btn", None)
        if g:
            g.setVisible(self._advanced_section_visible)
        if btn:
            btn.setText(
                "Advanced features (work in progress) \u25B2" if self._advanced_section_visible
                else "Advanced features (work in progress) \u25BC"
            )

    def _toggle_outlier_section(self) -> None:
        """Expand/collapse Outliers panel (collapsed by default). When expanded, give more space to Results."""
        self._outlier_section_visible = not getattr(self, "_outlier_section_visible", False)
        self._outlier_g.setVisible(self._outlier_section_visible)
        n = getattr(self, "_outlier_count", 0)
        tri = "\u25B2" if self._outlier_section_visible else "\u25BC"
        self._outlier_toggle_btn.setText(f"Outliers: {n} {tri}")
        self._set_outlier_button_style(n)
        split = getattr(self, "bottom_split", None)
        if split and split.count() >= 2:
            s0, s1 = split.sizes()[0], split.sizes()[1]
            total = s0 + s1
            if self._outlier_section_visible:
                # Shrink Detected keys so Results (and Outliers table) get more space
                new_s0 = min(s0, 260)
                split.setSizes([new_s0, total - new_s0])
            else:
                # Restore similar height for both panes
                half = max(200, total // 2)
                split.setSizes([half, total - half])

    def _outlier_table_context_menu(self, pos: object) -> None:
        """Show context menu on outlier table; offer 'Open in Unrecognized'."""
        tbl = self.outlier_table
        idx = tbl.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        path_item = tbl.item(row, 0)
        relpath = (path_item.text() or "").strip() if path_item else ""
        if not relpath:
            return
        menu = QMenu(self)
        act = menu.addAction("Open in Unrecognized \u2192 Parameters")
        chosen = menu.exec(tbl.viewport().mapToGlobal(pos))
        if chosen == act:
            self._open_outlier_in_unrecognized(relpath)

    def _open_outlier_in_unrecognized(self, relpath: str) -> None:
        """Expand Unrecognized section and select first unrecognized token from the path's row."""
        row = next((r for r in (getattr(self, "_all_rows", None) or []) if (r.get("relpath") or "") == relpath), None)
        if not row:
            return
        folder_ttk = row.get("_folder_token_to_key") or {}
        file_ttk = row.get("_file_token_to_key") or {}
        all_ttk = {**folder_ttk, **file_ttk}
        folder_tokens = row.get("_folder_tokens") or []
        file_tokens = row.get("_file_tokens") or []
        unrec = [t for t in folder_tokens + file_tokens if t and t not in all_ttk]
        if not getattr(self, "_unrec_section_visible", False):
            self._unrec_section_visible = True
            self._unrec_g.setVisible(True)
            self._unrec_toggle_btn.setText("Unrecognized \u2192 Parameters \u25B2")
        self._refresh_unrecognized_panel()
        if unrec:
            tok = unrec[0]
            for i in range(self.unrec_token_combo.count()):
                if self.unrec_token_combo.itemData(i) == tok:
                    self.unrec_token_combo.setCurrentIndex(i)
                    break
        self.unrec_key_edit.setFocus()

    def _apply_theme(self) -> None:
        light = self.light_mode_cb.isChecked()
        self.setStyleSheet(STYLESHEET_LIGHT if light else STYLESHEET_DARK)
        if getattr(self, "_last_sample_rows", None):
            self._fill_path_overview(self._last_sample_rows)
        if getattr(self, "_last_detected_keys", None):
            self._refresh_key_tree(self._last_detected_keys, key_order=getattr(self, "_legend_key_order", None))

    def _populate_folder_tree(self, rows: list) -> None:
        by_folder, by_folder_ext = _build_folder_tree(rows)
        if not by_folder:
            self.folder_tree_w.clear()
            self._folder_tree_ready = False
            return

        all_paths: set[str] = set()
        for p in by_folder:
            parts = p.split("/") if p else []
            for i in range(1, len(parts) + 1):
                all_paths.add("/".join(parts[:i]))
        prefix_count: dict[str, int] = {}
        prefix_ext: dict[str, dict[str, int]] = {}
        for folder, c in by_folder.items():
            parts = folder.split("/") if folder else []
            exts = by_folder_ext.get(folder, {})
            for i in range(len(parts) + 1):
                p = "/".join(parts[:i]) if i else ""
                prefix_count[p] = prefix_count.get(p, 0) + c
                if p not in prefix_ext:
                    prefix_ext[p] = {}
                for ext, cnt in exts.items():
                    prefix_ext[p][ext] = prefix_ext[p].get(ext, 0) + cnt

        path_to_item: dict[str, QTreeWidgetItem] = {}
        sorted_paths = sorted(all_paths)
        path_to_idx = {p: i + 1 for i, p in enumerate(sorted_paths)}
        ext_filter = getattr(self, "_ext_filter", None)
        self.folder_tree_w.clear()
        for path in sorted_paths:
            idx = path_to_idx.get(path, 0)
            parts = path.split("/")
            name = parts[-1] if parts else ""
            parent_path = "/".join(parts[:-1]) if len(parts) > 1 else None
            parent_item = path_to_item.get(parent_path) if parent_path else None
            total = prefix_count.get(path, 0)
            exts_here = prefix_ext.get(path, {})
            files_str = ", ".join(f"{cnt} ({ext})" for ext, cnt in sorted(exts_here.items(), key=lambda x: (-x[1], x[0])))
            if not files_str:
                files_str = "0"
            count_selected = sum(exts_here.values()) if ext_filter is None else exts_here.get(ext_filter, 0)
            item = QTreeWidgetItem([str(idx), "", name, files_str])
            # Checkable only — do NOT set ItemIsUserTristate (that makes clicks cycle
            # checked → partial → unchecked). Partial is set programmatically on parents
            # when children are mixed.
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(2, Qt.ItemDataRole.UserRole, path)
            item.setCheckState(1, Qt.CheckState.Checked if count_selected > 0 else Qt.CheckState.Unchecked)
            if parent_item:
                parent_item.addChild(item)
            else:
                self.folder_tree_w.addTopLevelItem(item)
            path_to_item[path] = item
        for c in range(self.folder_tree_w.columnCount()):
            self.folder_tree_w.resizeColumnToContents(c)
        self._prefix_ext = prefix_ext
        self._prefix_count = prefix_count
        has_subfolders = len(all_paths) > 1 or any("/" in p for p in all_paths)
        self._update_folder_tree_title(None)
        if not has_subfolders:
            info_item = QTreeWidgetItem(["", "", "", "No subfolders, all files in root"])
            info_item.setFlags(info_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            info_item.setData(2, Qt.ItemDataRole.UserRole, None)
            self.folder_tree_w.insertTopLevelItem(0, info_item)
        self.folder_tree_g.show()
        self._folder_tree_ready = False
        self.folder_tree_w.blockSignals(True)
        self._suggest_exclude()
        self.folder_tree_w.blockSignals(False)
        self._folder_tree_ready = True
        self._apply_folder_selection()

    def _update_folder_tree_title(self, selected_count: int | None) -> None:
        """Show selected file count so checkbox changes feel immediate."""
        if selected_count is None:
            self.folder_tree_g.setTitle(
                "3. Include folders (uncheck to exclude, changes apply immediately)"
            )
            return
        self.folder_tree_g.setTitle(
            f"3. Include folders ({_fmt_count(selected_count)} selected — changes apply immediately)"
        )

    def _set_folder_check_recursive(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        item.setCheckState(1, state)
        for i in range(item.childCount()):
            self._set_folder_check_recursive(item.child(i), state)

    def _sync_folder_parent_check(self, parent: QTreeWidgetItem) -> None:
        """Parent reflects children: all / none / partial."""
        n = parent.childCount()
        if n <= 0:
            return
        checked = 0
        unchecked = 0
        for i in range(n):
            st = parent.child(i).checkState(1)
            if st == Qt.CheckState.Checked:
                checked += 1
            elif st == Qt.CheckState.Unchecked:
                unchecked += 1
        if checked == n:
            parent.setCheckState(1, Qt.CheckState.Checked)
        elif unchecked == n:
            parent.setCheckState(1, Qt.CheckState.Unchecked)
        else:
            parent.setCheckState(1, Qt.CheckState.PartiallyChecked)

    def _on_folder_check_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 1:
            return
        if not getattr(self, "_folder_tree_ready", False):
            return
        if getattr(self, "_folder_check_updating", False):
            return
        # Cascade parent → children; then bubble parent states so the tree matches selection.
        self._folder_check_updating = True
        self.folder_tree_w.blockSignals(True)
        try:
            state = item.checkState(1)
            if state != Qt.CheckState.PartiallyChecked:
                for i in range(item.childCount()):
                    self._set_folder_check_recursive(item.child(i), state)
            parent = item.parent()
            while parent is not None:
                self._sync_folder_parent_check(parent)
                parent = parent.parent()
        finally:
            self.folder_tree_w.blockSignals(False)
            self._folder_check_updating = False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            QApplication.processEvents()
            self._apply_folder_selection()
        finally:
            QApplication.restoreOverrideCursor()

    def _apply_folder_selection(self) -> None:
        included: set[str] = set()

        def collect(it: QTreeWidgetItem) -> None:
            path = it.data(2, Qt.ItemDataRole.UserRole)
            # Fully checked only — PartiallyChecked parents are covered by checked children.
            if path is not None and it.checkState(1) == Qt.CheckState.Checked:
                included.add(str(path))
            for i in range(it.childCount()):
                collect(it.child(i))

        for i in range(self.folder_tree_w.topLevelItemCount()):
            collect(self.folder_tree_w.topLevelItem(i))

        self._folder_includes = included
        self.rows = filter_rows_by_folder_includes(self._get_ext_filtered_rows(), included)
        self._update_folder_tree_title(len(self.rows))
        self._show_nomenclature()

    def _get_ext_filtered_rows(self) -> list:
        """Rows filtered by _ext_filter (None = all types)."""
        if not self._all_rows:
            return []
        if self._ext_filter is None:
            return list(self._all_rows)
        return [r for r in self._all_rows if r.get("ext") == self._ext_filter]

    def _populate_ext_filter_buttons(self, ext_counts: Counter) -> None:
        """Build clickable buttons: [.tif 1000] [.csv 50] [All 1050]. Default = dominant."""
        while self.ext_filter_buttons_l.count():
            w = self.ext_filter_buttons_l.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not ext_counts:
            return
        total = sum(ext_counts.values())
        sorted_exts = ext_counts.most_common()
        for ext, cnt in sorted_exts:
            btn = QPushButton(f"{ext} ({_fmt_count(cnt)})")
            btn.setCheckable(True)
            btn.setChecked(ext == self._ext_filter)
            btn.setToolTip(f"Show only {ext} files")
            btn.clicked.connect(lambda checked=False, e=ext: self._on_ext_filter_clicked(e))
            self.ext_filter_buttons_l.addWidget(btn)
        all_btn = QPushButton(f"All ({_fmt_count(total)})")
        all_btn.setCheckable(True)
        all_btn.setChecked(self._ext_filter is None)
        all_btn.setToolTip("Show all file types")
        all_btn.clicked.connect(lambda: self._on_ext_filter_clicked(None))
        self.ext_filter_buttons_l.addWidget(all_btn)

    def _on_ext_filter_clicked(self, ext: str | None) -> None:
        """User clicked an extension filter. Update display and folder checkboxes."""
        self._ext_filter = ext
        for i in range(self.ext_filter_buttons_l.count()):
            w = self.ext_filter_buttons_l.itemAt(i).widget()
            if isinstance(w, QPushButton):
                lbl = w.text()
                if ext is None:
                    w.setChecked(lbl.startswith("All "))
                else:
                    w.setChecked(lbl.startswith(ext + " "))
        self._update_folder_tree_check_boxes()
        self.rows = filter_rows_by_folder_includes(self._get_ext_filtered_rows(), self._folder_includes)
        if self._folder_includes is not None:
            self._update_folder_tree_title(len(self.rows))
        self._show_nomenclature()

    def _update_folder_tree_check_boxes(self) -> None:
        """Set folder Include checkboxes from current _ext_filter and _prefix_ext."""
        prefix_ext = getattr(self, "_prefix_ext", None)
        if not prefix_ext:
            return
        ext_filter = getattr(self, "_ext_filter", None)
        self.folder_tree_w.blockSignals(True)
        try:
            def set_rec(it: QTreeWidgetItem) -> None:
                path = it.data(2, Qt.ItemDataRole.UserRole)
                if path is not None:
                    exts_here = prefix_ext.get(path, {})
                    count_selected = sum(exts_here.values()) if ext_filter is None else exts_here.get(ext_filter, 0)
                    it.setCheckState(1, Qt.CheckState.Checked if count_selected > 0 else Qt.CheckState.Unchecked)
                for i in range(it.childCount()):
                    set_rec(it.child(i))
            for i in range(self.folder_tree_w.topLevelItemCount()):
                set_rec(self.folder_tree_w.topLevelItem(i))
        finally:
            self.folder_tree_w.blockSignals(False)
        self._apply_folder_selection()

    def _suggest_exclude(self) -> None:
        exclude_keywords = ("results", "output", "processed", "statistical", "mean", "export", "out", "temp")
        for i in range(self.folder_tree_w.topLevelItemCount()):
            self._suggest_exclude_rec(self.folder_tree_w.topLevelItem(i), exclude_keywords)
        # Uncheck folders that are much smaller than the majority (e.g. 5x200 + 1x4 -> uncheck the 4)
        prefix_count = getattr(self, "_prefix_count", None) or {}
        candidates: list[tuple[QTreeWidgetItem, int]] = []
        if self.folder_tree_w.topLevelItemCount() >= 1:
            root = self.folder_tree_w.topLevelItem(0)
            root_path = root.data(2, Qt.ItemDataRole.UserRole) or ""
            if root_path == "" and root.childCount() > 0:
                for i in range(root.childCount()):
                    it = root.child(i)
                    path = it.data(2, Qt.ItemDataRole.UserRole) or ""
                    c = prefix_count.get(path, 0)
                    candidates.append((it, c))
            else:
                for i in range(self.folder_tree_w.topLevelItemCount()):
                    it = self.folder_tree_w.topLevelItem(i)
                    path = it.data(2, Qt.ItemDataRole.UserRole) or ""
                    c = prefix_count.get(path, 0)
                    candidates.append((it, c))
        if len(candidates) >= 2 and max(c for _, c in candidates) >= 10:
            import statistics
            counts = [c for _, c in candidates]
            med = statistics.median(counts)
            threshold = min(20, max(1, 0.15 * med))
            for it, c in candidates:
                if c < threshold:
                    it.setCheckState(1, Qt.CheckState.Unchecked)

    def _update_effective_rows(self, keys: list | None = None) -> None:
        """Compute _effective_rows: all if include_incomplete else only rows with all detected keys."""
        if not self.rows:
            self._effective_rows = []
            self._folder_list = []
            return
        k = keys or getattr(self, "_last_detected_keys", None) or suggest_nomenclature(self.rows)["detected_fields"]
        incl = getattr(self, "include_incomplete_cb", None)
        if not k or (incl is not None and incl.isChecked()):
            self._effective_rows = list(self.rows)
        else:
            self._effective_rows = [r for r in self.rows if all(r.get(key) is not None for key in k)]
        self._folder_list = sorted(set(_row_folder(r) for r in self._effective_rows))
        if getattr(self, "folder_idx_spin", None):
            self.folder_idx_spin.blockSignals(True)
            self.folder_idx_spin.setRange(0, max(0, len(self._folder_list)))
            if self.folder_idx_spin.value() > len(self._folder_list):
                self.folder_idx_spin.setValue(0)
            self.folder_idx_spin.blockSignals(False)

    def _on_include_incomplete_toggled(self) -> None:
        self._update_effective_rows(self._last_detected_keys)
        self.key_is_used.clear()
        if self._last_detected_keys:
            self._refresh_key_tree(self._last_detected_keys, key_order=getattr(self, "_legend_key_order", None))
            self._update_detected_keys_header()
            root = self.root_edit.text().strip() or None
            self._legend_key_order = _compute_legend_key_order(
                self._effective_rows, self._last_detected_keys, root
            )
            self._refresh_path_overview()
            self._refresh_outlier_panel()

    def _update_detected_keys_header(self) -> None:
        """Update group box title with file count; no duplicate count in row."""
        n = len(self._effective_rows)
        n_all = len(self.rows)
        title = f"4. Detected keys ({_fmt_count(n)} files)"
        if n_all != n and n_all:
            title += f" (from {_fmt_count(n_all)} in folders)"
        self.struct_g.setTitle(title)
        self.schema_summary_label.setText("")

    def _suggest_exclude_rec(self, item: QTreeWidgetItem, keywords: tuple) -> None:
        path = item.data(2, Qt.ItemDataRole.UserRole) or ""
        path_lower = path.lower()
        if any(kw in path_lower for kw in keywords):
            item.setCheckState(1, Qt.CheckState.Unchecked)
        for i in range(item.childCount()):
            self._suggest_exclude_rec(item.child(i), keywords)

    def _browse_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select root folder")
        if path:
            self._set_root(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self.output_edit.setText(path)

    def _browse_db(self) -> None:
        start_dir = self.root_edit.text().strip()
        if not start_dir or not Path(start_dir).is_dir():
            start_dir = ""
        path, _ = QFileDialog.getSaveFileName(self, "Save database", start_dir, "SQLite DB (*.db)")
        if path:
            self.db_edit.setText(path)

    def _get_config(self) -> dict:
        self._sync_token_patterns_from_table()
        cfg = {
            "allowed_suffixes": DEFAULT_ALLOWED_SUFFIXES,
            "folder_token_depth": self.depth_spin.value(),
            "recursive": self.recursive_cb.isChecked(),
            "include_hidden": self.include_hidden_cb.isChecked(),
            "parallel_threshold": 999999,  # sequential only (parallel slower on Windows)
        }
        cfg["custom_token_map"] = dict(getattr(self, "custom_token_map", {}) or {})
        cfg["token_patterns"] = list(getattr(self, "token_patterns", []) or [])
        return cfg

    def _start_crawl(self) -> None:
        root_dir = self.root_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        if not root_dir:
            QMessageBox.warning(self, "Root required", "Please select a root folder first.")
            return
        if not Path(root_dir).is_dir():
            QMessageBox.critical(self, "Error", f"Folder does not exist: {root_dir}")
            return
        if not output_dir:
            output_dir = str(Path(root_dir) / "_index")
            self.output_edit.setText(output_dir)

        self.crawl_btn.setEnabled(False)
        self.progress_label.setText("Crawling...")
        self._crawl_progress = QProgressDialog("Indexing files...", None, 0, 0, self)
        self._crawl_progress.setWindowTitle("DAMPF")
        self._crawl_progress.setMinimumDuration(0)
        self._crawl_progress.setModal(False)
        self._crawl_progress.show()
        config = self._get_config()
        old = self.current_config or {}
        self.current_config = {
            **config, "root_dir": root_dir, "output_dir": output_dir,
            "db_path": self.db_edit.text().strip() or "",
            "table_name": old.get("table_name") or "data",
            "relative_filepath_column": old.get("relative_filepath_column") or "relpath",
        }
        q = queue.Queue()
        self.log_widget.clear()
        self._crawl_start_time = time.perf_counter()
        while True:
            try:
                self._log_queue.get_nowait()
            except queue.Empty:
                break
        t = threading.Thread(
            target=_run_indexer_worker,
            args=(root_dir, output_dir, config, q),
            kwargs={"log_queue": self._log_queue},
        )
        t.daemon = True
        t.start()
        self._crawl_queue = q
        self._crawl_done = False

    def _poll_queue(self) -> None:
        while True:
            try:
                msg = self._log_queue.get_nowait()
                self.log_widget.appendPlainText(msg)
                sb = self.log_widget.verticalScrollBar()
                if sb:
                    sb.setValue(sb.maximum())
            except queue.Empty:
                break
        if self._crawl_queue and not self._crawl_done:
            try:
                result = self._crawl_queue.get_nowait()
                status, payload = result
                self._crawl_done = True
                self.crawl_btn.setEnabled(True)
                if status == "ok":
                    prog = getattr(self, "_crawl_progress", None)
                    if prog:
                        prog.setLabelText("Processing results...")
                    raw_rows, _ = payload
                    t_gui0 = time.perf_counter()
                    self._all_rows = list(raw_rows)
                    _apply_custom_token_map(self._all_rows, self.custom_token_map)
                    ext_counts = Counter(r.get("ext", "") for r in raw_rows if r.get("ext"))
                    dominant = ext_counts.most_common(1)[0][0] if ext_counts else ""
                    self._ext_filter = dominant if dominant else None
                    self._populate_ext_filter_buttons(ext_counts)
                    self._folder_includes = None  # until folder tree applies selection
                    self.rows = filter_rows_by_folder_includes(self._get_ext_filtered_rows(), self._folder_includes)
                    n_shown = len(self.rows)
                    n_all = len(self._all_rows)
                    if dominant and n_shown != n_all:
                        msg = (
                            f"Done: {_fmt_count(n_all)} files indexed. "
                            f"Showing {_fmt_count(n_shown)} ({dominant}); other types are in the buttons above."
                        )
                    else:
                        msg = f"Done: {_fmt_count(n_all)} files indexed. Showing {_fmt_count(n_shown)} ({dominant or 'all'})."
                    self.progress_label.setText(msg)
                    t0 = time.perf_counter()
                    self._populate_folder_tree(self._all_rows)
                    t1 = time.perf_counter()
                    self._show_nomenclature()
                    t2 = time.perf_counter()
                    total_wall = time.perf_counter() - getattr(self, "_crawl_start_time", t_gui0)
                    gui_dt = t2 - t_gui0
                    self.log_widget.appendPlainText(
                        f"[total] {total_wall:.3f}s wall | gui post-process: {gui_dt:.3f}s (tree: {t1-t0:.3f}s, nomenclature: {t2-t1:.3f}s)"
                    )
                    if getattr(self, "_crawl_progress", None):
                        self._crawl_progress.close()
                        self._crawl_progress = None
                else:
                    if getattr(self, "_crawl_progress", None):
                        self._crawl_progress.close()
                        self._crawl_progress = None
                    self.progress_label.setText("")
                    QMessageBox.critical(self, "Crawl error", str(payload))
            except queue.Empty:
                pass
        QTimer.singleShot(200, self._poll_queue)

    def _show_nomenclature(self) -> None:
        sugg = suggest_nomenclature(self.rows)
        detected = sugg["detected_fields"]
        root = self.root_edit.text().strip() or None
        detected = _compute_legend_key_order(self.rows, detected, root)
        self._last_detected_keys = detected
        self._update_effective_rows(detected)
        all_dups = set()
        for r in self.rows:
            all_dups.update(r.get("_duplicate_keys", []))
        total, per_key = _schema_consistency(self.rows, detected) if detected else (0, {})
        all_same = all(per_key.get(k, 0) == total for k in detected) if detected else True
        if not all_same:
            self.dup_label.setStyleSheet("color: #f9a825; font-weight: bold; font-size: 10px; padding: 0 4px 0 0;")
            self.dup_label.setText("Warning: schema inconsistent (some files missing parameters). Use 'Include incomplete (fill empty)' to add them.")
        elif all_dups:
            self.dup_label.setStyleSheet("font-size: 10px; padding: 0 4px 0 0;")
            self.dup_label.setText("Info: parameter in folder and filename: " + ", ".join(sorted(all_dups)))
        else:
            self.dup_label.setStyleSheet("font-size: 10px; padding: 0 4px 0 0;")
            self.dup_label.setText("")
        root = self.root_edit.text().strip() or None
        self._legend_key_order = _compute_legend_key_order(self._effective_rows, detected, root)
        self._refresh_key_tree(detected, key_order=self._legend_key_order)
        self._refresh_path_overview()
        self._refresh_unrecognized_panel()
        self._refresh_outlier_panel()

    def _on_confidence_threshold_changed(self, _value: float = 0.0) -> None:
        """Recompute outlier list when the confidence spinner changes."""
        if not getattr(self, "_effective_rows", None):
            return
        self._refresh_outlier_panel()
        if getattr(self, "outlier_only_cb", None) and self.outlier_only_cb.isChecked():
            self._refresh_path_overview()

    def _refresh_outlier_panel(self) -> None:
        """Fill outlier table from schema outliers and typo candidates; update _outlier_relpaths."""
        self._outlier_relpaths = set()
        self.outlier_table.setRowCount(0)
        rows = getattr(self, "_effective_rows", None) or []
        detected = getattr(self, "_last_detected_keys", None) or []
        if not rows:
            return
        thr = (
            float(self.confidence_spin.value())
            if getattr(self, "confidence_spin", None) is not None
            else DEFAULT_CONFIDENCE_THRESHOLD
        )
        schema_outliers = detect_schema_outliers(rows, detected, confidence_threshold=thr)
        typo_candidates = detect_typo_candidates(rows)
        table_rows: list[tuple[str, str, str]] = []
        for r, reason in schema_outliers:
            rel = r.get("relpath") or ""
            if rel:
                self._outlier_relpaths.add(rel)
            table_rows.append((rel, "Schema deviation", reason))
        for rel, _depth, segment, suggested, cnt_a, cnt_s in typo_candidates:
            if rel:
                self._outlier_relpaths.add(rel)
            table_rows.append((rel, "Typo?", f'"{segment}" -> "{suggested}"? (n={cnt_a} vs {cnt_s})'))
        self.outlier_table.setRowCount(len(table_rows))
        for i, (path, art, detail) in enumerate(table_rows):
            self.outlier_table.setItem(i, 0, QTableWidgetItem(path))
            self.outlier_table.setItem(i, 1, QTableWidgetItem(art))
            self.outlier_table.setItem(i, 2, QTableWidgetItem(detail))
        n = len(table_rows)
        self._outlier_count = n
        tri = "\u25B2" if getattr(self, "_outlier_section_visible", False) else "\u25BC"
        self._outlier_toggle_btn.setText(f"Outliers: {n} {tri}")
        self._set_outlier_button_style(n)

    def _refresh_key_tree(self, detected_keys: list, key_order: list | None = None) -> None:
        self.key_tree.blockSignals(True)
        self.key_tree.clear()
        if not detected_keys:
            self.struct_g.setTitle("4. Detected keys (0 files)")
            self.schema_summary_label.setText("")
            self.key_tree.blockSignals(False)
            return
        total, per_key = _schema_consistency(self._effective_rows, detected_keys)
        n_all = len(self._all_rows) if hasattr(self, "_all_rows") else total
        self._update_detected_keys_header()
        stats = _key_stats(self._effective_rows, detected_keys)
        self._suggested_categorical = suggest_categorical_keys(self._effective_rows, threshold=10)
        colors = _KEY_COLORS_LIGHT if self.light_mode_cb.isChecked() else _KEY_COLORS_DARK
        key_order = key_order or getattr(self, "_legend_key_order", None) or detected_keys
        key_to_color = {k: colors[i % len(colors)] for i, k in enumerate(key_order)}
        raw_units: dict[str, str] = {}
        for r in self._effective_rows:
            for k in detected_keys:
                if k in raw_units:
                    continue
                v = r.get(k)
                if v is None:
                    continue
                if is_quantitative_val(v):
                    raw_units[k] = v.get("unit", "")
                    break
                if isinstance(v, list) and v and is_quantitative_val(v[0]):
                    raw_units[k] = v[0].get("unit", "")
                    break
        def _fmt_num(x) -> str:
            if x is None:
                return "-"
            if isinstance(x, float) and x != int(x):
                return f"{x:.2g}"
            return str(int(x))

        # Flat list: one row per key (no category tree). Order by key_order.
        tree_result = build_key_tree(detected_keys, self.key_categories, self.key_display_names, key_order)
        order_idx = {k: i for i, k in enumerate(key_order)}
        all_pairs = [(k, d) for _cat, pairs in tree_result for k, d in pairs]
        all_pairs.sort(key=lambda x: (order_idx.get(x[0], 9999), x[0]))
        for key, display_name in all_pairs:
            s = stats.get(key, {})
            u = s.get("uniques", 0)
            mn, mx, mean = s.get("min"), s.get("max"), s.get("mean")
            min_str = _fmt_num(mn)
            max_str = _fmt_num(mx)
            mean_str = _fmt_num(mean)
            full_count = per_key.get(key, 0)
            missing = total - full_count
            if missing == 0:
                full_str = str(total)
            else:
                full_str = f"{full_count} (−{missing})"
            uniq_str = str(u)
            default_used = u > 1
            is_used = self.key_is_used.get(key, default_used)
            self.key_is_used[key] = is_used
            default_cat = u < 10
            is_cat = self.key_is_categorical.get(key, default_cat)
            self.key_is_categorical[key] = is_cat
            si_exp = self.key_si_scale.get(key)
            has_unit = get_unit_info(key) is not None
            base = SI_BASE_UNIT.get(key, "")
            raw_u = raw_units.get(key, "")
            if si_exp is not None and has_unit:
                unit_text = exponent_to_unit(base, si_exp)
            elif has_unit and raw_u:
                unit_text = raw_u
            else:
                unit_text = "-"
            exp_to_show = si_exp if si_exp is not None else (unit_to_exponent(raw_u) if raw_u and has_unit else None)
            si_text = str(exp_to_show) if exp_to_show is not None else ""
            item = QTreeWidgetItem(
                ["", "", uniq_str, full_str, display_name, key, si_text, unit_text, min_str, max_str, mean_str]
            )
            item.setData(5, Qt.ItemDataRole.UserRole, key)
            item.setData(6, Qt.ItemDataRole.UserRole, has_unit)
            item.setData(7, Qt.ItemDataRole.UserRole, raw_u)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            item.setCheckState(0, Qt.CheckState.Checked if is_used else Qt.CheckState.Unchecked)
            item.setCheckState(1, Qt.CheckState.Checked if is_cat else Qt.CheckState.Unchecked)
            bg = key_to_color.get(key)
            if bg:
                item.setBackground(5, QBrush(QColor(bg)))
            self.key_tree.addTopLevelItem(item)
        self.key_tree.blockSignals(False)
        for c in range(self.key_tree.columnCount()):
            self.key_tree.resizeColumnToContents(c)

    def _on_key_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        key = item.data(5, Qt.ItemDataRole.UserRole)
        if not key:
            return
        if column == 0:
            self.key_is_used[key] = item.checkState(0) == Qt.CheckState.Checked
        elif column == 1:
            self.key_is_categorical[key] = item.checkState(1) == Qt.CheckState.Checked
        elif column == 4:
            display_name = item.text(4).strip()
            self.key_display_names[key] = display_name or key
        elif column == 5:
            item.setText(5, key)
        elif column == 6 and item.data(6, Qt.ItemDataRole.UserRole):
            txt = item.text(6).strip()
            if not txt:
                self.key_si_scale.pop(key, None)
                raw_u = item.data(7, Qt.ItemDataRole.UserRole) or ""
                item.setText(7, raw_u if raw_u else "-")
            else:
                m = re.match(r"10\^(-?\d+)$", txt)
                exp_str = m.group(1) if m else txt  # plain number e.g. -3 or 10^-3
                try:
                    exp = int(exp_str)
                    self.key_si_scale[key] = exp
                    base = SI_BASE_UNIT.get(key, "")
                    item.setText(7, exponent_to_unit(base, exp))
                except ValueError:
                    pass

    def _on_tree_select(self) -> None:
        items = self.key_tree.selectedItems()
        if not items:
            self._refresh_key_samples_label(None)
            return
        item = items[0]
        key = item.data(5, Qt.ItemDataRole.UserRole)
        if key:
            self._refresh_key_samples_label(key)
        else:
            self._refresh_key_samples_label(None)

    def _refresh_key_samples_label(self, key: str | None) -> None:
        """Show sample values for selected key. Called on tree selection or path refresh."""
        if not key:
            self.key_samples_label.setText("")
            self.key_samples_label.setToolTip("Click a key above to see sample values for that parameter.")
            return
        rows = getattr(self, "_effective_rows", None) or []
        if not rows:
            self.key_samples_label.setText(f"Sample values for [{key}]: (no data)")
            return
        vals_seen: set = set()
        samples: list[str] = []
        max_samples = 15
        for r in rows:
            if len(samples) >= max_samples:
                break
            v = r.get(key)
            if v is None:
                continue
            v_display = get_display_value(v, r)
            if is_quantitative_val(v_display):
                s = format_val_unit(v_display)
            elif isinstance(v_display, list) and v_display and is_quantitative_val(v_display[0]):
                s = ", ".join(format_val_unit(x) for x in v_display[:3])
                if len(v_display) > 3:
                    s += ", ..."
            elif isinstance(v_display, (list, dict)):
                s = json.dumps(v_display, sort_keys=True, default=str)[:50]
                if len(s) >= 50:
                    s += "..."
            else:
                s = str(v_display)
            if s not in vals_seen:
                vals_seen.add(s)
                samples.append(s)
        if not samples:
            self.key_samples_label.setText(f"Sample values for [{key}]: (none in current data)")
        else:
            txt = ", ".join(samples)
            if len(rows) > max_samples and len(samples) == max_samples:
                txt += ", ..."
            self.key_samples_label.setText(f"Sample values for [{key}]: {txt}")
        self.key_samples_label.setToolTip(f"Values for parameter {key} in current data.")

    def _get_used_keys(self) -> list | None:
        """Return list of keys that are checked in Used column, or None for all."""
        out: list = []
        for i in range(self.key_tree.topLevelItemCount()):
            item = self.key_tree.topLevelItem(i)
            key = item.data(5, Qt.ItemDataRole.UserRole)
            if key and item.checkState(0) == Qt.CheckState.Checked:
                out.append(key)
        return out if out else None

    def _get_categorical_keys(self) -> list:
        """Return keys checked Cat (TEXT for WOLKE filters). Defaults seeded in _refresh_key_tree."""
        out: list = []
        for i in range(self.key_tree.topLevelItemCount()):
            item = self.key_tree.topLevelItem(i)
            key = item.data(5, Qt.ItemDataRole.UserRole)
            if key and item.checkState(1) == Qt.CheckState.Checked:
                out.append(key)
        return out

    def _refresh_unrecognized_panel(self) -> None:
        """Populate unrecognized token combo and mappings list."""
        self._refreshing_unrec_panel = True
        try:
            self.unrec_token_combo.clear()
            self.unrec_mappings_list.clear()
            rows = getattr(self, "_all_rows", None) or []
            if not rows:
                return
            unrec = _collect_unrecognized_tokens(rows)
            for tok, cnt in unrec:
                self.unrec_token_combo.addItem(f"{tok} ({cnt})", tok)
            for tok, key in sorted(self.custom_token_map.items(), key=lambda x: (x[1], x[0])):
                it = QTreeWidgetItem([tok, key])
                it.setData(0, Qt.ItemDataRole.UserRole, tok)
                it.setData(4, Qt.ItemDataRole.UserRole, key)
                self.unrec_mappings_list.addTopLevelItem(it)
        finally:
            self._refreshing_unrec_panel = False
        self._on_unrec_token_selected()

    def _on_unrec_token_selected(self) -> None:
        """When token selected, pre-fill key edit with suggestion from custom_token_map patterns."""
        if getattr(self, "_refreshing_unrec_panel", False):
            return
        idx = self.unrec_token_combo.currentIndex()
        if idx < 0:
            self.unrec_key_edit.clear()
            return
        tok = self.unrec_token_combo.itemData(idx)
        if not tok:
            return
        suggested = suggest_key_for_token(str(tok), self.custom_token_map)
        self.unrec_key_edit.setText(suggested or "")
        self.unrec_key_edit.setPlaceholderText("key name" + (f" (suggested: {suggested})" if suggested else ""))

    def _add_custom_token_mapping(self) -> None:
        """Add token -> key mapping and refresh."""
        idx = self.unrec_token_combo.currentIndex()
        if idx < 0:
            return
        tok = self.unrec_token_combo.itemData(idx)
        key = self.unrec_key_edit.text().strip()
        if not tok or not key:
            return
        self.custom_token_map[str(tok)] = key
        _apply_custom_token_map(self._all_rows, self.custom_token_map)
        self.rows = filter_rows_by_folder_includes(self._get_ext_filtered_rows(), self._folder_includes)
        self._show_nomenclature()
        self._refresh_unrecognized_panel()
        self.unrec_key_edit.clear()

    def _batch_map_suggested(self) -> None:
        """Map all unrecognized tokens that have a suggestion from existing patterns."""
        rows = getattr(self, "_all_rows", None) or []
        if not rows:
            return
        unrec = _collect_unrecognized_tokens(rows)
        batch = get_batch_suggestions(unrec, self.custom_token_map)
        if not batch:
            QMessageBox.information(
                self,
                "Map all suggested",
                "No unrecognized tokens match existing patterns. Add at least one mapping first (e.g. C1 -> channel).",
            )
            return
        n = len(batch)
        ok = QMessageBox.question(
            self,
            "Map all suggested",
            f"Map {n} token(s) to their suggested keys?\n\n" + "\n".join(f"  {t} -> {k}" for t, k in batch[:10]) + ("\n  ..." if n > 10 else ""),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Ok,
        )
        if ok != QMessageBox.StandardButton.Ok:
            return
        for tok, key in batch:
            self.custom_token_map[str(tok)] = key
        _apply_custom_token_map(self._all_rows, self.custom_token_map)
        self.rows = filter_rows_by_folder_includes(self._get_ext_filtered_rows(), self._folder_includes)
        self._show_nomenclature()
        self._refresh_unrecognized_panel()
        QMessageBox.information(self, "Map all suggested", f"Mapped {n} token(s).")

    def _remove_custom_token_mapping(self) -> None:
        """Remove selected mapping and refresh."""
        items = self.unrec_mappings_list.selectedItems()
        if not items:
            return
        tok = items[0].data(0, Qt.ItemDataRole.UserRole)
        key = items[0].data(5, Qt.ItemDataRole.UserRole)
        if tok and key and tok in self.custom_token_map:
            del self.custom_token_map[tok]
            for row in self._all_rows:
                if row.get(key) == tok:
                    del row[key]
                for ttk in (row.get("_folder_token_to_key") or {}, row.get("_file_token_to_key") or {}):
                    if tok in ttk:
                        del ttk[tok]
            self.rows = filter_rows_by_folder_includes(self._get_ext_filtered_rows(), self._folder_includes)
            self._show_nomenclature()
            self._refresh_unrecognized_panel()

    def _refresh_path_overview(self) -> None:
        """Recompute sample paths from current effective rows and refresh overview."""
        if not getattr(self, "_effective_rows", None):
            if getattr(self, "path_overview", None):
                self.path_overview.clear()
            return
        rows = list(self._effective_rows)
        if getattr(self, "outlier_only_cb", None) and self.outlier_only_cb.isChecked() and getattr(self, "_outlier_relpaths", None):
            rows = [r for r in rows if r.get("relpath") in self._outlier_relpaths]
        folder_idx = getattr(self, "folder_idx_spin", None)
        if folder_idx and folder_idx.value() > 0 and getattr(self, "_folder_list", None):
            idx = folder_idx.value() - 1
            if 0 <= idx < len(self._folder_list):
                target = self._folder_list[idx]
                rows = [r for r in rows if _row_folder(r) == target]
        n = len(rows)
        if not n:
            self._last_sample_rows = []
            self._fill_path_overview([])
            return
        m = min(self.path_sample_spin.value(), n)
        if m <= 1:
            indices = [0] if n else []
        else:
            indices = [(i * (n - 1)) // (m - 1) for i in range(m)]
        sample_rows = [rows[i] for i in indices if i < n]
        self._last_sample_rows = sample_rows
        self._fill_path_overview(sample_rows)

    def _fill_path_overview(self, rows: list) -> None:
        """Show multiple paths with parameter colors, one per line."""
        self.path_overview.clear()
        detected = getattr(self, "_last_detected_keys", None) or []
        if not rows:
            if detected:
                colors = _KEY_COLORS_LIGHT if self.light_mode_cb.isChecked() else _KEY_COLORS_DARK
                key_to_color = {k: colors[i % len(colors)] for i, k in enumerate(detected)}
                legend_parts = [f'<span style="background-color:{c}; padding:0 4px;"> ({k}) </span>' for k, c in [(k, key_to_color[k]) for k in detected]]
                self.color_legend.setTextFormat(Qt.TextFormat.RichText)
                self.color_legend.setText("Parameter → color: " + "  ".join(legend_parts))
            else:
                self.color_legend.setText("")
            self.color_legend.setToolTip(
                "Parameters in brackets: not present in current samples. "
                "Color is stable across folder switches."
            )
            return
        root_dir = self.root_edit.text().strip() or None
        keys_in_samples: set = set()
        for r in rows:
            _, _, _, folder_seg, file_seg, _ = _build_path_segments(r, root_dir)
            keys_in_samples.update(k for _s, _e, k in folder_seg + file_seg)
        detected = getattr(self, "_last_detected_keys", None) or []
        ordered = [k for k in detected] + [k for k in sorted(keys_in_samples) if k not in detected]
        colors = _KEY_COLORS_LIGHT if self.light_mode_cb.isChecked() else _KEY_COLORS_DARK
        key_to_color = {k: colors[i % len(colors)] for i, k in enumerate(ordered)}
        lines: list[str] = []
        segs_per_line: list[list[tuple[int, int, str, bool]]] = []
        dup_per_line: list[set[str]] = []
        sep = "\\" if any("\\" in str(r.get("relpath", "")) for r in rows) else "/"
        for r in rows:
            _, folder_str, file_str, folder_seg, file_seg, keys_dup = _build_path_segments(r, root_dir)
            rel = (folder_str + sep + file_str) if folder_str else file_str
            if not rel:
                rel = r.get("relpath", "")
            lines.append(rel)
            offset_file = len(folder_str) + len(sep) if folder_str else 0
            segs = [(s, e, k, True) for s, e, k in folder_seg]
            segs.extend((offset_file + s, offset_file + e, k, False) for s, e, k in file_seg)
            segs_per_line.append(segs)
            dup_per_line.append(set(keys_dup))
        legend_order = getattr(self, "_legend_key_order", None) or ordered
        unrec_color = "#e0e0e0" if self.light_mode_cb.isChecked() else "#505050"
        neutral_color = "#f0f0f0" if self.light_mode_cb.isChecked() else "#404040"
        self.color_legend.setTextFormat(Qt.TextFormat.RichText)
        pseudopath_html = _build_pseudopath_from_rows(
            rows, root_dir, legend_order, sep, key_to_color, neutral_color, unrec_color
        )
        leg = ("Recognized: " + pseudopath_html) if pseudopath_html else ""
        self.color_legend.setText(leg)
        self.color_legend.setToolTip(
            "Pseudo-path from actual paths. Key names; (key) = key not in all paths. Colors = parameter."
        )
        full = "\n".join(lines)
        self.path_overview.setPlainText(full)
        cursor = self.path_overview.textCursor()
        pos = 0
        for i, line in enumerate(lines):
            segs = segs_per_line[i]
            gaps = _gaps_from_segments(segs, len(line))
            for gap_start, gap_end in gaps:
                for start, end, seg_type in _split_gap_into_segment_types(line, gap_start, gap_end):
                    if seg_type == "rest":
                        fmt = QTextCharFormat()
                        fmt.setBackground(QColor(unrec_color))
                        cursor.setPosition(pos + start)
                        cursor.setPosition(pos + end, cursor.MoveMode.KeepAnchor)
                        cursor.setCharFormat(fmt)
            for start, end, key, in_folder in segs:
                fmt = QTextCharFormat()
                base = key_to_color.get(key, "#ccc")
                if in_folder and key in dup_per_line[i]:
                    c = QColor(base)
                    c.setAlpha(85)
                    fmt.setBackground(c)
                else:
                    fmt.setBackground(QColor(base))
                cursor.setPosition(pos + start)
                cursor.setPosition(pos + end, cursor.MoveMode.KeepAnchor)
                cursor.setCharFormat(fmt)
            pos += len(line) + 1
        block = self.path_overview.document().firstBlock()
        while block.isValid():
            tc = QTextCursor(block)
            fmt = block.blockFormat()
            fmt.setBottomMargin(5)
            tc.setBlockFormat(fmt)
            block = block.next()
        sel_key = None
        tree = getattr(self, "key_tree", None)
        if tree and tree.selectedItems():
            it = tree.selectedItems()[0]
            sel_key = it.data(5, Qt.ItemDataRole.UserRole)
        if sel_key:
            self._refresh_key_samples_label(sel_key)

    def _load_schema_from_db(self) -> None:
        db_path = self.db_edit.text().strip()
        if not db_path or not Path(db_path).is_file():
            QMessageBox.warning(self, "Load schema", "Select an existing DB file first.")
            return
        schema = load_schema_from_db(db_path)
        if not schema:
            QMessageBox.information(self, "Load schema", "No schema found in DB.")
            return
        loaded = []
        if isinstance(schema.get("key_display_names"), dict):
            self.key_display_names = dict(schema["key_display_names"])
            loaded.append("display names")
        if isinstance(schema.get("key_categories"), dict):
            self.key_categories = dict(schema["key_categories"])
            loaded.append("categories")
        if isinstance(schema.get("key_is_categorical"), dict):
            self.key_is_categorical = {k: bool(v) for k, v in schema["key_is_categorical"].items()}
            loaded.append("categorical flags")
        if isinstance(schema.get("key_is_used"), dict):
            self.key_is_used = {k: bool(v) for k, v in schema["key_is_used"].items()}
            loaded.append("used flags")
        ctm = schema.get("custom_token_map")
        if isinstance(ctm, dict):
            for tok, key in list(self.custom_token_map.items()):
                for row in self._all_rows:
                    if row.get(key) == tok:
                        del row[key]
                    for ttk in (row.get("_folder_token_to_key") or {}, row.get("_file_token_to_key") or {}):
                        if tok in ttk:
                            del ttk[tok]
            self.custom_token_map = dict(ctm)
            loaded.append(f"{len(self.custom_token_map)} token mappings")
            if self._all_rows:
                _apply_custom_token_map(self._all_rows, self.custom_token_map)
                self.rows = filter_rows_by_folder_includes(self._get_ext_filtered_rows(), self._folder_includes)
                self._show_nomenclature()
            self._refresh_unrecognized_panel()
        tp = schema.get("token_patterns")
        if isinstance(tp, list):
            self.token_patterns = [dict(p) for p in tp if isinstance(p, dict)]
            if self.token_patterns:
                loaded.append(f"{len(self.token_patterns)} token patterns")
            self._refresh_token_patterns_table()
        if loaded:
            if self._last_detected_keys:
                self._refresh_key_tree(self._last_detected_keys, key_order=getattr(self, "_legend_key_order", None))
            QMessageBox.information(self, "Load schema", "Loaded: " + ", ".join(loaded) + ".")
        else:
            QMessageBox.information(self, "Load schema", "Schema loaded (no display names or token mappings).")

    def _save_to_db(self) -> None:
        self._sync_token_patterns_from_table()
        if not self._effective_rows:
            QMessageBox.warning(self, "No data", "Run a crawl first.")
            return
        root = self.root_edit.text().strip()
        if not root:
            QMessageBox.warning(self, "No root", "Set root folder first.")
            return
        root_path = Path(root).resolve()
        db_path = self.db_edit.text().strip() or str(default_db_path_for_root(root_path))
        db_path_resolved = Path(db_path).resolve()
        try:
            db_path_resolved.relative_to(root_path)
        except ValueError:
            db_path = str(default_db_path_for_root(root_path))
            self.db_edit.setText(db_path)
        config = self._get_config()
        used_keys = self._get_used_keys()
        categorical_keys = self._get_categorical_keys()
        column_si_scale = {k: v for k, v in (getattr(self, "key_si_scale", {}) or {}).items() if v is not None}
        # output_dir must be under root; else use root/_index and fix GUI
        out_raw = self.output_edit.text().strip()
        default_output = str(root_path / "_index")
        try:
            if out_raw:
                out_resolved = Path(out_raw).resolve()
                out_resolved.relative_to(root_path)
                output_dir = out_raw
            else:
                output_dir = default_output
        except (ValueError, OSError):
            output_dir = default_output
        if output_dir == default_output and out_raw != default_output:
            self.output_edit.setText(output_dir)
        # Persist full display names (user overrides + defaults from key_lut) so they appear in DB config
        key_display_names_export = dict(self.key_display_names)
        for k in (used_keys or list(getattr(self, "key_display_names", {}).keys()) or []):
            if k not in key_display_names_export:
                key_display_names_export[k] = get_display_name(k, None) or k
        for k in getattr(self, "_last_detected_keys", []) or []:
            if k not in key_display_names_export:
                key_display_names_export[k] = get_display_name(k, None) or k
        schema = {"root_dir": self.root_edit.text(), "output_dir": output_dir, "db_path": db_path,
                  "table_name": (self.current_config or {}).get("table_name") or "data",
                  "relative_filepath_column": (self.current_config or {}).get("relative_filepath_column") or "relpath",
                  "folder_token_depth": config["folder_token_depth"],
                  "recursive": config["recursive"], "include_hidden": config["include_hidden"],
                  "column_si_scale": column_si_scale,
                  "key_display_names": key_display_names_export, "key_categories": self.key_categories,
                  "key_is_categorical": dict(self.key_is_categorical), "key_is_used": dict(self.key_is_used),
                  "custom_token_map": dict(self.custom_token_map),
                  "token_patterns": list(getattr(self, "token_patterns", []) or [])}
        try:
            t0 = time.perf_counter()
            write_index_to_sqlite(
                self._effective_rows,
                {},
                db_path,
                schema_config=schema,
                used_keys=used_keys,
                categorical_keys=categorical_keys,
            )
            dt = time.perf_counter() - t0
            self.log_widget.appendPlainText(f"[save_db] {dt:.3f}s | {len(self._effective_rows)} rows -> {db_path}")
            QMessageBox.information(self, "DB", f"Saved: {db_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _export_files(self) -> None:
        if not self._effective_rows:
            QMessageBox.warning(self, "No data", "Run a crawl first.")
            return
        out_dir = self.output_edit.text().strip() or str(Path(self.root_edit.text()) / "_index")
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        used_keys = self._get_used_keys()
        column_si_scale = {k: v for k, v in (getattr(self, "key_si_scale", {}) or {}).items() if v is not None}
        try:
            t0 = time.perf_counter()
            write_jsonl(self._effective_rows, out_path / "index.jsonl", used_keys=used_keys, column_si_scale=column_si_scale)
            write_csv(self._effective_rows, out_path / "index.csv", used_keys=used_keys, column_si_scale=column_si_scale)
            meta = build_column_metadata(self._effective_rows, used_keys, column_si_scale)
            if meta:
                write_index_meta(meta, out_path / "index_meta.json")
            dt = time.perf_counter() - t0
            self.log_widget.appendPlainText(f"[export] {dt:.3f}s | {len(self._effective_rows)} rows -> {out_path}")
            QMessageBox.information(self, "Export", f"Exported to:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def closeEvent(self, event) -> None:
        splitter_sizes = ""
        if getattr(self, "save_log_split", None):
            splitter_sizes = ",".join(str(s) for s in self.save_log_split.sizes())
        main_splitter_sizes = ""
        if getattr(self, "bottom_split", None):
            main_splitter_sizes = ",".join(str(s) for s in self.bottom_split.sizes())
        outer_splitter_sizes = ""
        if getattr(self, "outer_split", None):
            outer_splitter_sizes = ",".join(str(s) for s in self.outer_split.sizes())
        thr = (
            float(self.confidence_spin.value())
            if getattr(self, "confidence_spin", None) is not None
            else DEFAULT_CONFIDENCE_THRESHOLD
        )
        save_settings(
            self.size().width(), self.size().height(),
            self.root_edit.text(), self.output_edit.text(), self.db_edit.text(),
            light_mode=self.light_mode_cb.isChecked(),
            splitter_sizes=splitter_sizes,
            main_splitter_sizes=main_splitter_sizes,
            outer_splitter_sizes=outer_splitter_sizes,
            confidence_threshold=thr,
        )
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = DampfGui()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
