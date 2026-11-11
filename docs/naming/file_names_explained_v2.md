# File Naming Convention & Metadata Extraction

Pipeline: **RAW DATA → DAMPF → KEIM → WOLKE → BLITZ**
Quick reference: [cheat_sheet_v2.md](cheat_sheet_v2.md)

DAMPF reads a file path as a row of metadata. WOLKE uses those fields for filters, sliders, and histograms, and passes the chosen images to BLITZ.

Name every file with three operators: `_` separates, `-` glues, `=` defines. The rest of this page is what the indexer also does when a name does not follow that.

## 1. The two kinds

- **Number:** A measurement or a counter (`4p5kV`, `10us`, `run=01`, `0042`). WOLKE can sort it, plot it, and limit the range.
- **Category:** A label from a list (`target=metal-grounded`, `plasma=on`, the date `2024-02-07`). WOLKE shows it as filters you click.

Digits after `=` are a number. Text after `=` is a category.

## 2. The three operators

| Operator | Action | What to write |
| :--- | :--- | :--- |
| `_` or `/` | **Separates** | `run=01_target=metal-grounded`. A subfolder is read like a block in the filename. |
| `-` | **Glues** | `metal-grounded`, `2024-02-07`. One name, one block. |
| `=` | **Defines** | `plasma=on`, `run=01`, `temp=22p5c`. The name is yours. |

## 3. Master example

```text
cold-jet/2024-02-07_run=01_target=metal-grounded_4p5kV_10us_temp=22p5c_0042.png
```

| Token | Kind | Key | Value | What happens |
| --- | --- | --- | --- | --- |
| `cold-jet/` | Gray | — | — | No rule matched. Nothing is stored. Write `setup=cold-jet` if you want a filter. |
| `2024-02-07` | Category | `date` | `2024-02-07` | ISO date. A list in WOLKE. |
| `run=01` | Number | `run` | `1` | Digits after `=`. The leading zero is dropped. |
| `target=metal-grounded` | Category | `target` | `metal-grounded` | Text after `=`. The hyphen keeps one label. |
| `4p5kV` | Number | `voltage` | `4.5 kV` | Unit `kV`. `p` is the decimal point. |
| `10us` | Number | `exposure` | `10 µs` | Unit `us`. |
| `temp=22p5c` | Number | `temp` | `22.5 °C` | Your name `temp`, value with unit `c`. |
| `0042` | Number | `frame` | `42` | Last digits before the extension. |

## 4. What a block becomes

`=` is the rule to use.

- Digits after `=` → number (`run=01` → `run` = 1).
- Text after `=` → category (`plasma=on`).
- A number with a unit after `=` → number under your name (`temp=22p5c` → `temp` = 22.5 °C).

Without `=`, a block can still match:

- `2024-02-07` → category `date`
- a known unit stuck to the number → a number (`10us` → `exposure`, `4p5kV` → `voltage`, `22p5c` → `temp`)
- `run` glued to digits → number `run` (`run01`, `run1`)
- a modality word → `modality` (`rgb`, `ir`, `thermal`)
- a processing word → `processing` (`raw`, `dark`, `flat`)
- the last plain integer in the filename → number `frame`

The full unit, modality, and processing lists are in DAMPF under **Naming rules**. The examples above are the common ones.

If nothing matches, the block stays gray. It is not stored, and WOLKE cannot filter on it. A folder is the same: `raw/` is processing, `cold-jet/` stays gray until you write `setup=cold-jet`.

## 5. Characters that also split

You do not name files with these. They already break a block, because paths and messy exports contain them:

space, comma, semicolon, plus, brackets, backslash, and a dot that is not a decimal point.

A decimal dot is kept: `4.5kV` is the same number as `4p5kV`.

A comma is not a decimal. `4,5kV` splits. DAMPF stores 5 kV and drops the 4. There is no error.

`shot+01` splits on the plus. The `01` becomes frame 1.

Write the block with `_`, `-`, and `=` instead.

## 6. Mistakes that get copied

| Written | What you get | Write this |
| --- | --- | --- |
| `run-01` | Gray | `run=01` |
| `plasma-on` | Gray | `plasma=on` |
| `target=metal_grounded` | `target` = metal, and `grounded` left over | `target=metal-grounded` |
| `10 us` or `10_us` | The unit falls off | `10us` |
| `4,5kV` | 5 kV, the 4 is gone | `4p5kV` or `4.5kV` |
| `22p5` | Gray | `temp=22p5` or `22p5c` |

## 7. In DAMPF

- Pad the frame with the same width (`0001`–`9999`). DAMPF stores `0042` as 42. The zeros are for the file manager.
- **Type:** A block that changes is **Category**. More than 10 different numbers are **Numeric**. Choose **Numeric** when a short list is still a measurement (a voltage sweep, a temperature sweep).
- A folder or underscore block that is the same in every file stays gray. A block that changes is stored on its own.
- **Naming rules:** Units, modality words, and processing words are lists in this installation. Delete an entry you do not want recognized.
