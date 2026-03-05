# DAMPF v1.0 – Status und Roadmap

## Ziel: Produkt-Launch

**v1.0 = Proper_file_naming funktioniert zu 100%.** Nutzer, die sich an die Konvention halten, bekommen alles korrekt erkannt. Ohne Ueberforderung – Cheat Sheet zeigt kurz, wie es geht.

---

## Was ist bereits implementiert

| Bereich | Status |
|---------|--------|
| **Proper_file_naming** | Doku + Cheat Sheet vorhanden |
| **Indexer** | Erkennt: date, run, rep, exposure, voltage, lengths, frame, cam, channel, key=value, M25, 300He, FF, etc. |
| **GUI** | Crawl, Keys, Pfad-Overview (farbig/grau), Save to DB, Export |
| **Erweiterung** | modality_map, stopwords, custom_token_map ueber project.json/DB |

---

## Was fuer v1.0 noetig ist

1. ~~**Audit:** Proper_file_naming vs. Indexer~~ – erledigt
2. ~~**Luecken schliessen:** RE_CH +c (C1,C2,C3→channel), RE_LETTERS 2–4 (KPSc)~~ – erledigt
3. **Keine neuen Features** – nur Korrektheit

---

## Optional (nicht fuer v1.0)

| Feature | Rolle |
|---------|-------|
| **custom_token_map** | Eigene Token→Key ueber JSON/DB. Domain-spezifisch (z.B. Plasma-Physik). Einfache Lookup-Tabelle. |
| **Grau-Maske** | Einfache Oberflaeche zum Fuellen grauer Tokens – falls Nutzer von der Konvention abweicht |
| **Vorschlaege, Batch** | Zurueckgestellt – nicht noetig fuer v1.0 |

---

## Domain-agnostisch vs. domain-spezifisch

| Typ | Beispiele | Wo |
|-----|-----------|-----|
| **Domain-agnostisch** | frame, date, run, exposure, voltage, lengths | In Proper_file_naming, Indexer built-in |
| **Domain-spezifisch** | KPSc, 5slmAr, SyncK | custom_token_map oder key=value (explizit) |

**Fuer v1.0:** Domain-agnostische Sachen muessen stimmen. Domain-spezifisch ueber key=value (explizit) oder custom_token_map – schlank, ohne Ueberbau.

---

## Konkrete Schritte zu v1.0

1. **Proper_file_naming** – Tabelle "Vom DAMPF-Indexer erkannt" durchgehen
2. **Indexer** – Jedes Muster testen, Luecken dokumentieren
3. **Luecken beheben** – Nur was in der Konvention steht
4. **Cheat Sheet** – Bleibt der One-Pager, keine Ueberladung

---

## Nicht tun

- Kein komplexer Rack-X-Crawler fuer chaotische Daten
- Keine Ueberladung mit Vorschlaege/Batch/Patterns
- Nutzer nicht mit zu viel Konfiguration ueberfordern
