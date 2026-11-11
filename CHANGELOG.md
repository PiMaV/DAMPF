# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

- GitHub Release binaries use branded, versioned names: `DAMPF-vX.Y.Z.exe` (Windows) and `DAMPF-vX.Y.Z-linux-x86_64` (glibc/x86_64; built on Ubuntu).
- Naming docs list `=` as the explicit column form (`plasma=on`, `target=metal-grounded`). A hyphenated name alone does not create a column.

### Fixed

- Indexer follows the naming schema: `_` separates parameters, `-` stays inside one name. `plasma-on` is one token; `2024-02-07` stays a date; a number+unit inside a hyphenated name (`Slit-0p5mm`, `150us-Exposure`) is still read.
- Include-folders (#3): unchecking a parent now cascades to children; step 4 file counts refresh; empty selection no longer silently re-includes everything. Title shows how many files are selected. Checkbox clicks are on/off only (partial is display-only when children differ).

### Removed

## [1.1.0] - 2026-11-11

### Added

- **Cat** checkbox writes selected keys as SQLite TEXT so WOLKE shows them as filters instead of histograms (default when a key has fewer than 10 distinct values).
- Per-column header tooltips on step 4 (Used, Cat, Uniques, Full, and the remaining key columns).
- `.img` is included in the default crawl suffix list (path indexing only; WOLKE/BLITZ still cannot open the format).
- Outlier panel **Min confidence** spinner (default 0.3, stored in `dampf.ini`) so borderline deep-path caches can be quieted without a re-crawl.
- Compact `YYYYMMDDHHMMSS` tokens (and glued prefixes like `IMG20220601093439`) map to `date` + `time`.

### Changed

- Confidence score uses filename tokens only (folders still contribute keys, but deep `Project/…/cache` paths no longer dilute the score).
- Six-digit clock tokens (`HHMMSS`) map to `time` instead of `frame` (date adjacency noted in the parse trace; trailing filename numbers stay `frame`).
- Filename pattern `frame_<channel>_<frame>` (e.g. `frame_004_0000.img`) sets `channel` and `frame`.
- Root `dampf.ini` is gitignored (local paths/window only); shipped template remains `config/dampf.ini` with empty paths.
- README documents what Used, Cat, Uniques, and Full mean in step 4.
- Load schema from DB restores Used and Cat checkboxes.
- After crawl, the type filter tooltip and status line state that all allowed types were indexed while the view defaults to the most common type (other types stay on the filter buttons).
- Naming docs: plain digit tokens are documented as `frame` (not `seq`); cheat sheet lists default crawl suffixes including `.img`.
- Reference `config/dampf.ini` uses empty paths and the default 800×1000 window size.

### Removed

- Optional **Group** column and its `dampf.ini` / schema label storage (labels were never written to the data table).
