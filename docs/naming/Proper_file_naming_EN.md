# Path and file names

Convention the **DAMPF indexer** reads ([../../app/dampf/indexer.py](../../app/dampf/indexer.py)).

**Short form:** [Naming_Cheat_Sheet.md](Naming_Cheat_Sheet.md)

---

## Four rules

1. **`_` or a new folder** separates parameters. **`-`** stays inside a name. **`=`** sets the column name. Never spaces.
2. **Glue the unit to the number:** `4kV`, `10us`, `0p2us`.
3. **Decimal:** `p` preferred (`0p2us`, `22p5`). A dot works too (`0.2us`, `4.2kV`).
4. **Example:** `2024-02-07_run1_4kV_10us_001.png` → date, run, voltage, exposure, frame.

---

## Characters

| Role | Character | Example |
| ---- | --------- | ------- |
| Separate parameters | `_` or a folder | `4kV_10us`, `4kV/10us` |
| Stay inside one name | `-` | `2024-02-07`, `plasma-on`, `Slit-0p5mm` |
| Name the column | `=` | `plasma=on`, `target=metal-grounded`, `voltage=4kV` |
| Decimal | `p` or `.` | `22p5`, `4.2kV` |

The name on the left of `=` is letters and digits and may contain `-` (`c-set=001`, `target-material=glass`). There is no separate length cap; path plus filename together stay within 255 characters. `_` cannot sit inside the name or the value, because it starts the next parameter: `target=metal_grounded` becomes `target=metal` and `grounded`. Use a hyphen in the value: `target=metal-grounded`.

A number+unit inside a hyphenated name is read, and the words beside it are not: `150us-Exposure` is the exposure, `Slit-0p5mm` is 0.5 mm. A bare `22p5` is the decimal 22.5, not a key `p5`.

---

## One property, many files

`-` glues words into a single name. That name is not a column, so the two names cannot be compared.

`=` is one column. Every file carries one value of that same property.

| Written on the files | Column | In WOLKE |
| --- | --- | --- |
| `plasma-on` and `plasma-off` | none. Two separate names. | nothing to filter |
| `plasma=on` and `plasma=off` | `plasma`, text `on` / `off` | one filter. Two entries, or 5'000, still one text column. Text does not sort as a measurement. |
| `temp=22p5`, `temp=18`, `temp=30` | `temp`, numbers 22.5, 18, 30 | one histogram. Sort and range-filter by temperature. |
| `18c`, `22p5c`, `30c` | `temp`, same numbers, unit in the token | same histogram. The unit already names the column. |

One temperature in the whole set is still `temp=22p5`. The next experiment lands in the same column. A single value does not separate files; the column type is already right.

`plasma=on` means the run is in state on. `temp=22p5` means the run was done at 22.5. Both are properties of the file. The hyphen form `plasma-on` only names a thing. It does not record which state that file is in.

---

## In WOLKE

WOLKE and KEIM read the SQLite columns, not the filenames.

- Text (`plasma=on`, `target=glass`) is a filter.
- Numbers (`4kV`, `temp=22p5`, `frame`) are a histogram. In DAMPF, **Cat** can force a numeric column to text, and WOLKE then shows it as a filter.
- A hyphen in a column name is `-` in the file (`target-material`) and `_` in the database (`target_material`). SQLite and WOLKE allow only letters, digits, and `_` in column names. WOLKE shows that column name, not the display name edited in DAMPF.

---

## Implicit and explicit

| | Example | Meaning |
| --- | --- | --- |
| Implicit | `4kV_10us_001.png` | voltage, exposure, frame |
| Explicit | `voltage=4kV_exposure=10us_frame=001.png` | the same values, with the column names written out |

Use explicit when the column name has to be fixed or the value is text: `plasma=on`, `target=metal-grounded`, `sample=ABC123`. Implicit is shorter when the unit already names the column (`4kV`, `10us`).

---

## Recognized by the indexer

| Pattern | Example | Field |
| --- | --- | --- |
| Decimal | `0p2us`, `4.2kV`, `22p5` | 0.2, 4.2, 22.5 |
| Time | `ns`, `us`, `ms`, `s` | exposure |
| Voltage | `v`, `kv`, `mv`, `uv` | voltage |
| Current | `a`, `ma`, `ua` | current |
| Frequency | `hz`, `khz`, `mhz`, `ghz` | freq |
| Length | `nm`, `um`, `mm`, `cm`, `m`, `px` | lengths |
| Temperature | `c`, `°c`, `k` | temp |
| Date | `2024-02-07`, `20240207` | date |
| Clock | `141710` | time `14:17:10`, not frame. The last number in the filename stays frame. |
| Compact datetime | `YYYYMMDDHHMMSS`, `IMG20220601093439` | date + time. A letter prefix is split off. |
| `frame_<ch>_<n>` | `frame_004_0000` | channel + frame |
| Run / rep / trial | `run1`, `rep2`, `trial3` | run, rep, trial |
| Letter(s)+number | `M25`, `S4`, `T250` | key is the letters, value is the number (`m` = 25) |
| Number+letter(s) | `300He`, `300N2` | He, N2, CO2 are gas in %. Otherwise the key is the letters. |
| Flow | `5slmAr`, `10slmN2` | gas_flow |
| Letters only, 2–4 | `FF`, `KPSc` | key is the word |
| Hyphen inside a name | `plasma-on`, `Slit-0p5mm`, `150us-Exposure` | one name, not a column. A number+unit inside it is read; the words are not keys. |
| Frame | `000`, `001`, `040` | frame. Plain digits; the last one in the filename. |
| Camera / channel | `cam1`, `channel2`, `C1` | camera, channel |
| `name=value` | `plasma=on`, `plasma=off`, `temp=22p5` | one column for every file. Text stays text. A number stays a number. |
| Processing | `raw`, `dark`, `flat`, `avg`, … | processing |
| Modality | `rgb`, `ir`, `thermal`, … | modality |

---

## Also

No spaces. Several words: `noisy-and-dark-environment` or `NoisyAndDarkEnvironment`.

Do not use: `` ` \ / : * ? " < > | [ ] & $ , . ``

Exception: `.` inside a number with a unit (`4.2kV`). No umlauts: `oe`, `ae`, `ue`.

Put parameters in the folders **or** in the filename. Both at once still read; if the same key appears twice, the filename wins.

Names at least 2 characters, 3 is better. `4kV_10us_c_001` is a bad name (`c` alone). `4kV_10us_c-set_001` is the name `c-set`.

Dates: `YYYY-MM-DD`. When it has to be short: `YYYYMMDD`.

Running numbers at the end, with leading zeros: `Image0001`, `Image0301`.

---

## Extension

1. **New unit** (for example `sccm`, `bar`): add it to `RE_NUMBER_UNIT` and the matching `RE_*` in [../../app/dampf/indexer.py](../../app/dampf/indexer.py), plus `unit_scale()` and `parse_tokens()`. Add a row to the table above.
2. **New tag or modality:** extend `MODALITY_MAP` or `PROC_TAGS`, or use `name=value`.
3. **This project only:** adjust `modality_map` and `stopwords` in the GUI or `project.json`.
