# Proper Path and File names

Konvention fuer Pfade und Dateinamen; der **DAMPF-Indexer** ([indexer.py](indexer.py)) ist darauf abgestimmt und erkennt die unten genannten Muster.

---

## Schema
| Use Case             | Char                   | Example                  |
| -------------------- | ---------------------- | ------------------------ |
| PARAMETER Separation | _ (underscore) OR Path | 4kV_10us_FF OR 4kV\10us  |
| Decimal Point        | p (The char p)         | 0p2us                    |
| INNER Separation     | - (dash / minus)       | 2020-06-21 or Slit-0p5mm |

---

## Vom DAMPF-Indexer erkannt

| Schreibweise | Beispiel-Token | Erkanntes Feld |
| ------------ | ----------------- | -------------- |
| Dezimal mit `p` | 0p2us, 4p2kv, 22p5 | Wert als Dezimal (0.2, 4.2, 22.5) |
| Zeit | ns, us, ms, s | exposure (val+unit) |
| Spannung | v, kv, mv, uv | voltage (val+unit) |
| Strom | a, ma, ua | current (val+unit) |
| Frequenz | hz, khz, mhz, ghz | freq (val+unit) |
| Laenge/Abstand | nm, um, mm, cm, m, px | lengths |
| Temperatur | c, °c, k | temp (val+unit) |
| Datum | 2024-02-07, 20240207 | date |
| Run/Rep/Trial | run1, rep2, trial3 | run, rep, trial |
| Buchstabe(n)+Zahl (Parameter) | M25, S4, T250 | 1–3 Buchstaben + Zahl → key=value (z.B. m=25) |
| Zahl+Buchstabe(n) (Parameter) | 300He, 300N2 | Zahl + 1–3 Zeichen → key=value; He/N2/CO2 = Gasanteil in % |
| Nur Buchstaben (2–3 Zeichen) | FF | String-Parameter key=value (z.B. ff=ff) |
| Laufnummer / Frame (nur Ziffern) | 000, 001, 040, 165 | frame (als Integer, 3+ Ziffern) |
| Sequenz/Session (1–2 Ziffern) | 07 in 10mm_07 | seq (z.B. Session-Nr. bei identischen Werten) |
| Kamera/Channel | cam1, channel2 | camera, channel |
| key=value | beliebig | als Key-Value gespeichert |
| Processing-Tags | raw, dark, flat, avg, … | processing (Liste) |
| Modality | rgb, ir, thermal, … | modality (ueber MODALITY_MAP) |

Neue „exotische“ Schreibweisen: siehe Abschnitt **Erweiterung** unten.

---

## Rules
SPACE or "White Space" is not an option! Use dashes (-) or CamelCasing instead:
	- NoisyAndDarkEnvironment OR noisy-and-dark-environment

BAD Chars (Dont use them in Names):
`` \ / : * ? " < > | [ ] & $ , . 

Dont use Umlauts (öäü) or language special chars  (é, à, ...)
use (oe, ae, ue, e, a)

if needed, PARAMETERS can be in Path AND Filename, ONLY if they are identical. Thus, a parameter in a Path = ``...Cond-1\Set-4\T-250\...`` must be identical in filename. Example: ``...Cond-1\Set-4\T-250\4kV\Set-4_10us_001.asc

PARAMETERS must be more than a single char (at least 3):
	- BAD: 4kv_10us_c_001
	- Good: 4kV_10us_c-set_001

- max. 255 chars for combined path + filename.
	- Example of a proper Path+File Combination with a 243 char naming: 
	- `` C:\Data\2024\ProjectX\PreTest\ExperimentNr\666\Setup1_Source4\StandardConditions_room5\10sccm_10kV_2A\ICCD-Images\150us-Exposure_250usGate_t0-1000ms\Session_2024-02-07\measurement_2024-02-07_T1500_room5_150us-Exposure_250usGate_Temp-22p5C.csv

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
   - In [indexer.py](indexer.py): Einheit in `RE_NUMBER_UNIT` (Zeile ~67–71) und in der passenden RE_*-Variable (RE_LEN, RE_VOLT, …) ergaenzen; ggf. neue RE_* und `unit_scale()` + Parsing in `parse_tokens()`.
   - Hier in **Vom DAMPF-Indexer erkannt** eintragen.

2. **Neue Tags / Modality / Keys:**
   - In [indexer.py](indexer.py): `MODALITY_MAP` oder `PROC_TAGS` erweitern, oder neues key=value-Pattern; ggf. neue Regex in `parse_tokens()`.
   - Hier unter „Vom DAMPF-Indexer erkannt“ dokumentieren.

3. **Projekt-spezifisch (ohne Code-Aenderung):**
   - Ueber project.json / GUI: `modality_map` und ggf. `stopwords` anpassen; erweiterbare key=value-Tokens werden bereits als solche erkannt.