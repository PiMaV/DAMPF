# DAMPF TODO

- [x] Indexer refaktorisiert (config-Parameter, Modul `indexer.py`)
- [x] SQLite-Schema und Schreiblogik (`db_writer.py`)
- [x] Nomenklatur-Vorschlaege aus erkannten Feldern
- [x] Schema-Persistenz (project.json / project.ini, optional aus DB)
- [x] GUI (Root, Crawl, Schema laden/speichern, Root gemaess Schema, DB speichern, Export JSONL/CSV)
- [x] EXE-Build (PyInstaller, `dist/DAMPF.exe`)
- [ ] Ausreisser-Erkennung: Ordner-/Dateinamen die dem Schema widersprechen oder Tippfehler enthalten; z.B. 9 von 10 Ordnern folgen Schema, 1 weicht ab
- [ ] Aggregationen (Min/Max/Mittelwert pro Gruppe) – spaetere Phase
- [ ] Anbindung Wolke/Blitz (DB bzw. index/groups) – in den jeweiligen Produkten

- unique und fill empty klappt noch nicht ganz: "talita" datensatz zeigt FF als paramter an; haben aber alle, daher kann der weg


Klick auf Parameter → Samples – Sinnvoll, nicht uebertrieben. Moegliche Varianten:
Beim Auswaehlen eines Keys in Section 4 unten N Pfad-Samples nur fuer diesen Parameter anzeigen (z.B. mit hervorgehobenem Wert).
Oder eine kleine Info-Box wie „Sample values: 10, 20, 150, …“ fuer den gewaehlten Key.
Soll ich eine davon umsetzen (z.B. „bei Klick auf Parameter N Samples anzeigen“)?

Warning nicht in rot zeigen; sondern gelb!

eckige klammer : fehlt im smaple, runde klammer : fehlt bei manchen im datnesatz; ohne klammer: bei allen vorhande
was ist der key und die Abkürzung ? Brauchen wir das ? wenn ja in metadaten
den SI exponten direkt anzeigen! also bei us = -6, dass ist intuiitver
Lukas Dataset: Datum ist ein problem

reihenfolge der detexted keys stimmt noch nciht

Evtl. progressbar beim einladen?

beim KP Datensatz wird länge und "Measurement" flasch erkannt; länge hat kein SI  abwohl in mm

Generell diskutieren: macht das mit LUT sinn, oder sollten wir hier was anders eanwenden?
