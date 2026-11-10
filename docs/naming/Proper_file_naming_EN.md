# Proper Path and File Names

Conventions for paths and filenames; the **DAMPF Indexer** ([../../app/dampf/indexer.py](../../app/dampf/indexer.py)) is tuned to these patterns.

**Quick ref:** [Naming_Cheat_Sheet.md](Naming_Cheat_Sheet.md) | **Deutsch:** [Proper_file_naming.md](Proper_file_naming.md)

---

## Quick Start (4 Rules)

1. **Separators:** `_` (underscore) or `-` (dash), never spaces
2. **Unit directly to number** (no space): `4kV`, `10us`, `0p2us`
3. **Decimal:** `p` preferred (0p2us), dot `.` also supported (0.2us)
4. **Example:** `2024-02-07_run1_4kV_10us_001.png` → date, run, voltage, exposure, frame

---

## Table of Contents

- [Schema](#schema)
- [Implicit vs Explicit (key=value)](#implicit-vs-explicit-keyvalue)
- [Recognized by DAMPF Indexer](#recognized-by-dampf-indexer)
- [Rules](#rules)
- [Extension](#extension)

---

## Schema

| Use Case | Char | Example |
| -------- | ---- | ------- |
| Parameter separation | _ (underscore) or path | 4kV_10us_FF or 4kV\10us |
| Unit to number | directly, no space | 4kV, 10us, 0p2us |
| Decimal point | p preferred, . supported | 0p2us or 0.2us |
| Inner separation | - (dash/minus) | 2024-06-21 or Slit-0p5mm |

---

## Implicit vs Explicit (key=value)

You can write parameters **implicitly** (short) or **explicitly** (unambiguous):

| Style | Example | Meaning |
| ----- | ------- | ------- |
| **Implicit** | `4kV_10us_001.png` | Indexer infers: 4kV=voltage, 10us=exposure, 001=frame |
| **Explicit** | `voltage=4kV_exposure=10us_frame=001.png` | You name each value directly |

**When to use explicit?**
- Custom parameters: `sample=ABC123`, `operator=john`, `batch=7`
- Disambiguation: `temp=22p5` instead of just `22p5` (no confusion with current)
- When implicit recognition does not apply

**Examples:**
```
Implicit:  run1_4kV_10us_001.png
Explicit:  run=1_voltage=4kV_exposure=10us_frame=001.png
```

Both work; explicit is always unambiguous, implicit is shorter.

---

## Recognized by DAMPF Indexer

| Pattern | Example token | Field |
| ------- | ------------- | ----- |
| Decimal (p preferred, . supported) | 0p2us, 4.2kv, 22p5 | value as decimal |
| Time | ns, us, ms, s | exposure (val+unit) |
| Voltage | v, kv, mv, uv | voltage (val+unit) |
| Current | a, ma, ua | current (val+unit) |
| Frequency | hz, khz, mhz, ghz | freq (val+unit) |
| Length | nm, um, mm, cm, m, px | lengths |
| Temperature | c, °c, k | temp (val+unit) |
| Date | 2024-02-07, 20240207 | date |
| Time (HHMMSS) | 141710 next to a date, or alone if clock-plausible | time (`14:17:10`); not frame. Last filename number stays frame. |
| Compact datetime | `YYYYMMDDHHMMSS` or `IMG20220601093439` | date + time (`2022-06-01`, `09:34:39`); letter prefix splits off |
| `frame_<ch>_<n>` | frame_004_0000 | channel + frame |
| Run/Rep/Trial | run1, rep2, trial3 | run, rep, trial |
| Letter(s)+number | M25, S4, T250 | key=value (e.g. m=25) |
| Number+letter(s) | 300He, 300N2 | key=value; He/N2/CO2 = gas % |
| Flow (slm) | 5slmAr, 10slmN2 | gas_flow (val, unit=slm, gas) |
| Letters only (2–4) | FF, KPSc | string param key=value |
| Frame (digits only) | 000, 001, 040, 165, 07 | frame (integer; plain digits at end of filename) |
| Camera/Channel | cam1, channel2, C1, C2, C3 | camera, channel |
| key=value | arbitrary | stored as key-value |
| Processing tags | raw, dark, flat, avg, … | processing (list) |
| Modality | rgb, ir, thermal, … | modality (via MODALITY_MAP) |

For exotic patterns: see **Extension** below.

---

## Rules

No spaces. Use dashes (-) or CamelCase:
- `NoisyAndDarkEnvironment` or `noisy-and-dark-environment`

**BAD chars (do not use in names):**

` \ / : * ? " < > | [ ] & $ , .

(Exception: `.` in numbers with unit like `4.2kv` is supported.)

No umlauts or special chars – use ASCII (oe, ae, ue, e, a).

**Path and filename – Best practice vs legacy**

- **Best practice:** Parameters in path **or** filename, not both.
- **Legacy:** Both supported; existing structures with params in path and filename still work. On conflict, filename logic applies.

Parameter names at least 2 chars (better 3+):
- BAD: `4kv_10us_c_001` (c alone = temp or current?)
- Good: `4kV_10us_c-set_001`

Max 255 chars for path + filename combined.

Dates: YYYY-MM-DD (YYYYMMDD OK if length matters).

Running numbers at end, with leading zeros:
```
...\T-22_sccm1p5_Image0001.png
...\T-22_sccm1p5_Image0301.png
```

---

## Extension

To add new units or patterns:

1. **New value+unit (e.g. sccm, bar):** Add unit to `RE_NUMBER_UNIT` and matching RE_* in [../../app/dampf/indexer.py](../../app/dampf/indexer.py); possibly new RE_*, `unit_scale()`, and parsing in `parse_tokens()`. Document here under Recognized.

2. **New tags/modality/keys:** Extend `MODALITY_MAP` or `PROC_TAGS` in [../../app/dampf/indexer.py](../../app/dampf/indexer.py), or add key=value pattern. Document under Recognized.

3. **Project-specific (no code change):** Adjust `modality_map` and `stopwords` via project.json / GUI.
