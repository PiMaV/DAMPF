# Design: Konfigurierbarkeit (B) und Lerneffekt (C)

## Ueberblick

| Option | Ziel | Kernidee |
|--------|------|----------|
| **B** | Weniger Hardcoding | Patterns (Regex, Key) aus Config/Schema statt aus Code |
| **C** | Lerneffekt | Aus Nutzer-Mappings ableiten: aehnliche Tokens → gleicher Key vorschlagen |

---

# B: Konfigurierbarkeit

## Aktuell (Hardcoded)

```
indexer.py:
  RE_RUN = r"^(?:run|r)(?P<n>\d{1,4})$"     → key "run"
  RE_CH  = r"^(?:ch|chan|channel)(?P<n>…)$" → key "channel"
  RE_LEN = r"^(?:x|y|z|…)?(?P<val>…)(?P<unit>nm|um|mm|…)$" → key "lengths"
  ...
  parse_tokens() → feste Reihenfolge, feste Keys
```

## Ziel

Nutzer/Projekt kann eigene Patterns definieren, ohne Code zu aendern. Neue Domains (z.B. Additive Fertigung) bekommen eigene Token→Key-Regeln.

## Schema-Erweiterung: `token_patterns`

```json
{
  "token_patterns": [
    {
      "key": "channel",
      "regex": "^(?:ch|chan|channel|c)(?P<n>\\d{1,4})$",
      "extract": "int",
      "capture_group": "n"
    },
    {
      "key": "seq",
      "regex": "^(?P<n>\\d{1,6})$",
      "extract": "int",
      "capture_group": "n",
      "priority": 10
    },
    {
      "key": "gas_flow",
      "regex": "^(?P<val>\\d+(?:p\\d+)?)slm(?P<gas>[a-z0-9]{1,3})$",
      "extract": "val_unit",
      "unit": "slm"
    }
  ]
}
```

### Pattern-Typen

| extract | Bedeutung | Beispiel |
|---------|------------|----------|
| `int` | Eine Zahl | run, rep, channel, frame |
| `str` | String | modality, processing |
| `val_unit` | Zahl + Einheit | lengths, exposure, voltage |
| `kv` | key=value | bereits RE_KV |

### Reihenfolge / Prioritaet

- Built-in Patterns zuerst (date, run, rep, …) – unveraenderbar
- `token_patterns` aus Schema danach
- `custom_token_map` als Fallback (exakte Token→Key)

### Konflikt: Gleicher Token, mehrere Patterns

- Erster Match gewinnt (wie jetzt)
- `priority` (optional): hoeher = frueher pruefen

## Implementierung B (Stufen)

### B1: Schema + Parser-Hook (minimal)

- `token_patterns` in DEFAULT_SCHEMA, schema_to_config
- In `parse_tokens`: nach Built-in, vor custom_token_map: user patterns durchgehen
- Format: `{"key": "seq", "regex": "^(?P<n>\\d{1,6})$", "extract": "int", "capture_group": "n"}`

### B2: GUI zum Bearbeiten

- Neuer Tab/Section "Token Patterns"
- Tabelle: Key | Regex | Extract | Prioritaet
- Add/Remove/Edit
- Speichern in project.json, DB

### B3: Presets fuer Domains

- `presets/additive.json`: token_patterns fuer C1→channel, 00000→seq, 5slmar→gas_flow
- "Load preset" laedt token_patterns + ggf. custom_token_map

## Abgrenzung

- **Built-in** bleibt: date, run, rep, exposure, voltage, lengths, … (Basis)
- **token_patterns** erweitert: domain-spezifische Regexes
- **custom_token_map** bleibt: exakte Token→Key (kein Regex)

---

# C: Lerneffekt

## Aktuell

- Kein Lernen
- custom_token_map: Nutzer traegt manuell ein
- Keine Vorschlaege aus Historie

## Ziel

Aus bestehenden Mappings ableiten: "C1→channel, also C2, C3 wahrscheinlich auch channel" – Vorschlag anzeigen, ein Klick uebernimmt.

## Lernquellen

| Quelle | Inhalt | Wo gespeichert |
|--------|--------|-----------------|
| **Aktuelles Projekt** | custom_token_map | Schema, DB |
| **Geladene Schemas** | custom_token_map aus anderer DB | – |
| **Nutzer-Aktionen** | "Nutzer hat C1→channel gemappt" | optional: user_prefs.json |

