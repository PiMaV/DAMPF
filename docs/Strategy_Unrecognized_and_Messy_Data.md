# Strategy: Unrecognized Data and Messy Naming

## Quick Reference (Antworten auf deine Fragen)

| Deine Frage | Kurze Antwort |
|-------------|---------------|
| "Unrecognized" – auch die Dateien, die wir gerade nicht nutzen? | Ja. Das sind **Unrecognized FILES** = Filter. Du siehst z.B. nur .asc, .jpg ist ausgeblendet. |
| Warum so viel Grau? | **Unrecognized TOKENS** = Teile im Pfad, die das Schema nicht kennt. SyncK, Gain150, 100EE0001 etc. |
| Ich kann als Mensch leicht erkennen: SyncK, SyncAA, SyncDD gehoeren zusammen | Genau. Loesung: **custom_token_map**. Token → Key. Spaeter: Batch-Mapping (mehrere auf einmal). |
| Wenn sich Dinge vermischen / Tippfehler (MultFilI vs MultFiLI)? | Das ist **Kategorie 3**: Typos/Inkonsistenzen. Aktuell: wir fangen das nicht. Option: spaeter Ausreisser-Erkennung. |
| Universal Tool oder "Shit on it"? | **Hybrid**: Schema + custom_token_map als Basis. Wer Konvention nicht einhaelt, bekommt trotzdem Hilfe – kein "Pech gehabt". |

---

## Drei verschiedene Konzepte (nicht vermischen)

| # | Begriff | Bedeutung | Wo sichtbar | Loesung |
|---|---------|-----------|------------|---------|
| 1 | **Unrecognized FILES** | Dateien, die du gerade nicht siehst (Filter nach Typ) | Filter-by-type: .jpg vs .asc – du klickst, andere sind ausgeblendet | Filter-Buttons – bereits da |
| 2 | **Unrecognized TOKENS** | Teile im Pfad, die das Schema nicht kennt | Grau im Path-Overview: SyncK, 1000ppmO2, Gain150, 100EE0001 | custom_token_map – bereits da |
| 3 | **Typos / Inkonsistenzen** | Ordner- oder Dateinamen weichen ab (MultFilI vs MultFiLI) | Verschiedene Pfadstrukturen, keine einheitliche Token-Zuordnung | Aktuell: nicht abgefangen. Optional: Ausreisser-Erkennung |

**Wichtig:** 1 und 2 sind unterschiedlich. 1 = Filter. 2 = Schema-Luecken. 3 = Datenqualitaet.

---

## Philosophie: Universal vs. Strict

**Option A: Universal Tool**
- Wir helfen auch bei chaotischen Daten
- custom_token_map, Ausreisser-Erkennung, Tippfehler-Vorschlaege
- Mehr Aufwand, groessere Flexibilitaet

**Option B: Strict ("Shit on it")**
- "Wer unsere Konvention nicht einhaelt, hat Pech"
- Nur Proper_file_naming, keine Extras
- Einfach, aber unflexibel

**Empfehlung: Hybrid**
- **Basis:** Schema (Proper_file_naming) + custom_token_map (bereits implementiert)
- **Nicht "shit on it"** – wir geben dem Nutzer Moeglichkeiten, chaotische Daten zu strukturieren
- **Optional:** Ausreisser-Erkennung, Tippfehler-Hinweise – als separate Features, nicht Pflicht

---

## Aktuelle Logik (kurz)

1. **Crawl:** Alle erlaubten Typen (.jpg, .asc, .csv, …) werden indexiert
2. **Filter by type:** Du siehst z.B. nur .asc – .jpg ist ausgeblendet, aber nicht geloescht
3. **Token-Parsing:** Jeder Pfad wird in Tokens zerlegt; was das Schema kennt = farbig, Rest = grau
4. **custom_token_map:** Du kannst graue Tokens zu Parametern machen (z.B. SyncK → sync_mode)

**Warum so viel Grau?** Das Schema kennt nur: date, lengths, freq, exposure, voltage, run, rep, frame, FF/SF (letters-only), etc. Alles andere (1000ppmO2, Gain150, SyncK, 100EE0001) ist grau – bis du es ueber custom_token_map hinzufuegst.

---

## Sauberer Implementierungsplan

### Phase 1: Klarheit (Dokumentation + UI) ✓
- [x] Tooltip: "Unrecognized FILES = Filter. Unrecognized TOKENS = grau."
- [x] Tooltip unter "Unrecognized → Parameters"

### Phase 2: custom_token_map verbessern
- [x] Token → Key hinzufuegen
- [ ] Batch-Mapping: mehrere Tokens auf einmal zu einem Key (z.B. SyncK, SyncAA, SyncDD → sync_mode)
- [ ] Vorschlaege: "Sync*" → sync_mode?

### Phase 3: Ausreisser (separater Plan)
- [ ] Pfade markieren, die vom Schema abweichen
- [ ] Tippfehler-Vorschlaege (z.B. MultFiLI → MultFilI?)

### Phase 4: Philosophie dokumentiert
- DAMPF ist ein **hilfreiches** Tool – custom_token_map als Basis, Ausreisser optional
- Kein "shit on it"

---

## Konkrete Schritte fuer deine Beispieldaten

### Pfad-Beispiele (aus deiner Nachricht)

```
Bilder_MultiFil_I\20221026_MultFilI_1000ppmO2_10mm_1000sync_250Hz\ASCII\FF\SyncK_221026_...
Bilder_MultiFil_I\20221026_...\ASCII\SF\SyncAA_221026_...
Bilder_MultiFil_I\20221026_...\ASCII_LowResSync\SF\SyncA_221026_...
Bilder_MultiFil_I\20221104_MultFiLI_0_5mm_1000ppmO2_Puls_250Hz\FF\SyncL_221104_...
Bilder_MultiFil_I\NEU_10_03_23\SF\SyncD_221104_...
```

