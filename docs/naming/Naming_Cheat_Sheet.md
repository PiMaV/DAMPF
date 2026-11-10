# DAMPF Naming – Cheat Sheet

One-page quick reference. Full docs: [Proper_file_naming_EN.md](Proper_file_naming_EN.md) (EN) | [Proper_file_naming.md](Proper_file_naming.md) (DE)

---

## 3 Rules

| # | Rule | Example |
|---|------|---------|
| 1 | Separators: `_` or `-`, never space | `4kV_10us` or `Slit-0p5mm` |
| 2 | Unit directly to number (no space) | `4kV`, `10us`, `0p2us` |
| 3 | Decimal: `p` preferred, `.` supported | `0p2us` or `0.2us` |
| 4 | Example | `2024-02-07_run1_4kV_10us_001.png` |

---

## Schema

| Use | Char | Example |
|-----|------|---------|
| Parameter separation | `_` or path | `4kV_10us` |
| Decimal | `p` or `.` | `0p2us`, `4.2kv` |
| Inner separation | `-` | `2024-02-07`, `Slit-0p5mm` |

---

## Most Common Patterns

| Token | Field | Token | Field |
|-------|-------|-------|-------|
| ns, us, ms, s | exposure | v, kv, mv | voltage |
| a, ma, ua | current | nm, um, mm, m | lengths |
| c, k | temp | hz, khz, mhz | freq |
| 2024-02-07 | date | run1, rep2 | run, rep |
| 000, 001 | frame | cam1, C1 | camera, channel |
| 141710 | time | frame_004_0000 | channel+frame |
| IMG20220601093439 | date+time | 20220601093439 | date+time |
| M25, S4 | param | key=value | explicit |

---

## Implicit vs Explicit

| Style | Example |
|-------|---------|
| **Implicit** | `4kV_10us_001.png` |
| **Explicit** | `voltage=4kV_exposure=10us_frame=001.png` |

Use explicit for custom params: `sample=ABC123`, `temp=22p5`

---

## BAD Chars

`` ` \ / : * ? " < > | [ ] & $ , . ``

Exception: `.` in numbers like `4.2kv` is OK. No umlauts – use ASCII (oe, ae, ue).

---

## Crawl suffixes

Default allowlist: `.png` `.jpg` `.jpeg` `.tif` `.tiff` `.bmp` `.img` `.csv` `.tsv` `.txt` `.dat` `.asc` `.npy` `.npz` `.h5` `.hdf5` `.json` `.yaml` `.yml`.  
`.img` is path indexing only (WOLKE/BLITZ cannot open it).

## Best Practice

- Parameters in path **or** filename, not both (legacy: both supported)
- Param names ≥2 chars: `c-set` not `c`
- Dates: YYYY-MM-DD
- Frame numbers at end, with leading zeros: `001`, `040`
