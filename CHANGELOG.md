# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [1.1.0] - 2026-11-10

### Added

- **Cat** checkbox writes selected keys as SQLite TEXT so WOLKE shows them as filters instead of histograms (default when a key has fewer than 10 distinct values).
- Per-column header tooltips on step 4 (Used, Cat, Uniques, Full, and the remaining key columns).
- `.img` is included in the default crawl suffix list (path indexing only; WOLKE/BLITZ still cannot open the format).
- Outlier panel **Min confidence** spinner (default 0.3, stored in `dampf.ini`) so borderline deep-path caches can be quieted without a re-crawl.

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
