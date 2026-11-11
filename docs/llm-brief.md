# DAMPF — LLM brief

Machine-oriented product picture for agents. Humans use [README.md](../README.md): download the GitHub Release binary, `chmod +x` on Linux, run, set root → Crawl → **Save to DB**.

Brand names stay uppercase English: **WETTER**, **WOLKE**, **DAMPF**, **KEIM**, **BLITZ**, **DONNER**.

## Boundary

DAMPF is a **PyQt6 desktop indexer**. It crawls a folder tree, tokenizes path and filename segments, maps them to typed keys with a rule-based parser, and writes a **SQLite** database (primary handoff for WOLKE / BLITZ / KEIM). Optional JSONL/CSV exports exist for inspection.

Pipeline: `Raw → DAMPF → KEIM → WOLKE → BLITZ`

Product stance: local single-user GUI + optional CLI indexer script. Deterministic rules, not ML. Domain-specific tokens go through `key=value` naming, `custom_token_map`, or user `token_patterns` — not hardcoded product names in the parser.

## Do

- GUI entry: `uv run dampf` / `python -m dampf.gui` (package under `app/dampf`, `pythonpath = ["app"]` in pytest) / release binary `DAMPF-vX.Y.Z.exe` or `DAMPF-vX.Y.Z-linux-x86_64`.
- Default DB path: `<crawl_root>/<root_folder_name>.db` via `default_db_path_for_root` in `db_writer.py`.
- Default ASCII export folder: `root/_index` (`index.jsonl`, `index.csv`, `index_meta.json`).
- Local UI state in `dampf.ini` next to the executable (frozen) or CWD (dev); gitignored. Template: `config/dampf.ini`. Window, paths, and the naming rubrics (units, modality, processing). Each rubric has a `*.predefined` block (rewritten from `naming_rules.py` on save) and a `*.user` block (what the crawl uses; the user may delete rows).
- Schema save/load: `project.json` / `project.ini` and Load schema from DB (`schema_io.py`, `load_schema_from_db`).
- Step 4: **Used** selects export columns; **Cat** forces TEXT for WOLKE filters (default when fewer than 10 distinct values).
- **How to name…** shows [naming/cheat_sheet_v2.md](naming/cheat_sheet_v2.md) and [naming/file_names_explained_v2.md](naming/file_names_explained_v2.md). Those files are bundled in the release binary (`docs/naming/` next to the icon). Do not keep a second copy of the rules in the GUI source. Three character rules stay in the indexer: `_` separates, `-` glues a name, `=` defines name and value.

## Don't

- Do not put Python / uv / PyInstaller install paths on the README front page.
- Do not call `=` a column in the human naming pages. The words there are number and category. The pages are three short rules (`_` separates, `-` glues, `=` defines) plus examples.
- Do not treat a 2–4 letter token as its own column. That heuristic is removed. A word becomes a category through `name=value`, or through a user-block row.
- Do not hardcode unit, modality, or processing lists in the indexer. They live in `dampf.ini` (`naming_rules.py` is only the shipped predefined block).
- Do not revive Group Keys / `groups.json` / per-key Group column (removed in 1.1.0).
- Do not treat plain digit tokens as `seq` in docs; user-facing convention is `frame` (internal reassignment may still normalize minority `seq` → `frame`).
- Do not invent a learning / ML fallback as the product path; Advanced tools stay optional and folded.
- Do not commit machine-local `dampf.ini` paths.

## Output contract

| Store | Content |
|-------|---------|
| SQLite `data` | One row per file; path relative to DB directory; typed columns |
| SQLite `column_metadata` | Units / display metadata |
| SQLite `config` (optional) | Schema bits (modality_map, stopwords, token_patterns, custom_token_map, …) |
| JSONL/CSV (optional) | Same rows for spreadsheets / diffs |

Internal row keys (`path`, `tokens`, `trace`, `confidence`, `_file_tokens`, …) are stripped from the contract table (`ROW_META_KEYS` in `db_writer.py`).

## Parsing order

Built-in regex rules → user **`token_patterns`** (regex → key) → exact **`custom_token_map`**. Tokens are lowercased in the pipeline. Confidence uses filename tokens only (folders still contribute keys).

`token_patterns` entry shape: `{"key", "regex", "extract", "priority"}`. Extract types: `int`, `str`, `val_unit`, `date_short_YY`, `date_short_DM`. Short dates like `22_01_26` are only via a user pattern (YY vs DM).

Outliers: schema deviation / typo candidates in Results; Min confidence spinner (default 0.3) in `dampf.ini`.

A new unit (for example `sccm`) is a parser change in `indexer.py` (`RE_NUMBER_UNIT`, the matching `RE_*`, `unit_scale()`, `parse_tokens()`), not a fourth naming rule.

## Key paths

| Path | Role |
|------|------|
| `app/dampf/gui.py` | Qt UI, crawl, Advanced (token_patterns + unrecognized map), Save to DB |
| `app/dampf/indexer.py` | Tokenize + parse + `run_indexer` |
| `app/dampf/db_writer.py` | SQLite write + default DB path |
| `app/dampf/schema_io.py` | DEFAULT_SCHEMA, project.ini/json |
| `app/dampf/key_lut.py` | Display names, units, export value helpers |
| `app/dampf/outlier_detection.py` | Path outliers |
| `app/dampf/filename_semantic_indexer.py` | CLI JSONL/CSV helper (`dampf-index`); edit constants for one-off runs |
| `app/dampf/app_settings.py` | `dampf.ini` window/paths |
| `config/dampf.ini` | Shipped empty-path template |
| `scripts/build_exe.py` | PyInstaller local binary |
| `.github/workflows/ci.yml` | pytest on push to `main` |
| `.github/workflows/release.yml` | Tag `v*` → versioned Windows + Linux binaries |

## Build and release

Local binary:

```bash
uv sync --extra dev
uv run python scripts/build_exe.py
```

→ `dist/DAMPF.exe` (Windows) or `dist/DAMPF` (Linux). Icons from `icon/`.

Release: `pyproject.toml` `version` must match the tag. Push tag `vX.Y.Z` (current `v1.2.1`) on the commit that has that version → Actions **Release** publishes `DAMPF-vX.Y.Z.exe` and `DAMPF-vX.Y.Z-linux-x86_64`. The Linux job is pinned to `ubuntu-24.04` so the onefile binary does not require glibc 2.43. Do not move it to `ubuntu-latest` while that label is Ubuntu 26. Push to `main` alone runs CI only.

Linux runtime needs usual Qt/X11 libs for PyQt6 (`libxcb-cursor0`, `libxkbcommon-x11-0`, `libegl1`, `libgl1`, …).

## Version

`pyproject.toml` version must match changelog headings and release tags. See [CHANGELOG.md](../CHANGELOG.md).
