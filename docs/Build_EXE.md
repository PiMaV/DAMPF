# EXE bauen (Windows)

Mit **uv** und **PyInstaller** eine standalone DAMPF.exe erzeugen.

## Voraussetzung

- [uv](https://docs.astral.sh/uv/) installieren (z.B. `pip install uv` oder Installer von astral.sh).
- Im Projektordner (Repo-Root).

## Schritte

```bash
# Abhaengigkeiten inkl. PyInstaller (dev)
uv sync --extra dev

# EXE bauen (nutzt icon/icon.ico)
uv run python scripts/build_exe.py
```

Die EXE liegt danach unter `dist/DAMPF.exe`. Das Fenster-Icon kommt aus `icon/icon.ico` (wird im Code ueber `window.setWindowIcon(QIcon(str(p)))` gesetzt).

## Ohne uv

Falls du uv nicht nutzt:

```bash
pip install PyQt6 pyinstaller
python scripts/build_exe.py
```

(Python-Paket `dampf` liegt unter `app/dampf/`; mit `uv sync` ist es im venv verfuegbar. Ohne uv: `PYTHONPATH=app` setzen, damit `import dampf` funktioniert.)
