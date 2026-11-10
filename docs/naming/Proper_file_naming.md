# Proper Path and File names

Konvention fuer Pfade und Dateinamen; der **DAMPF-Indexer** ([../../app/dampf/indexer.py](../../app/dampf/indexer.py)) ist darauf abgestimmt und erkennt die unten genannten Muster.

**Schnellueberblick:** [Naming_Cheat_Sheet.md](Naming_Cheat_Sheet.md) | **English:** [Proper_file_naming_EN.md](Proper_file_naming_EN.md)

---

## Quick Start (4 Regeln)

1. **Trenner:** `_` (underscore) oder `-` (dash), nie Leerzeichen
2. **Einheit direkt an Zahl binden** (kein Leerzeichen): `4kV`, `10us`, `0p2us`
3. **Dezimal:** `p` bevorzugt (0p2us), Punkt `.` wird ebenfalls unterstuetzt (0.2us)
4. **Beispiel:** `2024-02-07_run1_4kV_10us_001.png` → Datum, Run, Spannung, Exposure, Frame

---

## Inhaltsverzeichnis

- [Schema](#schema)
- [Implizit vs. Explizit (key=value)](#implizit-vs-explizit-keyvalue)
- [Vom DAMPF-Indexer erkannt](#vom-dampf-indexer-erkannt)
- [Rules](#rules)
- [Erweiterung](#erweiterung-exotische-schreibweisen)

---

## Schema
| Use Case             | Char                   | Example                  |
| -------------------- | ---------------------- | ------------------------ |
| PARAMETER Separation | _ (underscore) OR Path | 4kV_10us_FF OR 4kV\10us  |
| Einheit an Zahl      | direkt, ohne Leerzeichen | 4kV, 10us, 0p2us |
| Decimal Point        | p bevorzugt, . unterstuetzt | 0p2us oder 0.2us   |
| INNER Separation (Trennung innerhalb eines Namens) | - (dash / minus) | 2020-06-21 or Slit-0p5mm |

---

## Implizit vs. Explizit (key=value)

Du kannst Parameter **implizit** (kurz) oder **explizit** (eindeutig) schreiben:

| Schreibweise | Beispiel | Bedeutung |
| ------------ | -------- | ---------- |
| **Implizit** | `4kV_10us_001.png` | Indexer erkennt: 4kV=Spannung, 10us=Exposure, 001=Frame |
| **Explizit** | `voltage=4kV_exposure=10us_frame=001.png` | Du benennst jeden Wert direkt |

**Wann explizit?**
- Eigene Parameter: `sample=ABC123`, `operator=john`, `batch=7`
- Eindeutigkeit: `temp=22p5` statt nur `22p5` (keine Verwechslung mit Strom)
- Wenn implizite Erkennung nicht greift

**Beispiele:**
```
Implizit:  run1_4kV_10us_001.png
Explizit:  run=1_voltage=4kV_exposure=10us_frame=001.png
```

Beides funktioniert; explizit ist immer eindeutig, implizit ist kuerzer.

---

## Vom DAMPF-Indexer erkannt

| Schreibweise | Beispiel-Token | Erkanntes Feld |
| ------------ | ----------------- | -------------- |
| Dezimal (`p` bevorzugt, `.` unterstuetzt) | 0p2us, 4.2kv, 22p5 | Wert als Dezimal (0.2, 4.2, 22.5) |
| Zeit | ns, us, ms, s | exposure (val+unit) |
| Spannung | v, kv, mv, uv | voltage (val+unit) |
| Strom | a, ma, ua | current (val+unit) |
| Frequenz | hz, khz, mhz, ghz | freq (val+unit) |
| Laenge/Abstand | nm, um, mm, cm, m, px | lengths |
| Temperatur | c, °c, k | temp (val+unit) |
| Datum | 2024-02-07, 20240207 | date |
| Uhrzeit (HHMMSS) | 141710 neben Datum, oder allein wenn uhrplausibel | time (`14:17:10`); nicht frame. Letzte Dateiname-Zahl bleibt frame. |
| `frame_<ch>_<n>` | frame_004_0000 | channel + frame |
| Run/Rep/Trial | run1, rep2, trial3 | run, rep, trial |
| Buchstabe(n)+Zahl (Parameter) | M25, S4, T250 | 1–3 Buchstaben + Zahl → key=value (z.B. m=25) |
| Zahl+Buchstabe(n) (Parameter) | 300He, 300N2 | Zahl + 1–3 Zeichen → key=value; He/N2/CO2 = Gasanteil in % |
| Durchfluss (slm) | 5slmAr, 10slmN2 | gas_flow (val, unit=slm, gas) |
| Nur Buchstaben (2–4 Zeichen) | FF, KPSc | String-Parameter key=value (z.B. ff=ff) |
| Laufnummer / Frame (nur Ziffern) | 000, 001, 040, 165, 07 | frame (als Integer; nackte Ziffern am Dateiende) |
| Kamera/Channel | cam1, channel2, C1, C2, C3 | camera, channel |
| key=value | beliebig | als Key-Value gespeichert |
| Processing-Tags | raw, dark, flat, avg, … | processing (Liste) |
| Modality | rgb, ir, thermal, … | modality (ueber MODALITY_MAP) |

Neue „exotische“ Schreibweisen: siehe Abschnitt **Erweiterung** unten.

---

## Rules
SPACE or "White Space" is not an option! Use dashes (-) or CamelCasing instead:
	- NoisyAndDarkEnvironment OR noisy-and-dark-environment

BAD Chars (Don't use them in names):

` \ / : * ? " < > | [ ] & $ , .

(Ausnahme: `.` in Zahlen mit Einheit wie `4.2kv` wird unterstuetzt.)

Don't use Umlauts or language special chars – use ASCII instead (oe, ae, ue, e, a).

**Pfad und Dateiname – Best Practice vs. Legacy**

- **Best Practice:** Parameter entweder im Pfad ODER im Dateinamen, nicht doppelt.
- **Legacy:** Beides wird unterstuetzt; bestehende Strukturen mit Parametern in Pfad und Dateiname funktionieren weiterhin. Bei Konflikten gilt die Dateiname-Logik.

Parameter-Bezeichner mindestens 2 Zeichen (besser 3+), damit keine Mehrdeutigkeit entsteht:
	- BAD: 4kv_10us_c_001 („c“ allein = Temperatur oder Strom?)
	- Good: 4kV_10us_c-set_001

- max. 255 chars for combined path + filename.
	- Example of a proper Path+File combination (243 chars):
	- `C:\Data\2024\ProjectX\PreTest\ExperimentNr\666\Setup1_Source4\StandardConditions_room5\10sccm_10kV_2A\ICCD-Images\150us-Exposure_250usGate_t0-1000ms\Session_2024-02-07\measurement_2024-02-07_T1500_room5_150us-Exposure_250usGate_Temp-22p5C.csv`

In the example, some information is redundant and could be reduced if necessary


DATES should be given as YYYY-MM-DD (without dash is OK; if length is an issue: YYYYMMDD)

RUNNING NUMBERS are at the end. USE Leading Zeros.
...
...\T-22_sccm1p5_Image0001.png
...\T-22_sccm1p5_Image0301.png
...\T-22_sccm1p5_Image4004.png
...

---

## Erweiterung (exotische Schreibweisen)

Um weitere Schreibweisen oder Einheiten zu unterstuetzen:

1. **Neue Wert+Einheit (z.B. sccm, bar):**
   - In [../../app/dampf/indexer.py](../../app/dampf/indexer.py): Einheit in `RE_NUMBER_UNIT` und in der passenden RE_*-Variable (`RE_LEN`, `RE_VOLT`, …) ergaenzen; ggf. neue RE_* und `unit_scale()` + Parsing in `parse_tokens()`.
   - Hier in **Vom DAMPF-Indexer erkannt** eintragen.

2. **Neue Tags / Modality / Keys:**
   - In [../../app/dampf/indexer.py](../../app/dampf/indexer.py): `MODALITY_MAP` oder `PROC_TAGS` erweitern, oder neues key=value-Pattern; ggf. neue Regex in `parse_tokens()`.
   - Hier unter „Vom DAMPF-Indexer erkannt“ dokumentieren.

3. **Projekt-spezifisch (ohne Code-Aenderung):**
   - Ueber project.json / GUI: `modality_map` und ggf. `stopwords` anpassen; erweiterbare key=value-Tokens werden bereits als solche erkannt.

**Ausreisser-Erkennung:** Bei Abweichungen vom Schema oder moeglichen Tippfehlern in Ordnernamen zeigt die DAMPF-GUI eine Outlier-Liste mit Vorschlaegen (Bereich „Ausreisser / Tippfehler“).