### Sofort moeglich (custom_token_map)

| Grauer Token | Vorschlag Key | Hinweis |
|--------------|---------------|---------|
| SyncK, SyncAA, SyncDD, SyncHH, SyncA, SyncE, SyncH, SyncL, SyncC, SyncG, SyncJ, SyncD | `sync_id` oder `sync_mode` | Alle Sync* gehoeren zusammen – spaeter Batch |
| Gain150 | `gain` | |
| 100EE0001, 100EE0047, … | `ee_id` oder `frame` | |
| 1000ppmO2 | `gas_pct` | wenn als Gas interpretiert |
| FF, SF | bereits im Schema (letters-only) | |
| ASCII, ASCII_LowResSync | `modality` oder `processing` | ueber custom_token_map |

### Nicht abgefangen (Kategorie 3)

| Problem | Beispiel | Aktuell |
|---------|----------|---------|
| Tippfehler im Ordnernamen | MultFilI vs MultFiLI | Beide werden als Token behandelt, keine Korrektur |
| Unterschiedliche Strukturen | ASCII\FF vs FF direkt, NEU_10_03_23 | Token-Position variiert, aber Parsing funktioniert |

**Fazit:** custom_token_map deckt die grauen Tokens ab. Typos/Struktur-Inkonsistenzen bleiben – wir koennen sie spaeter optional markieren, aber nicht automatisch korrigieren.

---

## Wissensintegration: Wie kommt das Wissen in Unrecognized → Parameters?

Die Frage: Wie integrieren wir erlerntes Wissen (C1→channel, 00000→seq, SyncK→sync_mode, 5slmar→gas_flow) in den Workflow?

### Wo lebt das Wissen?

| Ort | Inhalt | Wiederverwendung |
|-----|--------|------------------|
| **custom_token_map** (Schema) | Token → Key | In project.json, DB, "Load schema from DB" |
| **DB / project.json** | Gesamtes Schema inkl. custom_token_map | Andere Projekte, gleicher Datentyp |
| **Pattern Library** (neu) | Vorschlaege: Token-Muster → Key | Dokumentation, spaeter: GUI-Vorschlaege, Presets |

### Drei Wege, Wissen einzufuegen

| Weg | Beschreibung | Status |
|-----|--------------|--------|
| **1. Manuell** | Token waehlen → Key eingeben → Add | Bereits implementiert |
| **2. Preset laden** | "Additive Manufacturing" / "Spektroskopie" laden → vorgefuellte custom_token_map | Phase 2 |
| **3. Vorschlaege** | Bei Token-Auswahl: "C1 → channel?" anzeigen, ein Klick uebernimmt | Phase 2 |

### Pattern Library (Wissensbasis)

Eine Datei oder Tabelle mit bekannten Mustern. Siehe **`docs/Pattern_Library.md`**. Nutzer kann nachschlagen; spaeter kann die GUI daraus vorschlagen.

| Token-Muster | Vorschlag Key | Kontext |
|--------------|---------------|---------|
| C1, C2, C3, … | `channel` | Kanal/Charge |
| 00000, 00005, 00023 | `seq` oder `frame` | 5-stellige Sequenz |
| SyncK, SyncAA, SyncDD | `sync_id` | Sync-Modus |
| Gain150, Gain200 | `gain` | Verstaerkung |
| 1000ppmO2, 300He | `gas_pct` | Gasanteil |
| 5slmar, 10slmn2 | `gas_flow` | Durchfluss (slm) |
| KPSc, Cup, Pon | `setup` oder ignorieren | Setup-Konstanten |

### Implementierungsreihenfolge

1. **Jetzt:** Pattern Library als Dokumentation (z.B. `docs/Pattern_Library.md`) – Nutzer schaut nach, traegt manuell ein
2. **Phase 2a:** Preset-Dateien (JSON) mit vorgefuellter custom_token_map, z.B. `presets/additive_manufacturing.json` – "Load preset" in GUI
3. **Phase 2b:** Beim Token-Auswaehlen Vorschlag aus Pattern Library anzeigen – "C1 → channel?" als Quick-Add

### Flow: Wissen einfliessen lassen

```
Crawl → Graue Tokens sichtbar
         ↓
Nutzer oeffnet "Unrecognized → Parameters"
         ↓
[Option A] Schaut in Pattern_Library.md nach → traegt manuell ein
[Option B] Laedt Preset "Additive" → custom_token_map vorgefuellt
[Option C] Waehlt C1 → GUI zeigt "→ channel?" → Klick uebernimmt
         ↓
custom_token_map wird gespeichert (Save to DB, project.json)
         ↓
Naechstes Projekt: "Load schema from DB" → Wissen uebernommen
```

**Kern:** Das Wissen landet immer in `custom_token_map`. Die Pattern Library / Presets / Vorschlaege sind nur **Eingabekanaele** – sie fuellen custom_token_map schneller.

---

## Zusammenfassung

| Frage | Antwort |
|-------|---------|
| Unrecognized FILES? | Filter – du siehst nur den gewaehlten Typ. Andere sind ausgeblendet, nicht weg. |
| Unrecognized TOKENS (grau)? | Schema kennt sie nicht. Loesung: custom_token_map. |
| Typos / MultFilI vs MultFiLI? | Aktuell nicht abgefangen. Optional: Ausreisser-Erkennung spaeter. |
| Universal oder Strict? | Hybrid: Schema + custom_token_map. Kein "shit on it". |
| Naechster Schritt? | Phase 2: Batch-Mapping (SyncK, SyncAA, SyncDD → sync_mode in einem Schritt). |
