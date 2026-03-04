# key_lut.py - LUT for key categories, display names, and units (extensible by user).
# Used for tree view and GROUP_KEYS suggestions by unit/category.
# DAMPF defines the schema; WOLKE/BLITZ consume it.

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# --- Units-LUT: key -> (SI base unit, typical prefixes, short label) ---
# Enthaelt alle geaengigten Versionen und SI-Prefixe.
UNITS_LUT: Dict[str, Tuple[str, Tuple[str, ...], str]] = {
    "voltage": ("V", ("uV", "mV", "V", "kV"), "Voltage"),
    "current": ("A", ("uA", "mA", "A"), "Current"),
    "frequency": ("Hz", ("Hz", "kHz", "MHz", "GHz"), "Frequency"),
    "exposure": ("s", ("ns", "us", "ms", "s"), "Exposure"),
    "length": ("m", ("nm", "um", "mm", "cm", "m", "px"), "Length"),
    "lengths": ("m", ("nm", "um", "mm", "cm", "m", "px"), "Length"),
    "temperature": ("C", ("C", "K"), "Temperature"),
    "gas_pct": ("%", ("%",), "Gas"),  # He, N2, CO2 etc.
}

# Gas keys (Zahl+Buchstabe wie 300He, 300N2) -> unit %
GAS_KEYS = frozenset({"he", "n2", "co2"})

def unit_scale(unit: str) -> float:
    """Multiplikator um von unit zu SI zu kommen (z.B. us->1e-6)."""
    u = unit.lower().replace("µ", "u")
    scales = {
        "ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1.0,
        "hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9,
        "uv": 1e-6, "mv": 1e-3, "v": 1.0, "kv": 1e3,
        "ua": 1e-6, "ma": 1e-3, "a": 1.0,
        "nm": 1e-9, "um": 1e-6, "µm": 1e-6, "mm": 1e-3, "cm": 1e-2, "m": 1.0, "px": 1.0,
        "c": 1.0, "°c": 1.0, "k": 1.0,
    }
    return scales.get(u, 1.0)


def convert_val_to_si(val: float, unit: str) -> float:
    """Konvertiert Wert in SI-Basiseinheit."""
    return val * unit_scale(unit)


# SI-Exponent -> Prefix (-3=m, 6=M, etc.)
SI_EXPONENT_PREFIX: Dict[int, str] = {
    -12: "p", -9: "n", -6: "u", -3: "m", 0: "",
    3: "k", 6: "M", 9: "G", 12: "T",
}

# unit_scale liefert 10^exp; Mapping unit -> exponent fuer raw
def unit_to_exponent(unit: str) -> int:
    """Exponent (log10 des Skalenfaktors): us->-6, s->0, km->3."""
    import math
    sc = unit_scale(unit)
    if sc <= 0:
        return 0
    return round(math.log10(sc))


def exponent_to_unit(base_unit: str, exp: int) -> str:
    """z.B. exponent_to_unit('s', -3) -> 'ms'; exp 0 -> base."""
    pre = SI_EXPONENT_PREFIX.get(exp, "")
    if base_unit == "%":
        return "%"
    return pre + base_unit


# SI-Basiseinheit pro Key (fuer Konvertierung)
SI_BASE_UNIT: Dict[str, str] = {
    "exposure": "s",
    "voltage": "v",
    "current": "a",
    "freq": "hz",
    "temp": "c",
    "length": "m",
    "lengths": "m",
    "he": "%",
    "n2": "%",
    "co2": "%",
}

# Key -> category label (for tree grouping). User can extend via project.json "key_categories".
DEFAULT_KEY_CATEGORIES: Dict[str, str] = {
    "date": "Date",
    "run": "Run",
    "rep": "Repetition",
    "trial": "Trial",
    "frame": "Frame / Index",
    "camera": "Camera",
    "channel": "Channel",
    "roi": "ROI",
    "modality": "Modality",
    "processing": "Processing",
    "lengths": "Length",
    "exposure": "Exposure",
    "temp": "Temperature",
    "freq": "Frequency",
    "voltage": "Voltage",
    "current": "Current",
    "he": "Gas",
    "n2": "Gas",
    "co2": "Gas",
    "experiment": "Experiment",
    "sample": "Sample",
    "seq": "Sequence",
    "m": "Parameter",
    "ff": "Parameter",
}

# Key -> suggested display name. User can override in GUI / project.json "key_display_names".
# Fuer quantitative Keys: Display wird mit unit ergaenzt via get_display_name(key, unit).
DEFAULT_KEY_DISPLAY_NAMES: Dict[str, str] = {
    "lengths": "Length",
    "exposure": "Exposure",
    "temp": "Temperature",
    "freq": "Frequency",
    "voltage": "Voltage",
    "current": "Current",
    "he": "He (%)",
    "n2": "N2 (%)",
    "co2": "CO2 (%)",
    "m": "Parameter M",
    "ff": "FF",
    "frame": "Frame",
    "seq": "Sequence",
    "date": "Date",
    "run": "Run",
    "rep": "Rep",
    "sample": "Sample",
    "experiment": "Experiment",
}

# Legacy: map old keys to new (fuer Rueckwaertskompatibilitaet)
_LEGACY_KEY_MAP = {
    "exposure_s": "exposure",
    "exposure_us": "exposure",
    "temp_C": "temp",
    "freq_Hz": "freq",
    "voltage_V": "voltage",
    "current_A": "current",
}


def _normalize_key(key: str) -> str:
    """Gibt neuen Key zurueck falls Legacy-Mapping existiert."""
    return _LEGACY_KEY_MAP.get(key, key)


