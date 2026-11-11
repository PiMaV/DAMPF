# DAMPF Naming – Cheat Sheet

One page. Full text: [Proper_file_naming_EN.md](Proper_file_naming_EN.md)

---

## Four rules

| # | Rule | Example |
| --- | --- | --- |
| 1 | `_` or a folder separates parameters. `-` stays inside one name. `=` names the column. Never a space. | `4kV_10us`, `plasma-on`, `plasma=on` |
| 2 | Unit glued to the number | `4kV`, `10us`, `0p2us` |
| 3 | Decimal: `p` preferred, `.` also works | `22p5`, `4.2kV` |
| 4 | Example | `2024-02-07_run1_4kV_10us_001.png` |

`-` glues a name and does not make a column. `plasma-on` and `plasma-off` are two names.

`=` is one column for every file. `plasma=on` and `plasma=off` are the text column `plasma` (a WOLKE filter, however many states). `temp=22p5`, `temp=18`, and `temp=30` are the number column `temp` (sort and histogram). `18c`, `22p5c`, `30c` are that same temperature column. One value in the set is still written this way.

`_` cannot sit inside a name or a value (`target=metal-grounded`, not `target=metal_grounded`). In the database and in WOLKE, `-` inside a column name is `_` (`target-material` → `target_material`).

---

## Characters

| Role | Character | Example |
| --- | --- | --- |
| Separate parameters | `_` or a folder | `4kV_10us` |
| Stay inside one name | `-` | `2024-02-07`, `Slit-0p5mm` |
| Name the column | `=` | `plasma=on`, `target=metal-grounded` |
| Decimal | `p` or `.` | `22p5`, `4.2kV` |

---

## Common patterns

| Token | Field | Token | Field |
| --- | --- | --- | --- |
| ns, us, ms, s | exposure | v, kv, mv | voltage |
| a, ma, ua | current | nm, um, mm, m | length |
| c, k | temp | hz, khz, mhz | freq |
| 2024-02-07 | date | run1, rep2 | run, rep |
| 000, 001 | frame | cam1, C1 | camera, channel |
| 141710 | time | frame_004_0000 | channel + frame |
| IMG20220601093439 | date + time | 20220601093439 | date + time |
| M25, S4 | letter + number | 5slmAr | gas flow |
| plasma=on | column `plasma` | target=metal-grounded | column `target` |

---

## Also

Do not use: `` ` \ / : * ? " < > | [ ] & $ , . ``

`.` inside a number with a unit is fine (`4.2kV`). No umlauts (`oe`, `ae`, `ue`).

Parameters in the folders **or** in the filename. Names at least 2 characters (`c-set`, not `c`). Dates `YYYY-MM-DD`. Frame numbers at the end, with leading zeros (`001`).

Default crawl suffixes: `.png` `.jpg` `.jpeg` `.tif` `.tiff` `.bmp` `.img` `.csv` `.tsv` `.txt` `.dat` `.asc` `.npy` `.npz` `.h5` `.hdf5` `.json` `.yaml` `.yml`.

`.img` is indexed only. WOLKE and BLITZ cannot open it.
