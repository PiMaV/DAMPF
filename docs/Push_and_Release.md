# Push und Release

**Branch:** nur `main`. **GitHub Actions:** Push auf `main` startet **CI** (`pytest`, Linux). Push eines Tags `v*` startet **Release** (Windows-`DAMPF.exe`). EXE-Build **nur** ueber Tag-Push, nicht ueber normalen Branch-Push.

---

## Alltag (Aenderungen auf `main`)

Commit und Push wie ueblich (z. B. GIT in Cursor / GitHub Desktop). Danach optional unter **Actions** pruefen: Workflow **CI**.

---

## Release (Version + EXE)

**Voraussetzung:** Repo geklont, `origin` = GitHub. **`pyproject.toml`**-`version` und der Tag (z. B. `v0.2.0`) **muessen zur selben Versionsnummer** passen.

### Variante A (einfach): Alltag wie immer, dann nur Tag

Wenn die neue Version **schon auf `main` liegt** (inkl. geaenderter `pyproject.toml`), reicht lokal:

```bash
git pull origin main
git tag v0.2.0
git push origin v0.2.0
```

(`v0.2.0` anpassen; `pull` vermeidet, dass der Tag auf einem alten Stand haengt.)

Das loest **Release** aus. Schritt 4 unten.

### Variante B: Version und Push in einem Shell-Schritt

Wenn du den Release-Commit lieber komplett per CLI machst:

```bash
git add pyproject.toml
# oder alle Aenderungen mitstagen:
# git add .
git commit -m "Bump version to 0.2.0"
git push origin main
git tag v0.2.0
git push origin v0.2.0
```

`git add .` ist ok, wenn **alles**, was du stagen willst, zu diesem Release gehoert (keine halbfertigen Dateien im Repo-Root).

### Danach

Auf GitHub **Actions** → **Release** abwarten, dann **Releases** → `DAMPF.exe`.

**Tag/Repair:** `git tag -d v0.2.0`. Auf GitHub Release und Tag loeschen, dann erneut taggen/pushen.

---

**Kurz:** `git push origin main` → nur Tests. `git push origin v0.2.0` → Release + EXE (Commit hinter dem Tag muss die passende `version` in `pyproject.toml` enthalten).
