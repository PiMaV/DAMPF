# Group Keys – Referenz

Group Keys sind in der GUI **ausgeblendet** (nur fuer Export/DB relevant). Diese Referenz erklaert, was sie sind und wo sie verwendet werden.

---

## Was sind Group Keys?

- **Keine Auswirkung auf:** Erkennung von Parametern, Key-Tree, Pfaduebersicht oder pro-Datei-Ergebnisse in DAMPF.
- **Nur relevant fuer:** Wie Dateien zu **logischen Gruppen** zusammengefasst werden – und das nur bei **Export** und **Save to DB**.

**Definition:** Eine **Gruppe** = alle Dateien, die dieselbe Kombination von Werten fuer die gewaehlten Keys haben.  
Beispiel: Group Keys = `date`, `run` → Gruppe `date=2022-01-19 | run=1` = alle Dateien mit diesem Datum und dieser Run-Nummer.

---

## Wo werden sie verwendet?

| Aktion | Verwendung |
|--------|------------|
| **Export** | `groups.json` listet pro Gruppen-Label die zugehoerigen Dateipfade. Downstream-Tools koennen so "alle Dateien einer Gruppe" laden. |
| **Save to DB** | Das Schema speichert `group_keys`; WOLKE/BLITZ (oder andere Consumer) wissen, wie eine logische Einheit (z.B. ein Messlauf) definiert ist. |
| **Crawl** | `run_indexer` erhaelt `group_keys` und liefert ein Gruppen-Dict; die GUI nutzt intern dasselbe fuer Anzeige/Export. |

---

## Default

Ohne sichtbare Group-Keys-UI verwendet DAMPF intern:

- **Default:** `date`, `experiment`, `sample`, `run`, `rep`

Dieser Default wird beim Crawl, beim Save to DB und beim Export verwendet, wenn die Gruppe-Keys-Zeile ausgeblendet ist.

---

## Group-Keys-UI wieder einblenden

Falls du Group Keys aendern musst (z.B. andere Keys fuer groups.json oder DB):

- In **gui.py** die Zeile `self._group_keys_container.hide()` auskommentieren oder durch `self._group_keys_container.setVisible(True)` ersetzen, damit die Zeile mit Label, Eingabefeld, Button "Choose…" und "→ N groups" wieder erscheint.

---

*Siehe auch: TODO.md / Anbindung Wolke/Blitz; db_writer.py (Schema config).*
