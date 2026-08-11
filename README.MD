# DAMPF — Data Aggregation & Modular Processing Framework

## TL;DR

Converts raw folder-based datasets into a structured **SQLite database** (and optional CSV/JSON exports) for querying, filtering, and analysis — usable standalone or as part of the WETTER framework.

## WETTER Framework

[![Landing Page](https://img.shields.io/badge/WETTER-Landing_Page-0a0f14?style=flat-square)](https://wetter.mess.engineering)
[![DAMPF](https://img.shields.io/badge/DAMPF-Indexing-00fff2?style=flat-square)](https://github.com/PiMaV/DAMPF)
[![KEIM](https://img.shields.io/badge/KEIM-Inference-9ccc65?style=flat-square)](https://github.com/PiMaV/KEIM)
[![WOLKE](https://img.shields.io/badge/WOLKE-Web_Explorer-lightgrey?style=flat-square)](https://github.com/PiMaV/WOLKE)
[![BLITZ](https://img.shields.io/badge/BLITZ-Image_Explorer-ff5a4f?style=flat-square)](https://github.com/PiMaV/BLITZ)

This project is part of the **WETTER framework**, a modular toolkit for structured processing, analysis, and exploration of scientific imaging datasets.

**Pipeline:** `Raw Data → DAMPF → KEIM → WOLKE → BLITZ`

At its core, WETTER operates on a **structured SQLite dataset**:  
DAMPF converts raw file-based archives into a queryable database, which is then extended (KEIM), explored (WOLKE), and visualized (BLITZ).

The central entry point, ecosystem overview, and module navigation are available here:  
**[wetter.mess.engineering](https://wetter.mess.engineering)**

### Modules at a glance

- **DAMPF — Data Aggregation & Modular Processing Framework**  
  Semantic indexing of file and folder structures into a structured SQLite dataset (primary data source).

- **KEIM — Knowledge Extraction & Inference Module**  
  Scalar statistics, feature extraction, and analytical evaluation on top of the indexed dataset.

- **WOLKE — Web-Oriented Layout for Knowledge Exploration**  
  Browser-based exploration of structured metadata with filtering, selection, and dataset navigation.

- **BLITZ — Bulk Loading and Interactive Time series Zonal analysis**  
  High-performance interactive visualization and analysis of selected data.

---

## What is DAMPF

> **DAMPF is the entry point of the WETTER pipeline.**  
> It performs semantic indexing of file and folder structures and produces a **SQLite database** as its primary output: one row per file, typed columns, and supporting tables (`column_metadata`, optional `config`).
> This turns raw archives into **structured metadata that can be queried, filtered, and used programmatically** (WOLKE, BLITZ, scripts).

---

![DAMPF GUI](docs/images/Screenshot_GUI_Example.png)

---

## Purpose

DAMPF automatically structures large collections of measurement files based on folder and file naming conventions.

Semantic information such as date, run number, temperature, exposure time, camera ID, sample name, or modality is extracted from paths and filenames and mapped into a uniform schema.

The resulting dataset can be explored and analyzed by other tools in the WETTER ecosystem.

**Typical use cases:**
- Scientific image data (PNG, TIFF, JPG)
- NumPy arrays (NPY, NPZ)
- CSV/text measurement data
- HDF5 files
- Mixed folder structures with experimental parameters in the path

---

## Indexing Pipeline

1. **Folder scan**
   - Recursive
   - Filter on defined file types

2. **Tokenization**
   - Split on `_ - . /`
   - Split at letter↔digit boundaries
   - Include folder names

3. **Rule-based parsing**
   - Date detection (ISO, compact)
   - Run / Rep / Trial
   - Camera / Channel / ROI / Frame
   - Exposure (ns, us, ms, s)
   - Temperature (°C, K)
   - Frequency, voltage, current
   - Modality tags
   - Processing tags (raw, dark, flat, avg, ...)

4. **Structured schema**

```json
{
  "date": "2026-02-28",
  "run": 3,
  "temp": {"val": 20.0, "unit": "c"},
  "exposure": {"val": 2.0, "unit": "us"},
  "camera": 1,
  "modality": "ir",
  "processing": ["raw"],
  "path": "...",
  "confidence": 0.93
}
```

5. **Structured output**

* **SQLite (primary for WETTER tools):** one row per file in the `data` table, plus `column_metadata` and optional `config`.  
* **Optional ASCII exports:** `index.jsonl`, `index.csv`, `index_meta.json` for quick inspection, spreadsheets, or diffs.

Step 5 details match the **Output** section below (defaults, tables, column layout).

---

## Configuration

The GUI still reads and writes `dampf.ini` next to the executable (frozen) or in the current working directory (dev). A reference copy of the default layout is in [`config/dampf.ini`](config/dampf.ini).

**CLI:**
Adjust in `app/dampf/filename_semantic_indexer.py`:
`ROOT_DIR`, `OUTPUT_DIR`, `ALLOWED_SUFFIXES`, `FOLDER_TOKEN_DEPTH`. That script writes JSONL/CSV only; for SQLite use the GUI **Save to DB** or call `write_index_to_sqlite` from code.

**GUI:**

* Set crawl **root** and **output** folder (default export folder: `root/_index`)
* Set **database** path (default: `root/<root_folder_name>.db`, same rule as `default_db_path_for_root` in `app/dampf/db_writer.py`)
* Save schema as `project.json` / `project.ini`
* Reload via “Load root according to schema”

**Naming conventions:**

* [Naming_Cheat_Sheet.md](docs/naming/Naming_Cheat_Sheet.md)
* [Proper_file_naming.md](docs/naming/Proper_file_naming.md) (DE)
* [Proper_file_naming_EN.md](docs/naming/Proper_file_naming_EN.md) (EN)

---

## GUI and standalone binary

* **Start:** `uv run dampf`, or `python -m dampf.gui` (with `app` on `PYTHONPATH`, e.g. `set PYTHONPATH=app` before `python`), or `dist/DAMPF.exe` (Windows) / `dist/DAMPF` (Linux)

* **Workflow:**
  Root folder → Crawl → Adjust nomenclature → Save schema → **Save to DB** (primary) → optional **Export JSONL/CSV** to `_index` (or chosen output folder)

* **Schema handling:**
  Save as `project.json` / `project.ini`
  Reapply to new datasets

* **Outlier detection:**

  * Identifies inconsistent paths / typos
  * Suggests corrections
  * Optional filtered view (“Outliers only”)

* **Build binary:**
  `uv run python scripts/build_exe.py` → `dist/DAMPF.exe` (Windows) or `dist/DAMPF` (Linux). Tag `v*` on GitHub also publishes `DAMPF-linux-x86_64`.

Outputs integrate directly with:

* **WOLKE** (metadata exploration)
* **BLITZ** (image visualization)

---

## Output

Each indexed file corresponds to one row in the primary store (SQLite `data` table).

* **SQLite (primary handoff for WOLKE / BLITZ):** path is user-configurable; GUI default matches `default_db_path_for_root` in `app/dampf/db_writer.py` (`<crawl_root>/<root_folder_name>.db`, with sanitization and fallbacks).

  * `data` table (values)
  * `column_metadata` (units, traceability)
  * optional `config`

* **Optional ASCII exports** in the output folder (default `root/_index/`):

  * `index.jsonl` — line-based, machine-readable
  * `index.csv` — spreadsheet-friendly
  * `index_meta.json` — column metadata (units, raw units)

Includes:

* numeric-only value columns
* separate unit storage
* confidence score per file

---

## Why rule-based?

File naming is typically semi-structured. Rule-based parsing is:

* deterministic
* reproducible
* fast
* easy to debug

ML/LLM approaches are useful when:

* naming conventions vary strongly
* ambiguities increase
* adaptive parsing is required

The baseline is intentionally deterministic.

---

## Extension

* Add regex rules
* Add domain-specific tokens
* Refine confidence scoring
* Optional: ML fallback for unknown tokens

---

## About

Developed and maintained by  
[M.E.S.S. — Mattern Engineering & Software Solutions](https://mess.engineering)

Parts of this work were influenced by prior research activities in an academic context, including work at [INP Greifswald](https://www.inp-greifswald.de).