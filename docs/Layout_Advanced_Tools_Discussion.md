# Layout: Token Patterns, Unrecognized, Outliers – Diskussion

## Ausgangslage

Die drei Bereiche haengen aktuell an **5. Results** und wirken im Layout etwas angehaengt:

| Modul | Charakter | Nutzung |
|-------|-----------|---------|
| **Token Patterns** | Konfiguration / Eingriff | User legt Regex→Key-Regeln fest (z.B. Short-Date, eigene Domains). |
| **Unrecognized → Parameters** | Anzeige + Anpassung | Zeigt graue Tokens, User kann Token→Key mappen (Add/Remove/Batch). |
| **Outliers** | Nur Anzeige | Zeigt Pfade mit Schema-Abweichung oder Typo-Kandidaten; kaum Aenderung moeglich. |

- Token Patterns und Unrecognized sind **Profi-Werkzeuge**, werden von den meisten Nutzern kaum genutzt; koennten in spaeteren Versionen optional/entfernt werden.
- Token Patterns = aktiver **Eingriff** (Regeln definieren).
- Unrecognized = **Anzeige + Mapping** (Tokens sichtbar machen und zuordnen).
- Outliers = **reines Display** (nur informieren).

---

## Optionen

### A) Eine Kategorie „Advanced / Professional“

- **Eine** aufklappbare Sektion unter Results: z.B. **„Advanced (Token Patterns, Unrecognized, Outliers)“**.
- Beim Oeffnen: drei Sub-Bereiche (Token Patterns, Unrecognized, Outliers) untereinander oder in Tabs.
- **Vorteil:** Klar abgegrenzt, Hauptflow (Root → Crawl → Include → Keys → Results) bleibt schlank; „Advanced“ signalisiert: nur bei Bedarf.
- **Nachteil:** Ein Klick mehr; alle drei immer zusammen sichtbar, wenn man nur eines braucht.

### B) Zwei logische Gruppen

- **„Configuration“:** Token Patterns (Eingriff in die Erkennung).
- **„Inspection“:** Unrecognized (Anzeige + Mapping) + Outliers (nur Anzeige).
- Zwei Buttons/Leisten: „Token Patterns“ und „Unrecognized & Outliers“ (oder „Inspection“ mit zwei Sub-Panels).
- **Vorteil:** Trennung nach „konfigurieren“ vs „anschauen/anpassen“; Outliers bleibt beim Display-Bereich.
- **Nachteil:** Etwas mehr UI-Elemente; Begriffe muessen erklaerbar sein.

### C) Alles unter „Results“ lassen, aber klar gruppieren

- Results bleibt eine Sektion; darunter eine **einzige Leiste** z.B. **„More: Token Patterns · Unrecognized · Outliers“**.
- Klick oeffnet nur das gewaehlte Panel (oder alle als Akkordeon).
- **Vorteil:** Keine neue Hauptkategorie; „More“ macht klar: Zusatz fuer Fortgeschrittene.
- **Nachteil:** „Results“ wird langer; die drei wirken weiter als Anhaengsel, nur besser gebuendelt.

### D) Token Patterns woanders, Unrecognized + Outliers bei Results

- **Token Patterns** z.B. in einen eigenen Bereich „Schema / Patterns“ (nahe Detected Keys oder Crawl), weil es die Erkennung konfiguriert.
- **Unrecognized** und **Outliers** bleiben bei Results als reine Anzeige-/Korrektur-Tools.
- **Vorteil:** Konfiguration (Patterns) getrennt von Inspektion (Unrecognized, Outliers).
- **Nachteil:** Token Patterns verlagert sich; evtl. mehr Klicks fuer den Profi-Workflow.

---

## Umgesetzt (Stand nach Diskussion)

- **Outliers** gehoert semantisch zu **Results**: direkt unter Path Overview / Key samples. Anzeige: **„Outliers: 0“** (gruen) wenn keine, sonst **„Outliers: N“**; Klick oeffnet/schliesst die Tabelle (warum Abweichung/Typo). Checkbox „Outliers only in path overview“ bleibt darunter.
- **Advanced** ist eine eigene Gruppe darunter: **„Advanced features (work in progress)“** – enthaelt nur **Token Patterns** und **Unrecognized → Parameters**. Signalisiert: funktional, aber noch nicht fertig/evolving.

Wichtig: **Kein Hardcoding** von Breiten/Hoehen fuer diese Bereiche; sie sollen im bestehenden Layout (Splitter, Scroll) mitwachsen und weiter collapsible bleiben.

---

## Offene Punkte

1. Sollen Token Patterns und Unrecognized irgendwann **komplett ausblendbar** sein (z.B. „Profi-Tools anzeigen“ in Settings)?
2. Soll **Outliers** bei Results bleiben (nahe Path Overview) oder in „Advanced“/„Inspection“?
3. Bevorzugung: **eine** Advanced-Sektion (A/C) vs. **zwei** Gruppen Configuration vs. Inspection (B/D)?

Wenn du dich fuer eine Option entscheidest, kann das Layout (Gruppierung, Buttons, Reihenfolge) im Code gezielt angepasst werden.