def get_category(key: str, key_categories: Dict[str, str] | None = None) -> str:
    k = _normalize_key(key)
    lut = key_categories or {}
    return lut.get(k) or lut.get(key) or DEFAULT_KEY_CATEGORIES.get(k) or DEFAULT_KEY_CATEGORIES.get(key) or "Other"


def get_display_name(key: str, key_display_names: Dict[str, str] | None = None, unit: Optional[str] = None) -> str:
    """Display-Name fuer Key. Wenn unit gegeben und Key quantitativ: z.B. 'Exposure (us)'."""
    k = _normalize_key(key)
    lut = key_display_names or {}
    base = lut.get(k) or lut.get(key) or DEFAULT_KEY_DISPLAY_NAMES.get(k) or DEFAULT_KEY_DISPLAY_NAMES.get(key) or key
    if unit and k in UNITS_LUT:
        return f"{base} ({unit})"
    return base


def get_unit_info(key: str) -> Optional[Tuple[str, Tuple[str, ...], str]]:
    """Gibt (si_base, prefixe, label) fuer Key oder None (quantitative Keys)."""
    k = _normalize_key(key)
    if k in UNITS_LUT:
        return UNITS_LUT[k]
    if k in GAS_KEYS:
        return UNITS_LUT["gas_pct"]
    return None


def is_quantitative_val(v: Any) -> bool:
    """True wenn v ein val+unit Dict ist ({"val": x, "unit": "us"})."""
    return isinstance(v, dict) and "val" in v and "unit" in v


def extract_val_for_export(v: Any) -> Any:
    """Fuer DB/CSV: bei val+unit Dict nur den numerischen Wert liefern."""
    if is_quantitative_val(v):
        return v.get("val")
    return v


def get_export_value_and_metadata(
    v: Any,
    key: str,
    column_si_scale: Dict[str, int] | None,
) -> tuple[Any, str, str]:
    """
    (val_to_write, unit_for_meta, raw_unit).
    column_si_scale: key -> exponent (-3=m, 0=base, 6=M). None/fehlend = raw behalten.
    Bei lengths (Liste von val+unit): nimmt erstes Element, Spalte = nur Numeric; Unit in Metadaten.
    """
    if isinstance(v, list) and v and is_quantitative_val(v[0]):
        v = v[0]
    if not is_quantitative_val(v):
        return (v, "", "")
    val, raw_unit = float(v.get("val", 0)), v.get("unit", "")
    base = SI_BASE_UNIT.get(key, raw_unit)
    exp_user = column_si_scale.get(key) if column_si_scale else None
    if exp_user is not None:
        val_si = convert_val_to_si(val, raw_unit)
        val_out = val_si / (10 ** exp_user)
        unit_out = exponent_to_unit(base, exp_user)
        return (val_out, unit_out, raw_unit)
    return (val, raw_unit, raw_unit)


def format_val_unit(v: Any) -> str:
    """Formatierung fuer Anzeige: '500 us' oder einfacher Wert."""
    if is_quantitative_val(v):
        val, unit = v.get("val"), v.get("unit", "")
        return f"{val} {unit}" if unit else str(val)
    return str(v) if v is not None else ""


def build_key_tree(
    detected_keys: List[str],
    key_categories: Dict[str, str] | None = None,
    key_display_names: Dict[str, str] | None = None,
    key_order: List[str] | None = None,
) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """
    Returns list of (category_label, [(key, display_name), ...]) for TreeView.
    Sorted by category order; keys within category by key_order (path position) if given.
    """
    cat_order = ("Date", "Experiment", "Sample", "Run", "Repetition", "Trial", "Sequence", "Frame / Index",
                 "Parameter", "Length", "Exposure", "Temperature", "Frequency", "Voltage", "Current", "Gas",
                 "Camera", "Channel", "ROI", "Modality", "Processing", "Other")
    by_cat: Dict[str, List[Tuple[str, str]]] = {}
    seen_keys: set[str] = set()
    order_idx = {k: i for i, k in enumerate(key_order)} if key_order else {}
    for k in detected_keys:
        norm = _normalize_key(k)
        if norm in seen_keys and norm != k:
            continue
        seen_keys.add(norm)
        cat = get_category(norm, key_categories)
        disp = get_display_name(norm, key_display_names)
        by_cat.setdefault(cat, []).append((norm, disp))
    for v in by_cat.values():
        v.sort(key=lambda x: (order_idx.get(x[0], 9999), x[0]))
    out: List[Tuple[str, List[Tuple[str, str]]]] = []
    cat_order_list = list(cat_order)
    if order_idx:
        cat_min_order = {}
        for c, pairs in by_cat.items():
            idxs = [order_idx.get(p[0], 9999) for p in pairs]
            cat_min_order[c] = min(idxs) if idxs else 9999
        def _cat_sort_key(c: str) -> tuple:
            return (cat_min_order.get(c, 9999), cat_order_list.index(c) if c in cat_order_list else 9999)
        ordered_cats = sorted(by_cat.keys(), key=_cat_sort_key)
    else:
        ordered_cats = [c for c in cat_order if c in by_cat]
        ordered_cats += sorted(c for c in by_cat.keys() if c not in cat_order)
    for c in ordered_cats:
        if c in by_cat:
            out.append((c, by_cat[c]))
    return out


def suggest_group_keys_by_category(
    detected_keys: List[str],
    key_categories: Dict[str, str] | None = None,
) -> List[str]:
    """Suggest GROUP_KEYS order: by category priority, then by key."""
    tree = build_key_tree(detected_keys, key_categories, None)
    out: List[str] = []
    for _cat, pairs in tree:
        for k, _ in pairs:
            out.append(k)
    return out
