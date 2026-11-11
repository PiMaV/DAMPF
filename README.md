# DAMPF

Indexes folder and file names into a **SQLite** database — one row per file — for querying and for the rest of the [WETTER](https://wetter.mess.engineering) pipeline.

![DAMPF GUI](docs/images/Screenshot_GUI_Example.png)

**Download:** [latest release](https://github.com/PiMaV/DAMPF/releases/latest) — `DAMPF-vX.Y.Z.exe` (Windows) / `DAMPF-vX.Y.Z-linux-x86_64` (Linux).

1. Download the binary for your platform.
2. Linux: `chmod +x DAMPF-vX.Y.Z-linux-x86_64`, then run it. Windows: run the `.exe`.
3. Set the crawl **root**, click **Crawl**, adjust which keys to keep, then **Save to DB**.

**Step 4 — Detected keys**

- **Used** — which keys become columns. None checked means all keys; any checked means only those.
- **Cat** — store that column as TEXT so WOLKE shows a filter instead of a histogram (default when a key has fewer than 10 distinct values).
- **Uniques** — distinct values in the current file set.
- **Full** — how many files have the key; `(−N)` means N files are missing it.

**Naming:** [Cheat sheet](docs/naming/Naming_Cheat_Sheet.md) · [full convention](docs/naming/Proper_file_naming_EN.md)

For agents: [`docs/llm-brief.md`](docs/llm-brief.md).

---

Developed by [M.E.S.S.](https://mess.engineering).
