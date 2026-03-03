# gui.py - DAMPF GUI (PyQt6): responsive, 800px max, fits Full HD, INI settings.

from __future__ import annotations

import json
import queue
import re
import sys
import threading
from collections import Counter
from pathlib import Path

from indexer import (
    DEFAULT_ALLOWED_SUFFIXES,
    run_indexer,
    group_rows,
    suggest_nomenclature,
    suggest_categorical_keys,
    build_column_metadata,
    write_csv,
    write_index_meta,
    write_jsonl,
)
from db_writer import write_index_to_sqlite
from key_lut import (
    build_key_tree,
    suggest_group_keys_by_category,
    exponent_to_unit,
    format_val_unit,
    get_category,
    get_display_name,
    get_unit_info,
    is_quantitative_val,
    SI_BASE_UNIT,
)
from app_settings import load_settings, save_settings

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QTextBlockFormat, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QCheckBox, QSpinBox,
    QComboBox, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QSplitter, QScrollArea, QFrame, QSizePolicy, QInputDialog, QMessageBox,
    QFileDialog,
)

# Mind. 20 klar unterschiedliche Farben – keine Duplikate fuer verschiedene Parameter
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
"""
STYLESHEET_DARK = """
    QWidget { background-color: #2d323b; color: #e6edf3; }
    QGroupBox { font-weight: bold; }
    QLineEdit, QTextEdit, QComboBox, QSpinBox { background-color: #1e2127; color: #e6edf3; border: 1px solid #444c56; }
    QTreeWidget { background-color: #1e2127; color: #e6edf3; }
"""


def _row_folder(r: dict) -> str:
    """Folder path for row (dirname of relpath)."""
    rel = r.get("relpath", "")
    folder = str(Path(rel).parent).replace("\\", "/") if rel else ""
    return folder if folder != "." else ""


def _build_folder_tree(rows: list) -> dict:
    """Build {path: count} for each folder (dirname of relpath). path uses /."""
    by_folder: dict[str, int] = {}
    for r in rows:
        rel = r.get("relpath", "")
        folder = str(Path(rel).parent).replace("\\", "/") if rel else ""
        if folder == ".":
            folder = ""
        by_folder[folder] = by_folder.get(folder, 0) + 1
    return by_folder


_ROW_META_KEYS = frozenset(
    {"path", "relpath", "ext", "stem", "tokens", "trace", "recognized", "total_tokens",
     "confidence", "_duplicate_keys", "_folder_tokens", "_file_tokens", "_folder_token_to_key", "_file_token_to_key"}
)


def _key_stats(rows: list, keys: list) -> dict:
    """Per key: uniques, numeric -> min/max, else None. Returns {key: {"uniques": N, "min": x, "max": y}}."""
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
            elif isinstance(v, (list, dict)):
                vn = _json.dumps(v, sort_keys=True, default=str)
            else:
                vn = str(v)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    nums.append(float(v))
            vals.append(vn)
        stats[k] = {"uniques": len(set(vals)), "min": min(nums) if nums else None, "max": max(nums) if nums else None}
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


def _filter_to_dominant_suffix(rows: list) -> list:
    if len(rows) <= 1:
        return rows
    ext_counts = Counter(r.get("ext", "") for r in rows if r.get("ext"))
    if not ext_counts:
        return rows
    dominant_ext = ext_counts.most_common(1)[0][0]
    return [r for r in rows if r.get("ext") == dominant_ext] or rows


def _compute_legend_key_order(rows: list, detected_keys: list, root_dir: str | None) -> list:
    """Stable order by typical position in path (left-to-right). Uses avg normalized position."""
    if not rows or not detected_keys:
        return list(detected_keys)
    key_positions: dict[str, list[float]] = {}
    sep = "\\" if any("\\" in str(r.get("relpath", "")) for r in rows) else "/"
    for r in rows:
        _, folder_str, file_str, folder_seg, file_seg, _ = _build_path_segments(r, root_dir)
        rel = (folder_str + sep + file_str) if folder_str else file_str
        if not rel:
            rel = r.get("relpath", "")
        line_len = max(1, len(rel))
        offset_file = len(folder_str) + len(sep) if folder_str else 0
        for s, e, k in folder_seg:
            key_positions.setdefault(k, []).append(s / line_len)
        for s, e, k in file_seg:
            key_positions.setdefault(k, []).append((offset_file + s) / line_len)
    order = sorted(key_positions.keys(), key=lambda k: sum(key_positions[k]) / len(key_positions[k]))
    return order + [k for k in detected_keys if k not in order]


def _key_order_for_colors(detected_keys: list, all_keys: set) -> list:
    """Stable order: detected_keys first (filename order), then extras sorted."""
    order = [k for k in detected_keys if k in all_keys]
    order += sorted(k for k in all_keys if k not in detected_keys)
    return order


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
    for token, key in folder_to_key.items():
        for m in re.finditer(re.escape(token), folder_str, re.IGNORECASE):
            folder_seg.append((m.start(), m.end(), key))
            keys_in_folder.add(key)
    for token, key in file_to_key.items():
        for m in re.finditer(re.escape(token), file_str, re.IGNORECASE):
            file_seg.append((m.start(), m.end(), key))
            keys_in_file.add(key)
    keys_dup = sorted(keys_in_folder & keys_in_file)
    return root_str, folder_str, file_str, folder_seg, file_seg, keys_dup


def _run_indexer_worker(root_dir: str, output_dir: str, config: dict, result_queue: queue.Queue) -> None:
    try:
        rows, groups = run_indexer(root_dir, output_dir, config)
        result_queue.put(("ok", (rows, groups)))
    except Exception as e:
        result_queue.put(("err", str(e)))


class DampfGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DAMPF - Filename Semantic Indexer")
        settings = load_settings()
        self.resize(settings["width"], settings["height"])
        self.setMaximumWidth(settings["max_width"])
        self.setMaximumHeight(settings["max_height"])
        self.setMinimumSize(560, 480)

        self.root_dir = settings.get("root_dir", "")
        self.output_dir = settings.get("output_dir", "")
        self.db_path = settings.get("db_path", "")
        self.group_keys = "date, experiment, sample, run, rep"
        self.folder_depth = 99
        self.recursive = True
        self.include_hidden = False

        self.rows: list = []
        self._all_rows: list = []  # before folder filter
        self._folder_includes: set[str] = set()  # folder paths to include (empty = all)
        self.groups: dict = {}
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

        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setSpacing(6)
        main.setContentsMargins(8, 8, 8, 8)

        # Workflow steps (visible guidance)
        steps = QLabel(
            "1.) Select folder   |   2.) Crawl   |   3.) Include/exclude folders   |   "
            "4.) Check extraction   |   5.) Save to DB / Export"
        )
        steps.setStyleSheet("font-weight: bold; padding: 4px;")
        steps.setWordWrap(True)
        main.addWidget(steps)
        simple_hint = QLabel("Simple: drag folder -> Start Crawl -> Save to DB")
        simple_hint.setStyleSheet("font-size: 11px; padding: 0 4px;")
        main.addWidget(simple_hint)

        # Root
        root_g = QGroupBox("1. Root Folder")
        root_l = QHBoxLayout(root_g)
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Select or drop folder")
        self.root_edit.setText(self.root_dir)
        self.root_edit.setMinimumWidth(140)
        root_l.addWidget(self.root_edit)
        root_l.addWidget(QPushButton("Browse...", clicked=self._browse_root))
        cb_col = QVBoxLayout()
        self.advanced_check = QCheckBox("Show output & DB")
        self.advanced_check.toggled.connect(self._toggle_advanced)
        cb_col.addWidget(self.advanced_check)
        self.light_mode_cb = QCheckBox("Light mode")
        self.light_mode_cb.setChecked(settings.get("light_mode", True))
        self.light_mode_cb.toggled.connect(self._apply_theme)
        cb_col.addWidget(self.light_mode_cb)
        root_l.addLayout(cb_col)
        main.addWidget(root_g)

        # Advanced (hidden by default)
        self.advanced_w = QWidget()
        adv_l = QGridLayout(self.advanced_w)
        adv_l.addWidget(QLabel("Output:"), 0, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setText(self.output_dir)
        adv_l.addWidget(self.output_edit, 0, 1)
        adv_l.addWidget(QPushButton("Browse", clicked=self._browse_output), 0, 2)
        adv_l.addWidget(QLabel("Database:"), 1, 0)
        self.db_edit = QLineEdit()
        self.db_edit.setText(self.db_path)
        adv_l.addWidget(self.db_edit, 1, 1)
        adv_l.addWidget(QPushButton("Browse", clicked=self._browse_db), 1, 2)
        main.addWidget(self.advanced_w)
        self.advanced_w.hide()

        # Crawl
        crawl_g = QGroupBox("2. Crawl")
        crawl_l = QVBoxLayout(crawl_g)
        row1 = QHBoxLayout()
        self.crawl_btn = QPushButton("Start Crawl", clicked=self._start_crawl)
        self.progress_label = QLabel("")
        row1.addWidget(self.crawl_btn)
        row1.addWidget(self.progress_label)
        row1.addStretch()
        crawl_l.addLayout(row1)
        row2 = QHBoxLayout()
        self.recursive_cb = QCheckBox("Recursive")
        self.recursive_cb.setChecked(True)
        self.include_hidden_cb = QCheckBox("Include hidden")
        row2.addWidget(self.recursive_cb)
        row2.addWidget(self.include_hidden_cb)
        self.filter_dominant_cb = QCheckBox("Filter to dominant file type")
        self.filter_dominant_cb.setChecked(True)
        self.filter_dominant_cb.setToolTip("When checked: keep only the most frequent file type (e.g. if 1000 .tif + 4 .csv, keep only .tif). Uncheck to include all.")
        row2.addWidget(self.filter_dominant_cb)
        row2.addWidget(QLabel("Folder depth:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 99)
        self.depth_spin.setValue(99)
        row2.addWidget(self.depth_spin)
        row2.addStretch()
        crawl_l.addLayout(row2)
        gk_row = QHBoxLayout()
        gk_label = QLabel("Group keys:")
        gk_label.setToolTip("Subset of detected keys (4.) that defines how files are grouped in DB. E.g. date+experiment+sample. Different from detected keys: those are ALL extracted params; group keys = which ones form a logical group.")
        gk_row.addWidget(gk_label)
        self.group_keys_edit = QLineEdit()
        self.group_keys_edit.setText(self.group_keys)
        self.group_keys_edit.setPlaceholderText("auto-suggested after crawl; e.g. date, experiment, sample")
        self.group_keys_edit.setToolTip("Parameters that define a logical group. Auto-filled after crawl.")
        gk_row.addWidget(self.group_keys_edit)
        crawl_l.addLayout(gk_row)
        main.addWidget(crawl_g)

        # Folder inclusion tree (after crawl)
        self.folder_tree_g = QGroupBox("3. Include folders (uncheck to exclude, changes apply immediately)")
        folder_tree_l = QVBoxLayout(self.folder_tree_g)
        folder_tree_l.setSpacing(2)
        folder_tree_l.setContentsMargins(4, 8, 4, 4)
        self.folder_tree_w = QTreeWidget()
        self.folder_tree_w.setHeaderLabels(["Idx", "Include", "Folder", "Files"])
        self.folder_tree_w.setToolTip("Uncheck folders to exclude (e.g. RESULTS, output). Changes apply immediately.")
        self.folder_tree_w.setMinimumHeight(130)
        self.folder_tree_w.setMaximumHeight(182)
        self.folder_tree_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.folder_tree_w.itemChanged.connect(self._on_folder_check_changed)
        folder_tree_l.addWidget(self.folder_tree_w, 1)  # stretch 1 = 80%+
        suggest_btn = QPushButton("Suggest exclude (RESULTS, output, ...)", clicked=self._suggest_exclude)
        suggest_btn.setToolTip("Uncheck folders matching: results, output, processed, temp, etc.")
        folder_tree_l.addWidget(suggest_btn, 0)  # no stretch = minimal space
        main.addWidget(self.folder_tree_g)

        # 4. Detected structure (Keys + Path) – schema summary, per-key stats, categorical
        struct_g = QGroupBox("4. Detected keys & path preview")
        struct_g.setStyleSheet("QGroupBox { font-size: 12px; padding-top: 8px; }")
        struct_l = QVBoxLayout(struct_g)
        self.dup_label = QLabel("")
        self.dup_label.setStyleSheet("font-size: 11px; padding: 2px 0;")
        struct_l.addWidget(self.dup_label)
        self.schema_summary_label = QLabel("")
        self.schema_summary_label.setStyleSheet("font-size: 11px; padding: 2px 0;")
        self.schema_summary_label.setToolTip("Shows file count and schema consistency. Outliers = files missing some parameters.")
        struct_l.addWidget(self.schema_summary_label)
        incl_row = QHBoxLayout()
        self.include_incomplete_cb = QCheckBox("Include incomplete (fill with empty)")
        self.include_incomplete_cb.setChecked(True)
        self.include_incomplete_cb.setToolTip("When checked: include all files, fill missing parameters (e.g. CO2, N2) with empty. When unchecked: only files with all parameters.")
        self.include_incomplete_cb.toggled.connect(self._on_include_incomplete_toggled)
        incl_row.addWidget(self.include_incomplete_cb)
        incl_row.addStretch()
        struct_l.addLayout(incl_row)
        # Keys (full width)
        keys_left = QWidget()
        keys_ll = QVBoxLayout(keys_left)
        keys_ll.addWidget(QLabel("Detected keys (click to edit display name; Cat = categorical for filter/container):"))
        self.key_tree = QTreeWidget()
        self.key_tree.setHeaderLabels(["Used", "Key", "Stats", "Uniques", "Cat", "SI exp", "Unit"])
        self.key_tree.setMinimumHeight(100)
        self.key_tree.setMaximumHeight(200)
        self.key_tree.setColumnWidth(0, 60)
        self.key_tree.setColumnWidth(1, 200)
        self.key_tree.setStyleSheet("font-size: 11px;")
        self.key_tree.setToolTip("Used: include in export. Cat: categorical. SI exp: -3=m, 0=base, 6=M (empty=raw). Unit: result unit.")
        self.key_tree.itemSelectionChanged.connect(self._on_tree_select)
        self.key_tree.itemChanged.connect(self._on_key_tree_item_changed)
        keys_ll.addWidget(self.key_tree)
        key_edit_row = QHBoxLayout()
        key_edit_row.addWidget(QLabel("Display name:"))
        self.key_display_edit = QLineEdit()
        self.key_display_edit.setPlaceholderText("Select key in tree, then edit")
        self.key_display_edit.setToolTip("Override how this parameter is shown in exports. Apply to save.")
        key_edit_row.addWidget(self.key_display_edit)
        key_edit_row.addWidget(QPushButton("Apply", clicked=self._apply_display_name))
        key_edit_row.addWidget(QPushButton("Reset", clicked=self._reset_display_name))
        keys_ll.addLayout(key_edit_row)
        struct_l.addWidget(keys_left)
        # Path samples – full overview below keys (colored by parameters)
        path_header = QHBoxLayout()
        path_header.addWidget(QLabel("Path samples:"))
        self.path_sample_spin = QSpinBox()
        self.path_sample_spin.setRange(3, 50)
        self.path_sample_spin.setValue(13)
        self.path_sample_spin.setToolTip("Number of sample paths spread across data")
        self.path_sample_spin.valueChanged.connect(self._refresh_path_overview)
        path_header.addWidget(self.path_sample_spin)
        path_header.addWidget(QLabel("samples"))
        path_header.addWidget(QLabel("Folder (0=random; >0=idx):"))
        self.folder_idx_spin = QSpinBox()
        self.folder_idx_spin.setRange(0, 0)
        self.folder_idx_spin.setToolTip("0 = random file; >0 = folder index")
        self.folder_idx_spin.valueChanged.connect(self._refresh_path_overview)
        path_header.addWidget(self.folder_idx_spin)
        path_header.addStretch()
        struct_l.addLayout(path_header)
        self.color_legend = QLabel("")
        self.color_legend.setWordWrap(True)
        self.color_legend.setStyleSheet("font-size: 11px; padding: 2px 0;")
        struct_l.addWidget(self.color_legend)
        self.path_overview = QTextEdit()
        self.path_overview.setReadOnly(True)
        self.path_overview.setMaximumHeight(180)
        self.path_overview.setFontFamily("Consolas")
        self.path_overview.setStyleSheet("font-size: 10px; padding: 4px;")
        self.path_overview.setToolTip("Overview of sample paths with parameters colored. One path per line.")
        struct_l.addWidget(self.path_overview)
        main.addWidget(struct_g)

        # 5. Save
        refine_g = QGroupBox("5. Save")
        refine_l = QHBoxLayout(refine_g)
        refine_l.addStretch()
        save_btn = QPushButton("Save to DB", clicked=self._save_to_db)
        save_btn.setStyleSheet("font-weight: bold; min-width: 100px;")
        refine_l.addWidget(save_btn)
        refine_l.addWidget(QPushButton("Export JSONL/CSV", clicked=self._export_files))
        main.addWidget(refine_g)

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
                break
            elif p.parent.is_dir():
                self._set_root(str(p.parent.resolve()))
                break

    def _set_root(self, path: str) -> None:
        self.root_edit.setText(path)
        if not self.output_edit.text().strip():
            self.output_edit.setText(str(Path(path) / "_index"))
        if not self.db_edit.text().strip():
            self.db_edit.setText(str(Path(path) / "dampf.db"))

    def _toggle_advanced(self, on: bool) -> None:
        self.advanced_w.setVisible(on)

    def _apply_theme(self) -> None:
        light = self.light_mode_cb.isChecked()
        self.setStyleSheet(STYLESHEET_LIGHT if light else STYLESHEET_DARK)
        if getattr(self, "_last_sample_rows", None):
            self._fill_path_overview(self._last_sample_rows)
        if getattr(self, "_last_detected_keys", None):
            self._refresh_key_tree(self._last_detected_keys)

    def _populate_folder_tree(self, rows: list) -> None:
        by_folder = _build_folder_tree(rows)
        if not by_folder:
            self.folder_tree_w.clear()
            self._folder_tree_ready = False
            return

        def total_count(path: str) -> int:
            if not path:
                return sum(by_folder.values())
            return sum(c for p, c in by_folder.items() if p == path or p.startswith(path + "/"))

        all_paths: set[str] = set()
        for p in by_folder:
            parts = p.split("/") if p else []
            for i in range(1, len(parts) + 1):
                all_paths.add("/".join(parts[:i]))

        path_to_item: dict[str, QTreeWidgetItem] = {}
        sorted_paths = sorted(all_paths)
        path_to_idx = {p: i + 1 for i, p in enumerate(sorted_paths)}
        self.folder_tree_w.clear()
        for path in sorted_paths:
            idx = path_to_idx.get(path, 0)
            parts = path.split("/")
            name = parts[-1] if parts else ""
            parent_path = "/".join(parts[:-1]) if len(parts) > 1 else None
            parent_item = path_to_item.get(parent_path) if parent_path else None
            total = total_count(path)
            item = QTreeWidgetItem([str(idx), "", name, str(total)])
            item.setData(2, Qt.ItemDataRole.UserRole, path)
            item.setCheckState(1, Qt.CheckState.Checked)
            if parent_item:
                parent_item.addChild(item)
            else:
                self.folder_tree_w.addTopLevelItem(item)
            path_to_item[path] = item
        for c in range(self.folder_tree_w.columnCount()):
            self.folder_tree_w.resizeColumnToContents(c)
        self.folder_tree_g.show()
        self._folder_tree_ready = False
        self.folder_tree_w.blockSignals(True)
        self._suggest_exclude()
        self.folder_tree_w.blockSignals(False)
        self._folder_tree_ready = True
        self._apply_folder_selection()

    def _on_folder_check_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 1:
            return
        if not getattr(self, "_folder_tree_ready", False):
            return
        self._apply_folder_selection()

    def _apply_folder_selection(self) -> None:
        included: set[str] = set()
        def collect(it: QTreeWidgetItem) -> None:
            path = it.data(2, Qt.ItemDataRole.UserRole)
            if path is not None and it.checkState(1) == Qt.CheckState.Checked:
                included.add(str(path))
            for i in range(it.childCount()):
                collect(it.child(i))
        for i in range(self.folder_tree_w.topLevelItemCount()):
            collect(self.folder_tree_w.topLevelItem(i))

        if not included:
            included = set(_build_folder_tree(self._all_rows))
        self._folder_includes = included
        self.rows = self._filter_rows_by_folders(self._all_rows, included)
        self._show_nomenclature()

    def _filter_rows_by_folders(self, rows: list, included: set[str]) -> list:
        if not included:
            return rows
        out = []
        for r in rows:
            folder = str(Path(r.get("relpath", "")).parent).replace("\\", "/") if r.get("relpath") else ""
            if folder == ".":
                folder = ""
            if any(folder == p or folder.startswith(p + "/") for p in included):
                out.append(r)
        return out

    def _suggest_exclude(self) -> None:
        exclude_keywords = ("results", "output", "processed", "statistical", "mean", "export", "out", "temp")
        for i in range(self.folder_tree_w.topLevelItemCount()):
            self._suggest_exclude_rec(self.folder_tree_w.topLevelItem(i), exclude_keywords)

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
            config = self._get_config()
            self.groups = group_rows(self._effective_rows, config["group_keys"])
            self._refresh_key_tree(self._last_detected_keys)
            self.schema_summary_label.setText(self._format_schema_summary())
            root = self.root_edit.text().strip() or None
            self._legend_key_order = _compute_legend_key_order(
                self._effective_rows, self._last_detected_keys, root
            )
            self._refresh_path_overview()

    def _format_schema_summary(self) -> str:
        if not self._last_detected_keys:
            return ""
        total = len(self._effective_rows)
        per_key = {k: sum(1 for r in self._effective_rows if r.get(k) is not None) for k in self._last_detected_keys}
        all_same = all(per_key.get(k, 0) == total for k in self._last_detected_keys)
        n_all = len(self.rows)
        txt = f"{total:,} files"
        if n_all != total:
            txt += f" (from {n_all:,} in folders)"
        txt += "; " + ("all same keys" if all_same else "outliers – " + ", ".join(f"{total - per_key.get(k, 0)} missing '{k}'" for k in self._last_detected_keys if per_key.get(k, 0) < total))
        return txt

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
        path, _ = QFileDialog.getSaveFileName(self, "Save database", "", "SQLite DB (*.db)")
        if path:
            self.db_edit.setText(path)

    def _get_config(self) -> dict:
        gk = [x.strip() for x in self.group_keys_edit.text().split(",") if x.strip()]
        return {
            "allowed_suffixes": DEFAULT_ALLOWED_SUFFIXES,
            "folder_token_depth": self.depth_spin.value(),
            "group_keys": tuple(gk) if gk else ("date", "experiment", "sample", "run", "rep"),
            "recursive": self.recursive_cb.isChecked(),
            "include_hidden": self.include_hidden_cb.isChecked(),
        }

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
        config = self._get_config()
        old = self.current_config or {}
        self.current_config = {
            **config, "root_dir": root_dir, "output_dir": output_dir,
            "db_path": self.db_edit.text().strip() or "",
            "table_name": old.get("table_name") or "data",
            "relative_filepath_column": old.get("relative_filepath_column") or "relpath",
        }
        q = queue.Queue()
        t = threading.Thread(target=_run_indexer_worker, args=(root_dir, output_dir, config, q))
        t.daemon = True
        t.start()
        self._crawl_queue = q
        self._crawl_done = False

    def _poll_queue(self) -> None:
        if self._crawl_queue and not self._crawl_done:
            try:
                result = self._crawl_queue.get_nowait()
                status, payload = result
                self._crawl_done = True
                self.crawl_btn.setEnabled(True)
                if status == "ok":
                    raw_rows, _ = payload
                    if self.filter_dominant_cb.isChecked():
                        self._all_rows = _filter_to_dominant_suffix(raw_rows)
                        ext_counts = Counter(r.get("ext", "") for r in raw_rows if r.get("ext"))
                        dominant = ext_counts.most_common(1)[0][0] if ext_counts else ""
                        dominant_count = ext_counts.get(dominant, 0)
                        excluded = [(e, c) for e, c in ext_counts.items() if e != dominant and c > 0]
                        excluded_str = "; excluding " + ", ".join(f"{e}" for e, _ in excluded) if excluded else ""
                        msg = f"Done: {dominant_count} {dominant.upper().lstrip('.') or 'files'} found" + excluded_str
                    else:
                        self._all_rows = list(raw_rows)
                        msg = f"Done: {len(self._all_rows)} files indexed (all types)."
                    self.rows = list(self._all_rows)
                    self._folder_includes = set()
                    self.progress_label.setText(msg)
                    self._populate_folder_tree(self._all_rows)
                    self._show_nomenclature()
                else:
                    self.progress_label.setText("")
                    QMessageBox.critical(self, "Crawl error", str(payload))
            except queue.Empty:
                pass
        QTimer.singleShot(200, self._poll_queue)

    def _show_nomenclature(self) -> None:
        sugg = suggest_nomenclature(self.rows)
        detected = sugg["detected_fields"]
        self._last_detected_keys = detected
        self._update_effective_rows(detected)
        all_dups = set()
        for r in self.rows:
            all_dups.update(r.get("_duplicate_keys", []))
        total, per_key = _schema_consistency(self.rows, detected) if detected else (0, {})
        all_same = all(per_key.get(k, 0) == total for k in detected) if detected else True
        if not all_same:
            self.dup_label.setStyleSheet("color: #c5221f; font-weight: bold; font-size: 11px; padding: 2px 0;")
            self.dup_label.setText("Warning: schema inconsistent (some files missing parameters). Use 'Include incomplete (fill empty)' to add them.")
        elif all_dups:
            self.dup_label.setStyleSheet("font-size: 11px; padding: 2px 0;")
            self.dup_label.setText("Info: parameter in folder and filename: " + ", ".join(sorted(all_dups)))
        else:
            self.dup_label.setStyleSheet("font-size: 11px; padding: 2px 0;")
            self.dup_label.setText("")
        root = self.root_edit.text().strip() or None
        self._legend_key_order = _compute_legend_key_order(self._effective_rows, detected, root)
        self._refresh_key_tree(detected, key_order=self._legend_key_order)
        suggested = suggest_group_keys_by_category(detected, self.key_categories)
        self.group_keys_edit.setText(", ".join(suggested))
        config = self._get_config()
        self.groups = group_rows(self._effective_rows, config["group_keys"])
        if detected:
            self.key_display_edit.setText(get_display_name(detected[0], self.key_display_names))
        self._refresh_path_overview()

    def _refresh_key_tree(self, detected_keys: list, key_order: list | None = None) -> None:
        self.key_tree.blockSignals(True)
        self.key_tree.clear()
        if not detected_keys:
            self.schema_summary_label.setText("")
            self.key_tree.blockSignals(False)
            return
        total, per_key = _schema_consistency(self._effective_rows, detected_keys)
        all_same = all(per_key.get(k, 0) == total for k in detected_keys)
        n_all = len(self._all_rows) if hasattr(self, "_all_rows") else total
        schema_txt = f"{total:,} files"
        if n_all != total:
            schema_txt += f" (from {n_all:,} crawled)"
        schema_txt += "; schema: " + ("all same keys" if all_same else "outliers – " + ", ".join(f"{total - per_key.get(k, 0)} missing '{k}'" for k in detected_keys if per_key.get(k, 0) < total))
        self.schema_summary_label.setText(self._format_schema_summary())
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
                if v is not None and is_quantitative_val(v):
                    raw_units[k] = v.get("unit", "")
                    break
        for cat_label, pairs in build_key_tree(detected_keys, self.key_categories, self.key_display_names, key_order):
            cat_item = QTreeWidgetItem([cat_label, "", "", "", "", "", ""])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.key_tree.addTopLevelItem(cat_item)
            for key, display_name in pairs:
                s = stats.get(key, {})
                u = s.get("uniques", 0)
                mn, mx = s.get("min"), s.get("max")
                if mn is None:
                    stats_str = "-"
                    uniq_str = str(u)
                else:
                    if (isinstance(mn, float) and mn != int(mn)) or (isinstance(mx, float) and mx != int(mx)):
                        stats_str = f"{mn:.2g}-{mx:.2g}"
                    else:
                        stats_str = f"{int(mn)}-{int(mx)}"
                    uniq_str = str(u)
                incl = getattr(self, "include_incomplete_cb", None)
                default_used = incl.isChecked() if incl else (u > 1)
                is_used = self.key_is_used.get(key, default_used)
                is_cat = self.key_is_categorical.get(key, u < 10)
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
                si_text = str(si_exp) if si_exp is not None else ""
                child = QTreeWidgetItem(cat_item, ["", f"{display_name}  [{key}]", stats_str, uniq_str, "", si_text, unit_text])
                child.setData(1, Qt.ItemDataRole.UserRole, key)
                child.setData(5, Qt.ItemDataRole.UserRole, has_unit)
                child.setData(6, Qt.ItemDataRole.UserRole, raw_u)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked if is_used else Qt.CheckState.Unchecked)
                child.setCheckState(4, Qt.CheckState.Checked if is_cat else Qt.CheckState.Unchecked)
                if has_unit:
                    child.setFlags(child.flags() | Qt.ItemFlag.ItemIsEditable)
                bg = key_to_color.get(key)
                if bg:
                    child.setBackground(1, QBrush(QColor(bg)))
            cat_item.setExpanded(True)
        self.key_tree.blockSignals(False)
        for c in range(self.key_tree.columnCount()):
            self.key_tree.resizeColumnToContents(c)

    def _on_key_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if item.childCount() > 0:
            return
        key = item.data(1, Qt.ItemDataRole.UserRole)
        if not key:
            return
        if column == 0:
            self.key_is_used[key] = item.checkState(0) == Qt.CheckState.Checked
        elif column == 4:
            self.key_is_categorical[key] = item.checkState(4) == Qt.CheckState.Checked
        elif column == 5 and item.data(5, Qt.ItemDataRole.UserRole):
            txt = item.text(5).strip()
            if not txt:
                self.key_si_scale.pop(key, None)
                raw_u = item.data(6, Qt.ItemDataRole.UserRole) or ""
                item.setText(6, raw_u if raw_u else "-")
            else:
                try:
                    exp = int(txt)
                    self.key_si_scale[key] = exp
                    base = SI_BASE_UNIT.get(key, "")
                    item.setText(6, exponent_to_unit(base, exp))
                except ValueError:
                    pass

    def _on_tree_select(self) -> None:
        items = self.key_tree.selectedItems()
        if not items:
            return
        item = items[0]
        if item.childCount() > 0:
            return
        key = item.data(1, Qt.ItemDataRole.UserRole)
        if key:
            self.key_display_edit.setText(get_display_name(key, self.key_display_names))

    def _apply_display_name(self) -> None:
        items = self.key_tree.selectedItems()
        if not items or items[0].childCount() > 0:
            return
        key = items[0].data(1, Qt.ItemDataRole.UserRole)
        if not key:
            return
        name = self.key_display_edit.text().strip()
        self.key_display_names[key] = name or key
        self._refresh_key_tree(self._last_detected_keys)

    def _get_used_keys(self) -> list | None:
        """Return list of keys that are checked in Used column, or None for all."""
        out: list = []
        for i in range(self.key_tree.topLevelItemCount()):
            cat = self.key_tree.topLevelItem(i)
            for j in range(cat.childCount()):
                child = cat.child(j)
                key = child.data(1, Qt.ItemDataRole.UserRole)
                if key and child.checkState(0) == Qt.CheckState.Checked:
                    out.append(key)
        return out if out else None

    def _reset_display_name(self) -> None:
        items = self.key_tree.selectedItems()
        if not items or items[0].childCount() > 0:
            return
        key = items[0].data(1, Qt.ItemDataRole.UserRole)
        if not key:
            return
        self.key_display_names.pop(key, None)
        self.key_display_edit.setText(get_display_name(key, None))
        self._refresh_key_tree(self._last_detected_keys)

    def _refresh_path_overview(self) -> None:
        """Recompute sample paths from current effective rows and refresh overview."""
        if not getattr(self, "_effective_rows", None):
            if getattr(self, "path_overview", None):
                self.path_overview.clear()
            return
        rows = list(self._effective_rows)
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
        step = max(1, (n - 1) // m) if n > 1 else 1
        indices = sorted(set(i for i in range(0, n, step)) | ({n - 1} if n > 1 else set()))[:m]
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
        legend_parts = []
        for k in legend_order:
            base = key_to_color.get(k)
            if not base:
                continue
            present = k in keys_in_samples
            label = f"({k})" if not present else k
            legend_parts.append(f'<span style="background-color:{base}; padding:0 4px;"> {label} </span>')
        self.color_legend.setTextFormat(Qt.TextFormat.RichText)
        leg = "Parameter → color: " + "  ".join(legend_parts) if legend_parts else ""
        self.color_legend.setText(leg)
        self.color_legend.setToolTip(
            "Parameters in brackets: not present in current samples. "
            "Color is stable across folder switches."
        )
        full = "\n".join(lines)
        self.path_overview.setPlainText(full)
        cursor = self.path_overview.textCursor()
        pos = 0
        for i, line in enumerate(lines):
            for start, end, key, in_folder in segs_per_line[i]:
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

    def _save_to_db(self) -> None:
        if not self._effective_rows:
            QMessageBox.warning(self, "No data", "Run a crawl first.")
            return
        db_path = self.db_edit.text().strip() or str(Path(self.root_edit.text()) / "dampf.db")
        if not self.db_edit.text().strip():
            self.db_edit.setText(db_path)
        config = self._get_config()
        groups = group_rows(self._effective_rows, config["group_keys"])
        used_keys = self._get_used_keys()
        column_si_scale = {k: v for k, v in (getattr(self, "key_si_scale", {}) or {}).items() if v is not None}
        schema = {"root_dir": self.root_edit.text(), "output_dir": self.output_edit.text(), "db_path": db_path,
                  "table_name": (self.current_config or {}).get("table_name") or "data",
                  "relative_filepath_column": (self.current_config or {}).get("relative_filepath_column") or "relpath",
                  "group_keys": list(config["group_keys"]), "folder_token_depth": config["folder_token_depth"],
                  "recursive": config["recursive"], "include_hidden": config["include_hidden"],
                  "column_si_scale": column_si_scale,
                  "key_display_names": self.key_display_names, "key_categories": self.key_categories,
                  "key_is_categorical": dict(self.key_is_categorical), "key_is_used": dict(self.key_is_used)}
        try:
            write_index_to_sqlite(self._effective_rows, groups, db_path, schema_config=schema, used_keys=used_keys)
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
            write_jsonl(self._effective_rows, out_path / "index.jsonl", used_keys=used_keys, column_si_scale=column_si_scale)
            write_csv(self._effective_rows, out_path / "index.csv", used_keys=used_keys, column_si_scale=column_si_scale)
            meta = build_column_metadata(self._effective_rows, used_keys, column_si_scale)
            if meta:
                write_index_meta(meta, out_path / "index_meta.json")
            (out_path / "groups.json").write_text(json.dumps(self.groups, ensure_ascii=False, indent=2))
            QMessageBox.information(self, "Export", f"Exported to:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def closeEvent(self, event) -> None:
        save_settings(
            self.size().width(), self.size().height(),
            self.root_edit.text(), self.output_edit.text(), self.db_edit.text(),
            light_mode=self.light_mode_cb.isChecked(),
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
