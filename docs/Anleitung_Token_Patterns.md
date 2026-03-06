# Token Patterns: Eigene Muster anlegen und aendern

Kurze Anleitung, wie Sie eigene Erkennungsregeln (Regex → Key) anlegen und bearbeiten. **Datum** (inkl. Kurzform wie `22_01_26`) ist die Grenze zum Chaos: Darueber hinaus helfen nur noch Token Patterns oder exakte Zuordnungen.

---

## Kurz-Datum (z.B. 22_01_26) – ueber Token Patterns

- Tokens mit **6 Ziffern und Trenner** (z.B. `22_01_26`) als Datum: **Token Patterns** oeffnen, Zeile hinzufuegen:
  - **Key:** `date`
  - **Regex:** `^(?P<a>\d{2})[-_\.](?P<b>\d{2})[-_\.](?P<c>\d{2})$`
  - **Extract:** `date_short_YY` (22_01_26 = 2022-01-26) **oder** `date_short_DM` (22_01_26 = 2026-01-22, 22=Tag, 26=Jahr)
- Nur **eine** der beiden Zeilen behalten (YY oder DM), je nach Tagierung.

---

## Was sind Token Patterns?

- **Token Patterns** = Regeln, mit denen Pfadteile (Tokens) automatisch einem Parameter (Key) zugeordnet werden.
- Sie werden **beim naechsten Crawl** angewendet (nach den festen Regeln, vor den exakten Token→Key-Zuordnungen).
- Beispiel: Alle Tokens der Form `C1`, `C2`, `ch3` → Key **channel**.

---

## So legen Sie ein neues Pattern an

1. **Bereich oeffnen:** Unter "Ergebnisse" auf **Token Patterns** klicken (einklappbarer Bereich, liegt ueber "Unrecognized -> Parameters").
2. **Zeile hinzufuegen:** Button **Add** klicken → neue Zeile in der Tabelle.
3. **Spalten ausfuellen:**
   - **Key:** Parametername (z. B. `channel`, `seq`, `gain`).
   - **Regex:** Regulaerer Ausdruck, der den Token matcht, mit benannter Gruppe fuer den Wert (z. B. `^(?:c|ch)(?P<n>\d+)$`).
   - **Extract:** Art des Werts – `int`, `str`, `val_unit` (Zahl+Einheit), `date_short_YY`, `date_short_DM` (Kurz-Datum).
   - **Priority:** Zahl (optional); hoeher = Regel wird frueher geprueft.
4. **Speichern:** Beim naechsten **Crawl** oder **Save to DB** werden die Patterns uebernommen.

---

## So aendern oder loeschen Sie Patterns

- **Aendern:** In der Tabelle die Zelle anklicken und Text bearbeiten. Aenderungen gehen sofort in die Konfiguration ein.
- **Loeschen:** Zeile(n) in der Tabelle markieren → Button **Remove selected**.
- **Gueltigkeit:** Ungueltige Regex-Zeilen werden beim Crawl/Save ignoriert (kein Absturz).

---

## Kurz-Ueberblick

| Aktion        | Vorgehen                                      |
|---------------|-----------------------------------------------|
| Neues Pattern | Token Patterns oeffnen → **Add** → Key, Regex, Extract, Priority eintragen. |
| Pattern aendern | Zelle in der Tabelle anklicken und bearbeiten. |
| Pattern loeschen | Zeile auswaehlen → **Remove selected**.       |
| Uebernehmen   | **Crawl** starten oder **Save to DB** – dann gelten die Patterns. |

---

*Siehe auch: [Design_Configurable_and_Learning.md](Design_Configurable_and_Learning.md) (Format, Extract-Typen).*
