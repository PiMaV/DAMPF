# naming_rules.py - shipped naming rubrics written into dampf.ini.
# The indexer does not own these lists. The *.user sections are what a crawl uses.

from __future__ import annotations

# Suffix on a number -> column. Longest suffix wins (us before s, kv before v).
PREDEFINED_UNITS: dict[str, str] = {
    "ns": "exposure",
    "us": "exposure",
    "ms": "exposure",
    "s": "exposure",
    "kv": "voltage",
    "v": "voltage",
    "mv": "voltage",
    "uv": "voltage",
    "mm": "lengths",
    "nm": "lengths",
    "um": "lengths",
    "cm": "lengths",
    "m": "lengths",
    "px": "lengths",
    "c": "temp",
    "k": "temp",
    "hz": "freq",
    "khz": "freq",
    "mhz": "freq",
    "ghz": "freq",
    "a": "current",
    "ma": "current",
    "ua": "current",
}

# Token in the filename -> value stored in the modality column.
PREDEFINED_MODALITY: dict[str, str] = {
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

# Word in the filename -> one entry in the processing column.
PREDEFINED_PROCESSING: tuple[str, ...] = (
    "raw",
    "dark",
    "flat",
    "cal",
    "calib",
    "ref",
    "reference",
    "bg",
    "background",
    "mean",
    "avg",
    "median",
    "sum",
    "diff",
    "sub",
    "subtract",
    "norm",
    "normalized",
    "aligned",
    "registered",
    "denoise",
    "filtered",
)
