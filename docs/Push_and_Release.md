# Push und Release (Step by step)

DAMPF nutzt nur den Branch **`main`**. GitHub Actions:

| Aktion | Was passiert |
|--------|----------------|
| Push auf **`main`** (z. B. GitHub Desktop / IDE) | **CI** laeuft: `pytest` auf Linux (kein Windows-EXE-Build). |
| Push eines Tags **`v*`** (nur sinnvoll per **CLI**) | **Release** laeuft: PyInstaller baut `DAMPF.exe` und haengt sie an das GitHub-Release. |

Der **EXE-Build** startet also **nicht** beim normalen Pushen der App-Aenderungen, sondern **nur**, wenn du einen Versionstag per Kommandozeile pushst.

---

## Alltag: Aenderungen pushen (GUI)

1. Aenderungen committen.
2. In GitHub Desktop (oder Cursor / VS Code) auf **`main`** pushen.
3. Fertig. Optional auf GitHub unter **Actions** pruefen: Workflow **CI** (Tests).

---

## Release: Version + Windows-EXE (CLI)

**Voraussetzung:** Repo lokal geklont, Remote `origin` zeigt auf GitHub.

1. **Version setzen** in `pyproject.toml` bei `[project]` → `version = "x.y.z"` (ohne `v`, z. B. `0.2.0`).

2. **Commit und Push auf `main`** (darfst du wieder per GUI machen):
   - Commit-Nachricht z. B. `Bump version to 0.2.0`
   - Push nach `origin/main`

3. **Tag erstellen** (lokal, **CLI**), Tagname **muss** mit `v` beginnen und zur Version passen:
   ```bash
   git tag v0.2.0
   ```

4. **Nur den Tag pushen** (loest den Release-Workflow aus):
   ```bash
   git push origin v0.2.0
   ```

5. Auf GitHub **Actions** → Workflow **Release** abwarten, dann unter **Releases** die `DAMPF.exe` finden.

**Hinweis:** Wenn der Tag schon existiert oder du die Version aendern willst: Tag lokal loeschen (`git tag -d v0.2.0`), auf GitHub ggf. Release/Tag entfernen, dann erneut ab Schritt 1.

---

## Kurzcheck

- Normaler Push **main** → nur **CI** (Tests).
- `git push origin v1.2.3` → **Release** + EXE (Tag-Format `v*`).
