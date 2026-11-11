# Standalone binary bauen (Windows / Linux)

Mit **uv** und **PyInstaller** eine standalone DAMPF-Binary erzeugen.

## Voraussetzung

- [uv](https://docs.astral.sh/uv/) installieren (z.B. `pip install uv` oder Installer von astral.sh).
- Im Projektordner (Repo-Root).
- **Linux:** Qt/X11-Bibliotheken fuer PyQt6 (z. B. `libxcb-cursor0`, `libxkbcommon-x11-0`, `libegl1`, `libgl1`).

## Schritte

```bash
# Abhaengigkeiten inkl. PyInstaller (dev)
uv sync --extra dev

# Binary bauen (nutzt icon/icon.ico unter Windows, icon/icon_256.png unter Linux)
uv run python scripts/build_exe.py
```

Ausgabe:

* **Windows (lokal):** `dist/DAMPF.exe`
* **Linux (lokal):** `dist/DAMPF`
* **GitHub Release:** `DAMPF-vX.Y.Z.exe` / `DAMPF-vX.Y.Z-linux-x86_64` (Brand CAPS + full tag)

Das Fenster-Icon kommt aus `icon/` (wird im Code ueber `window.setWindowIcon(QIcon(str(p)))` gesetzt).

## Ohne uv

Falls du uv nicht nutzt:

```bash
pip install PyQt6 pyinstaller
python scripts/build_exe.py
```

(Python-Paket `dampf` liegt unter `app/dampf/`; mit `uv sync` ist es im venv verfuegbar. Ohne uv: `PYTHONPATH=app` setzen, damit `import dampf` funktioniert.)

## CI Release

Tag `v*` auf GitHub baut automatisch beide Plattformen — siehe [Push_and_Release.md](Push_and_Release.md).
