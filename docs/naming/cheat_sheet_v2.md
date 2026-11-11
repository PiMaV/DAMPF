# Naming Cheat Sheet

Pipeline: **RAW DATA → DAMPF → KEIM → WOLKE → BLITZ**
Details: [file_names_explained_v2.md](file_names_explained_v2.md)

- **Number:** A measurement or a counter. WOLKE uses it for sliders and histograms (`4p5kV`, `10us`, `0042`, `run=01`).
- **Category:** A label you pick from a list. WOLKE uses it as clickable filters (`target=metal-grounded`, `plasma=on`).

## 1. Three operators

- `_` or `/` : **Separates** blocks. A subfolder is read like a block in the filename.
- `-` : **Glues** one name (`metal-grounded`, `2024-02-07`).
- `=` : **Defines** name and value (`target=metal-grounded`, `run=01`).

Name files with these three. That is the whole scheme.

## 2. Master example

`cold-jet/2024-02-07_run=01_target=metal-grounded_4p5kV_10us_temp=22p5c_0042.png`

- `cold-jet/` → Gray. Nothing stored. Write `setup=cold-jet` if you want a filter.
- `2024-02-07` → Category `date` (a date string, a list in WOLKE)
- `run=01` → Number `run` = 1 (digits after `=` are a number)
- `target=metal-grounded` → Category `target` = metal-grounded
- `4p5kV` → Number `voltage` = 4.5 kV (`p` is the decimal point)
- `10us` → Number `exposure` = 10 µs
- `temp=22p5c` → Number `temp` = 22.5 °C
- `0042` → Number `frame` = 42 (last digits before the extension)

## 3. Write it this way

- Digits after `=` are a number: `run=01` → 1.
- Text after `=` is a category: `plasma=on`.
- A known unit stuck to the number is still a number: `4p5kV`, `10us`. Decimal point: `p` or `.` (`4.5kV`).
- Put the frame number at the end and keep the same width (`0001`–`9999`), so the file manager sorts in order.
