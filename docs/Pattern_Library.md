# Pattern Library – Token → Key Vorschlaege

Wissensbasis fuer "Unrecognized → Parameters". Wenn du graue Tokens siehst, schau hier nach – trage das Mapping manuell ein oder nutze spaeter Presets/Vorschlaege.

---

## Spektroskopie / MultiFil

| Token(-Muster) | Key | Beispiel |
|----------------|-----|----------|
| SyncK, SyncAA, SyncDD, SyncHH, SyncA, SyncE, … | `sync_id` | Sync-Modus |
| Gain150, Gain200 | `gain` | Verstaerkung |
| 100EE0001, 100EE0047 | `ee_id` oder `frame` | Frame/EE-ID |
| 1000ppmO2, 300He | `gas_pct` | Gasanteil (ppm/%) |
| ASCII, ASCII_LowResSync | `modality` oder `processing` | Verarbeitung |

---

## Additive Fertigung (KPSc-Cup-5slmAr-Pon)

| Token(-Muster) | Key | Beispiel |
|----------------|-----|----------|
| C1, C2, C3 | `channel` | Kanal/Charge |
| 00000, 00005, 00023 | `seq` oder `frame` | 5-stellige Sequenz |
| 5slmar, 10slmn2 | `gas_flow` | Durchfluss (slm) |
| KPSc, Cup, Pon | `setup` oder ignorieren | Setup-Konstanten |
| 0p1mm, 11p0mm, 50p0mm | `lengths` | Bereits im Schema erkannt |

---

## Allgemeine Muster

| Token-Muster | Key | Hinweis |
|--------------|-----|---------|
| Letter + 1–2 Ziffern (C1, M25) | `channel`, `m`, etc. | Schema erkennt als Param; Key-Display anpassen |
| 5–6 stellige Zahl | `seq` oder `frame` | RE_SEQ aktuell nur 1–2 Ziffern → custom_token_map |
| Zahl + ppm + Gas (1000ppmO2) | `gas_pct` | |
| Zahl + slm + Gas (5slmAr) | `gas_flow` | |

---

## Verwendung

1. **Crawl** ausfuehren
2. Graue Tokens im Path-Overview identifizieren
3. Hier nachschlagen: Token → Key
4. In GUI: Unrecognized → Parameters → Token waehlen, Key eintragen, Add
5. Save to DB – custom_token_map wird gespeichert
6. Naechstes Projekt: Load schema from DB → Mappings uebernommen

---

## Erweiterung

Neue Muster hier eintragen. Spaeter: Preset-Dateien und GUI-Vorschlaege basieren auf dieser Library.
