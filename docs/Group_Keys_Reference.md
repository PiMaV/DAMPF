# Group Keys – Entfernt

Die **Group-Keys-Funktionalitaet** wurde aus DAMPF entfernt.

---

## Was wurde entfernt?

- **Export:** Es wird kein `groups.json` mehr erzeugt.
- **Save to DB:** In der config-Tabelle wird `group_keys` nicht mehr gespeichert.
- **GUI:** Keine Group-Keys-Zeile, kein "Choose…", keine Gruppenanzahl.
- **Config/Schema:** `group_keys` gibt es weder in project.ini/project.json noch in der Indexer-Config.
- **API:** `run_indexer()` liefert weiterhin `(rows, {})`; das zweite Element ist ein leeres Dict zur Abwaertskompatibilitaet.

---

## Hintergrund

- **WOLKE** nutzt weder `groups.json` noch die DB-config/`group_keys`; WOLKE liest nur die eine Daten-Tabelle und filtert ueber deren Spalten (z.B. `date`, `run`) als normale Kategorien.
- Die Begriffe "Gruppe" und "Group Keys" haben in der GUI Verwirrung gestiftet (z.B. in Verbindung mit der "Used"-Spalte). Mit der Entfernung entfaellt diese Mehrdeutigkeit.
- Sollte in Zukunft wieder eine gruppenbasierte Auswertung noetig sein, kann sie ueber die vorhandenen Spalten in der data-Tabelle bzw. im Export abgebildet werden.

---

## Detected keys: flache Liste + Spalte "Group"

- **Kein Kategorie-Baum mehr:** Die Keys werden als flache Liste angezeigt (eine Zeile pro Key), sortiert nach Pfadposition. Keine vorgegebenen LUT-Kategorien (Parameter, Gas, Frequency etc.).
- **Spalte "Group (optional)":** Auswahl aus Vorgaben oder eigenes Label. Vorgaben per Default: Camera, Run, Source, Experiment, Modality (definiert in **app/dampf/gui.py** als `DEFAULT_GROUP_CHOICES`). Weitere Gruppen legt der Nutzer per Eingabe an; sie stehen sofort in allen Zeilen zur Verfuegung.
- **Persistenz:** Nutzer-definierte Gruppen werden in **dampf.ini** unter `[groups]` → `group_choices` gespeichert (beim Schliessen der GUI). Zusaetzlich beim "Save to DB" / "Load schema from DB" in der DB-config.
- **Vorteil:** Flexibel gruppierbar (z.B. voltage + frequency = Source; frequency + exposure = Camera), ohne feste LUT-Vorgaben.

---

*Stand: Nach Abschluss der Gruppen-Entfernung. Siehe auch: README.MD (Output ohne groups.json).*
