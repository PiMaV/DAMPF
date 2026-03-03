# Filename Semantic Indexer

## Zweck

Dieses Tool strukturiert große Mengen an Messdaten-Dateien automatisch anhand von Ordner- und Dateinamen.

Ziel ist es, semantische Informationen (z. B. Datum, Run, Temperatur, Exposure, Kamera, Sample, Modality, etc.) aus Pfad- und Dateinamen zu extrahieren und in ein einheitliches, maschinenlesbares Schema zu überführen.

Typischer Anwendungsfall:
- Wissenschaftliche Bilddaten (PNG, TIFF, JPG)
- NumPy-Arrays (NPY, NPZ)
- CSV-/Text-Messdaten
- HDF5-Dateien
- Gemischte Ordnerstrukturen mit experimentellen Parametern im Pfad

---

## Architektur

Pipeline:

1. **Ordnerscan**
   - Rekursiv
   - Filter auf definierte Dateitypen

2. **Tokenisierung**
   - Trennung auf `_ - . /`
   - Split von Letter↔Digit-Übergängen
   - Einbezug von Ordnernamen

3. **Regelbasiertes Parsing**
   - Datumserkennung (ISO, kompakt)
   - Run / Rep / Trial
   - Kamera / Channel / ROI / Frame
   - Exposure (ns, us, ms, s)
   - Temperatur (°C, K)
   - Frequenz, Spannung, Strom
   - Modality-Tags
   - Processing-Tags (raw, dark, flat, avg, ...)

4. **Strukturiertes Schema**
   Jede Datei wird als Dict gespeichert, z. B.:

   {
     "date": "2026-02-28",
     "run": 3,
     "temp": {"val": 20.0, "unit": "c"},
     "exposure": {"val": 2.0, "unit": "us"},
     "camera": 1,
     "modality": "ir",
     "processing": ["raw"],
     "path": "...",
     "confidence": 0.93
   }

5. **Grouping**
   Dateien werden über definierte Schlüssel (`GROUP_KEYS`) zugehörig gruppiert, z. B.:

   (date, experiment, sample, run, rep)

---

## Konfiguration

**CLI:** Im Script [filename_semantic_indexer.py](filename_semantic_indexer.py) oben anpassen: `ROOT_DIR`, `OUTPUT_DIR`, `ALLOWED_SUFFIXES`, `FOLDER_TOKEN_DEPTH`, `GROUP_KEYS`.

**GUI:** Root- und Output-Ordner sowie GROUP_KEYS in der Oberflaeche einstellen; Schema als project.json/project.ini speichern und wieder laden („Root gemaess Schema laden“).

**Namenskonventionen:** [Proper_file_naming.md](Proper_file_naming.md) definiert Schema (Dezimal `p`, Trenner, erlaubte Zeichen) und listet, welche Schreibweisen der Indexer erkennt; dort steht auch, wie man neue Schreibweisen ergaenzt.

---

## GUI und Standalone-EXE

- **Starten:** `python gui.py` oder `dist\DAMPF.exe` (nach Build).
- **Ablauf:** Root-Ordner waehlen → Crawl starten → Nomenklatur prufen/anpassen → Schema speichern (project.json/ini) und/oder In Datenbank speichern (SQLite).
- **Schema:** Erkannte Struktur als project.json (oder project.ini) speichern; beliebigen anderen Root „gemaess Schema“ laden und erneut crawlen.
- **EXE bauen:** `pyinstaller DAMPF.spec` → `dist\DAMPF.exe` (ein Datei, keine Python-Installation noetig).
- Ausgabe (SQLite, JSONL/CSV) ist fuer **Wolke** (Dash/Plotly, SQL) und **Blitz** (Image Viewer) nutzbar.

---

## Output

- `index.jsonl` → Eine Zeile pro Datei (numerische Werte ohne Unit-Spalten)
- `index.csv` → Excel-freundlicher Ueberblick (Spalten ohne Unit)
- `index_meta.json` → Column-Metadaten (unit, raw_unit pro quantitative Spalte)
- `groups.json` → Gruppierte Dateien nach Join-Key
- **SQLite** (optional): Eine Datentabelle `data` plus `column_metadata` (unit, raw_unit pro Spalte); optional `config` fuer DAMPF-Schema. DAMPF definiert das Schema; WOLKE/BLITZ bauen darauf auf. Quantitative Spalten haben nur numerische Werte; Units in `column_metadata` (Rueckfuehrbarkeit).
- Konfidenz-Score pro Datei

---

## Warum regelbasiert?

Dateinamen sind meist semi-formal.  
Regeln sind:

- deterministisch  
- reproduzierbar  
- schnell  
- gut debuggbar  

Ein Tiny-LLM oder ML-Modell ist optional sinnvoll, wenn:

- starke Variabilität in Naming-Konventionen besteht  
- viele Ambiguitäten auftreten  
- neue Konventionen automatisch erkannt werden sollen  

Baseline ist bewusst deterministisch.

---

## Erweiterung

- Neue Regex-Regeln ergänzen
- Domänenspezifische Tokens hinzufügen
- Confidence-Logik schärfen
- Optional: ML-Fallback für unbekannte Token

---

## Status

Engineering-Baseline zur strukturierten Erschliessung grosser Messdaten-Archive. GUI und SQLite-Backend implementiert; Aggregationen (Min/Max/Mittel pro Gruppe) geplant als naechster Schritt.