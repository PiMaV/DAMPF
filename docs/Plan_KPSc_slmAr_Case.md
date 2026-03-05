# Plan: KPSc, slmAr, Gross-/Kleinschreibung

## Problem

### 1. kpsc wird nicht erkannt
- **KPSc** = Kinpen Science (Produktname, einzelner Metadaten-Parameter)
- Tokenizer: `RE_LETTERS_ONLY_TOKEN` = 2–3 Zeichen. KPSc hat 4 → bleibt grau
- Loesung: Erweitern oder custom_token_map

### 2. slmar wird nicht erkannt (5slmAr wird getrennt)
- **5slmAr** = 5 slm (standard liters per minute) + Ar (Argon)
- Tokenizer splittet an Ziffer–Buchstabe: `5` + `slmar`
- `5` wird evtl. falsch als frame erkannt
- `slmar` bleibt grau – semantisch: Durchfluss + Gas
- Saubere Darstellung: gas_flow=5, unit=slm, gas=Ar

### 3. Gross-/Kleinschreibung
- Nutzer setzen CamelCase bewusst ein (KPSc, 5slmAr)
- Aktuell: alles wird zu lowercase normalisiert
- Anzeige/Export verliert die gewollte Schreibweise

---

## Option A: Hotfix (schnell)

| Thema | Massnahme | Aufwand |
|-------|-----------|---------|
| kpsc | RE_LETTERS_ONLY auf 2–4 Zeichen erweitern ODER custom_token_map: kpsc → product_name | 5 Min |
| slmar | custom_token_map: slmar → gas_flow (Wert bleibt "slmar", nicht ideal) | 0 Min (manuell) |
| 5slmAr | Tokenizer: `\d+slm[A-Za-z]+` als ein Token behalten | ~15 Min |
| Case | Zunaechst ignorieren | – |

**Einschraenkung:** slmar allein verliert die "5". Semantisch unvollstaendig.

---

## Option B: Plan (sauber)

### B1: kpsc / Produktnamen
- **Variante 1:** RE_LETTERS_ONLY auf 2–4 Zeichen
- **Variante 2:** Neuer Key `product` oder `product_name`, KPSc ueber custom_token_map
- **Variante 3:** token_patterns: `^[a-z]{4}$` → product (wenn kein anderes Muster)

### B2: 5slmAr / gas_flow
- **Tokenizer:** Vor split_transitions: `\d+slm[A-Za-z0-9]*` als ein Token behalten
- **Parser:** Neues Pattern fuer `(\d+)slm([A-Za-z0-9]+)` → gas_flow={val, unit: "slm", gas}
- Oder: zwei Keys: gas_flow=5, gas_type="Ar"

### B3: Gross-/Kleinschreibung
- **Speicherung:** Tokens intern weiterhin lowercase (Matching)
- **Anzeige:** Original-String aus Pfad speichern (`_token_original` oder aus relpath rekonstruieren)
- **Export:** Option "Original case" fuer Keys, die CamelCase haben sollen

---

## Empfehlung

| Phase | Was | Warum |
|-------|-----|-------|
| **Jetzt** | Hotfix: RE_LETTERS_ONLY 2–4, 5slmAr als ein Token | Schnell, kpsc + 5slmAr funktionieren |
| **Jetzt** | custom_token_map: kpsc → product_name (Nutzer traegt ein) | Kein Code, sofort nutzbar |
| **Spaeter** | Parser fuer 5slmAr → gas_flow + gas | Saubere Semantik |
| **Spaeter** | Case-Preservation | Groessere Aenderung |

---

## Konkrete Hotfix-Aenderungen

1. **indexer.py:** `RE_LETTERS_ONLY_TOKEN` von `{2,3}` auf `{2,4}`
2. **indexer.py:** In tokenize_string vor split_transitions: Tokens wie `5slmAr` (Zahl+slm+Buchstaben) als ein Stueck behalten – neuer Check fuer `\d+slm[a-zA-Z0-9]*`