## Lernlogik (ohne ML)

### C1: Muster-basierte Vorschlaege

**Regel:** Wenn Token T1 auf Key K gemappt ist, und T2 dem gleichen Muster folgt → schlage K fuer T2 vor.

| T1 (gemappt) | T2 (grau) | Muster | Vorschlag |
|--------------|------------|--------|-----------|
| C1 → channel | C2, C3 | `C\d+` | channel |
| SyncK → sync_id | SyncAA, SyncDD | `Sync[A-Z]+` | sync_id |
| 00000 → seq | 00005, 00023 | `\d{5,6}` | seq |
| Gain150 → gain | Gain200 | `Gain\d+` | gain |

**Implementierung:**
1. custom_token_map durchgehen: Token → Key
2. Fuer jeden grauen Token: Passt er zu einem bekannten Muster?
3. Muster = Regex aus Token ableiten: C1 → `^c\d+$`, SyncK → `^sync[a-z]+$`
4. Wenn grauer Token matcht → "→ channel?" anzeigen

### C2: Token-Familien

**Regel:** Tokens mit gleichem Praefix/Suffix gruppieren.

- SyncK, SyncAA, SyncDD → Praefix "sync"
- 00000, 00005, 00023 → alle 5-stellig
- C1, C2, C3 → Praefix "c"

**Implementierung:** Beim Sammeln der grauen Tokens: Gruppieren nach Muster. Wenn eine Gruppe schon teilweise gemappt ist → Rest vorschlagen.

### C3: Historie (optional, spaeter)

- Speichern: "Nutzer hat in Projekt X C1→channel gemappt"
- Beim naechsten Projekt: "C1 wurde schonmal als channel verwendet. Uebernehmen?"
- Speicherort: user_prefs.json oder projektuebergreifende DB

## Implementierung C (Stufen)

### C1: Vorschlaege im Unrecognized-Panel (minimal)

- `suggest_key_for_token(token, custom_token_map, unrec_tokens)`:
  - Fuer jedes (t, k) in custom_token_map: Generiere Muster aus t (z.B. C1 → `c\d+`)
  - Wenn token matcht → return k
- In GUI: Bei Token-Auswahl Key-Edit mit Vorschlag vorfuellen: "channel?"
- Button "Apply suggestion" oder Auto-Fill beim Fokus

### C2: Batch-Vorschlag

- "C2, C3 passen zum gleichen Muster wie C1 (→ channel). Alle zu channel mappen?"
- Ein Klick → custom_token_map erweitert um C2→channel, C3→channel

### C3: Muster → token_patterns (B+C verbinden)

- Nutzer mappt C1→channel
- System schlaegt vor: "Muster C* zu channel? Als token_pattern speichern?"
- Wenn ja: token_pattern hinzufuegen `{"key": "channel", "regex": "^c\\d+$", …}`
- Ab dann: C4, C5 werden automatisch erkannt (kein custom_token_map mehr noetig)

## Muster-Generierung aus Token

Einfache Heuristik (kein ML):

| Token | Generiertes Muster | Regex |
|-------|--------------------|-------|
| C1 | Buchstabe(n) + Ziffern | `^c\d+$` |
| C2 | (gleiche Familie) | `^c\d+$` |
| SyncK | Sync + Buchstaben | `^sync[a-z]+$` |
| SyncAA | (gleiche Familie) | `^sync[a-z]+$` |
| 00000 | N-stellige Zahl | `^\d{5}$` |
| Gain150 | Wort + Zahl | `^gain\d+$` |

**Regel:** 
- Wenn Token = `([a-z]+)(\d+)` → Muster `^<letters>\d+$`
- Wenn Token = `(\d+)([a-z]+)` → Muster `^\d+<letters>$`
- Wenn Token = `\d+` nur → Muster `^\d{len}$`

---

# Implementierungsreihenfolge

| Phase | B | C | Beschreibung |
|-------|---|---|--------------|
| 1 | B1 | C1 | token_patterns im Schema; Parser nutzt sie. Vorschlaege im Panel. |
| 2 | B2 | C2 | GUI fuer token_patterns. Batch-Vorschlag "alle C* → channel". |
| 3 | B3 | C3 | Presets. Muster aus Mapping → token_pattern vorschlagen. |

## Geschaetzter Aufwand

