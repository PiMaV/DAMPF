# Group Keys – removed

**Update:** The optional GUI column **Group** (per-key labels such as Camera / Run / Source) has also been removed. It was never written into the data table and WOLKE never used it. Older DBs may still contain `key_group_label` / `key_group_choices` in the `config` table; DAMPF ignores those keys.

---

Die **Group-Keys-Funktionalitaet** wurde aus DAMPF entfernt.

---

## Was wurde entfernt?

- **Export:** Es wird kein `groups.json` mehr erzeugt.
- **Save to DB:** In der config-Tabelle wird `group_keys` nicht mehr gespeichert.
- **GUI:** Keine Group-Keys-Zeile, kein "Choose…", keine Gruppenanzahl; die spaetere Spalte "Group (optional)" ist ebenfalls entfernt.
- **Config/Schema:** `group_keys` gibt es weder in project.ini/project.json noch in der Indexer-Config. `key_group_label` / `key_group_choices` werden nicht mehr gelesen oder geschrieben.
- **API:** `run_indexer()` liefert weiterhin `(rows, {})`; das zweite Element ist ein leeres Dict zur Abwaertskompatibilitaet.

---

## Hintergrund

- **WOLKE** nutzt weder `groups.json` noch die DB-config/`group_keys`; WOLKE liest nur die eine Daten-Tabelle und filtert ueber deren Spalten (z.B. `date`, `run`) als normale Kategorien.
- Die Begriffe "Gruppe" und "Group Keys" haben in der GUI Verwirrung gestiftet (z.B. in Verbindung mit der "Used"-Spalte). Mit der Entfernung entfaellt diese Mehrdeutigkeit.
- Sollte in Zukunft wieder eine gruppenbasierte Auswertung noetig sein, kann sie ueber die vorhandenen Spalten in der data-Tabelle bzw. im Export abgebildet werden.

---

*Stand: Group-Spalte entfernt. Siehe auch: README.MD (Step 4 — Detected keys).*