- **B1:** ~2–3h (Schema, parse_tokens erweitern)
- **C1:** ~1–2h (suggest_key_for_token, GUI vorfuellen)
- **B2:** ~2h (GUI-Tab)
- **C2:** ~1–2h (Batch-Vorschlag-Button)
- **B3 + C3:** ~2h (Presets, Muster→Pattern)

---

# D: Rudimentaeres Learning / KI – wann sinnvoll?

## microgpt (Karpathy) – Overkill?

[microgpt](https://karpathy.github.io/2026/02/12/microgpt/) ist ein minimales GPT (~200 Zeilen, keine Dependencies): trainiert auf Namen, generiert neue Namen. Next-token prediction.

**DAMPF braucht:** Token → Key (Klassifikation), nicht Sequenz-Generierung.

| microgpt | DAMPF |
|----------|-------|
| Input: Sequenz von Tokens | Input: einzelner Token |
| Output: naechster Token (Generierung) | Output: Key (Klassifikation) |
| Training: viele Dokumente | Training: custom_token_map (paar Dutzend Paare) |

**Fazit:** microgpt ist fuer unseren Use-Case Overkill. Wir brauchen keinen Transformer, keine Attention, keine Sequenz-Modellierung.

---

## Wann waere "echtes" Learning sinnvoll?

| Szenario | Regelbasiert (C) | Kleines NN |
|----------|-----------------|------------|
| C1, C2, C3 → channel | Regex ^c\d+$ reicht | Ueberfluss |
| SyncK, SyncAA → sync_id | Praefix-Muster reicht | Ueberfluss |
| Tippfehler: reuslts_left → results_left | Schwer | Embedding + Ahnlichkeit |
| Semantisch: ch1, channel_1, C1 → channel | Mehrere Regexes | Ein Modell lernt Ahnlichkeit |
| 1000+ verschiedene Token-Typen | Viele Regexes | Modell generalisiert |

**Regel:** Erst C (Heuristik) ausreizen. NN nur wenn Muster zu komplex oder Daten zu unsauber (Typos, Varianten).

---

## Rudimentaeres Learning – minimal implementierbar

Falls wir doch "was mit KI" wollen: **kein microgpt**, sondern ein winziger Klassifikator.

### Ansatz: Charakter-Level + Linear

```
Input: Token "C1" → [c, 1] als Indizes
Embedding: jeder Char → Vektor (learned)
Token-Repraesentation: Mean/Max der Char-Embeddings
Output: Linear → Num Keys (channel, seq, sync_id, …)
Loss: Cross-Entropy
Training: (token, key) aus custom_token_map
```

- ~50–100 Zeilen
- Keine Dependencies (nur numpy, oder pure Python)
- Training: wenn Nutzer custom_token_map aendert, 1–2 Sekunden
- Inference: Token → Key mit Confidence

### Noch simpler: k-Nearest-Neighbors

- Keine Training-Loop
- Token als String → einfaches Feature (Laenge, Praefix, Suffix, enthaelt_Ziffer, …)
- custom_token_map = "Trainingsdaten"
- Neuer Token: finde aehnlichsten bekannten Token (z.B. Levenshtein, oder Feature-Vektor)
- Vorschlag: Key des aehnlichsten

```python
def suggest_key(token: str, custom_token_map: dict) -> str | None:
    if not custom_token_map:
        return None
    best_key, best_dist = None, float("inf")
    for t, k in custom_token_map.items():
        d = levenshtein(token.lower(), t.lower())
        if d < best_dist:
            best_dist, best_key = d, k
    return best_key if best_dist <= 3 else None  # nur bei aehnlichkeit
```

- Typos: "reuslts_left" → naechster "results_left" → key
- Kein Training, sofort einsetzbar

---

## Empfehlung

| Phase | Was | Warum |
|-------|-----|-------|
| 1 | C (Heuristik) | C1→channel → C2,C3 vorschlagen. Kein NN noetig. |
| 2 | k-NN / Levenshtein | Typos, Varianten. Minimal, keine Dependencies. |
| 3 | Kleiner Klassifikator | Nur wenn k-NN nicht reicht (viele Keys, komplexe Ahnlichkeit). |

**microgpt:** Nicht verwenden. Falsche Architektur, zu schwer fuer die Aufgabe.

**Rudimentaer:** Ja – aber k-NN oder 50-Zeilen-MLP, nicht GPT.
