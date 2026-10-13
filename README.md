# Binär-Experiment: Kann ein KI-Modell Programme direkt als Maschinencode schreiben?

Ein Sprachmodell bekommt eine Programmieraufgabe und muss die fertige, ausführbare Datei als rohe Bytes
abliefern: eine komplette ELF64-Datei für Linux x86-64 als Hexdump, ohne Compiler und ohne Assembler.
Zum Vergleich löst es dieselbe Aufgabe in C, das gcc übersetzt. Neun Aufgaben steigender Größe
(aufgaben.py) von "Hallo Welt" bis zu einem kleinen Interpreter mit Funktionen und Rekursion.

**Ergebnis in Kürze** (Stand 13.10.2026, Details in [ERGEBNIS.md](ERGEBNIS.md)): Claude Opus 4.8 schreibt
korrekten Maschinencode bis etwa 900 Byte (T8, Variablenrechner), mit höchstens einer Korrekturrunde, braucht
dafür aber 40- bis 60-mal so viele Tokens wie für die C-Lösung. Bei rund 1,5 KB (T9, Funktionsrechner) bricht
es ein: vier Versuche mit je 128000 Tokens Denken, keine einzige Datei. C hält bei allen Größen. Claude Opus 5.5
lehnt Binär-Anfragen über die API fast immer per Sicherheitsfilter ab; das 1-Bit-quantisierte Bonsai 27B
schaffte kein einziges lauffähiges Binary. Alle Modellantworten, Denkzusammenfassungen und Rückmeldungen
liegen unter laeufe/.

Prüfstand: je Aufgabe Läufe im Modus `bin` (ELF64 als Hex) und `c` (C-Quelltext, gcc -O2), wahlweise mit
Rundenmodus, in dem das Modell nach Bau- und Testergebnis nachbessern darf.

## Voraussetzungen
Linux x86-64, Python 3, gcc. Keine Zusatzpakete.

## Lokales Modell testen (z. B. Bonsai über llama.cpp)
1. Server starten, z. B. `llama-server -m <modell.gguf> --port 8080 -c 32768`
2. Antworten holen:
   `python3 frage_modell.py --url http://localhost:8080/v1 --name bonsai27b --laeufe 3`
   Schon vorhandene Antworten werden übersprungen, ein Abbruch lässt sich also einfach fortsetzen.
   Dauer und Tokenzahl je Anfrage stehen in laeufe/<name>/protokoll.jsonl.
3. Prüfen: `python3 pruefen.py laeufe/bonsai27b`
   Ergebnis je Datei auf dem Bildschirm, Zusammenfassung am Ende, Details in ergebnisse.json.

Nützliche Schalter: `--aufgaben T1,T2`, `--modi bin`, `--max_tokens 32768`, `--temperatur 0.2`.
Denkende Modelle brauchen viel Platz: bei Abschneiden `--max_tokens` erhöhen. Steht der Hexblock
mehrfach in der Antwort, wertet pruefen.py den letzten.

## Claude direkt über die API (seit v2)
Läuft auf jedem Linux-Rechner, unter Windows in WSL (Ubuntu). Einmalig `gcc`, `binutils` und das Python-Paket
`anthropic` installieren, den API-Schlüssel als `ANTHROPIC_API_KEY` setzen, dann z. B.:
`python3 frage_modell.py --anbieter anthropic --name claude_runden --aufgaben T1,T4,T7 --modi bin_runden,c_runden --laeufe 2 --runden 4 --parallel 4`
Standard: claude-opus-5-5, adaptives Denken, effort high (`--reasoning_effort`), max_tokens 64000.
Lehnt der Sicherheitsfilter eine Anfrage ab, steht das als Ablehnung samt Kategorie im Protokoll
und in ergebnisse.json; ohne weiteren Schalter wird kein anderes Modell als Ersatz benutzt.

## Ersatzmodell bei Ablehnung (seit v3, `--ersatz`)
Lauf 3 (ERGEBNIS.md) zeigte, dass der Sicherheitsfilter über die API fast alle Binär-Anfragen ablehnt (Kategorie cyber).
Mit `--ersatz` nutzt frage_modell.py den serverseitigen Ersatz der Anthropic-API (Beta `server-side-fallback-2026-07-01`,
`fallbacks=default`): Opus 5.5 bleibt das angefragte Modell, bei einer Ablehnung wiederholt Anthropic dieselbe Anfrage
auf dem für die Kategorie vorgesehenen Ersatzmodell (bei cyber derzeit Claude Opus 4.8). Welches Modell geantwortet hat,
steht je Anfrage in protokoll.jsonl (`usage.modell`, bei Ersatz zusätzlich `usage.ersatz` und `usage.ersatz_wechsel`),
pruefen.py zeigt es als `[Ersatz: ...]` und schreibt es als `ersatz` in ergebnisse.json. Hinweis: Nach einem Wechsel
leitet Anthropic gleiche Anfragen etwa eine Stunde lang direkt zum Ersatzmodell; auch das wird als Ersatz vermerkt.
Ersatzläufe gehören in einen eigenen Laufordner, damit die Modelle nicht vermischt werden, z. B.:
`python3 frage_modell.py --anbieter anthropic --ersatz --name claude_ersatz --aufgaben T1,T4,T7 --modi bin_runden,c_runden --laeufe 2 --runden 4 --parallel 4`

## Rundenmodus (seit v2)
`--modi bin_runden,c_runden` lässt das Modell nachbessern: Nach jeder Abgabe wird gebaut und getestet,
bei einem Fehlschlag bekommt das Modell Testfall, erwartete und tatsächliche Ausgabe, Exit-Code bzw.
Signal und bei binär zusätzlich `readelf -h -l` und eine objdump-Disassemblierung seiner eigenen Bytes.
Höchstens `--runden` Abgaben (Standard 5). Die Werkzeuge lesen nur, Code erzeugt allein das Modell.
Ergebnis je Lauf: letzte Abgabe in `<Aufgabe>_<Modus>_<Lauf>.txt`, alle Runden samt Rückmeldung in
`runden/`, benötigte Runden in protokoll.jsonl und ergebnisse.json (`runden`).
Beispiel: `python3 frage_modell.py --name test --aufgaben T1,T7 --modi bin_runden,c_runden --runden 4`
Neue Aufgabe T7 (Ausdrucksrechner mit + - * /, Klammern, Punkt vor Strich, 10 Tests) braucht
schätzungsweise 1 bis 2 KB Maschinencode und liegt damit deutlich über T1 bis T6.

## Versuch bin_offsets (zurückgebaut)
Lauf 7 (ERGEBNIS.md) hat getestet, ob es hilft, wenn das Modell die Bytes zeilenweise mit Dateioffset und Kommentar
ausgibt. Ergebnis: keine Offset-Fehler, gleiche Fehlerarten, kein messbarer Tokenvorteil. Der Modus ist aus
frage_modell.py entfernt; pruefen.py kann das Format weiterhin lesen, damit laeufe/claude_opus48_offsets nachprüfbar bleibt.
Doppelstart-Schutz: frage_modell.py legt laeufe/<name>/lauf.pid an und verweigert einen zweiten Start auf denselben Ordner.

## Aufgaben vergrößern
Neue Aufgabe in aufgaben.py eintragen (Text plus Testfälle mit stdin, args, erwartet), z. B. T9, T10 ...
Ziel ist die Größe zu finden, ab der Binär einbricht und C noch hält.
T8 (seit v3, Variablenrechner): T7 plus Variablen, Zuweisungen, print-Zeilen, Rest-Operator %, Lesen bis Dateiende,
10 Tests (bis 26 Variablen, 700 Byte Programm). Erwartete Ausgaben sind gegen einen Referenz-Interpreter und eine
C-Lösung geprüft. Geschätzt 1 bis 1,5 KB Maschinencode, also etwa das Doppelte von T7.
Lauf mit Opus 4.8 (Opus 5.5 lehnt Binär über die API meist ab, siehe ERGEBNIS.md Lauf 3):
`python3 frage_modell.py --anbieter anthropic --modell claude-opus-4-8 --name claude_opus48_T8 --aufgaben T8 --modi bin_runden,c_runden --laeufe 2 --runden 4 --parallel 4`
T9 (seit v3, Funktionsrechner): T8 plus Funktionsdefinitionen mit 1 bis 4 Parametern, Vergleiche, Bedingungsausdruck
`? :` mit Auswertung nur des gewählten Zweigs, Rekursion bis Tiefe 200. 10 Tests (Fakultät, ggT, Fibonacci rekursiv mit
21891 Aufrufen, Collatz, Rangfolge). Geprüft wie T8 mit Referenz-Interpreter und C-Lösung. Neu gegenüber T8 sind
Aufrufrahmen mit lokalen Parametern über einem rekursiven Parser. Weil T7 schon einmal 64000 Tokens in einer Runde
verbraucht hat, mit größerer Antwortgrenze starten:
`python3 frage_modell.py --anbieter anthropic --modell claude-opus-4-8 --name claude_opus48_T9 --aufgaben T9 --modi bin_runden,c_runden --laeufe 2 --runden 4 --parallel 4 --max_tokens 128000`

## Sicherheit
pruefen.py führt die vom Modell erzeugten Programme aus. Die Aufgaben sind harmlos, das Modell ist
aber nicht geprüft: am besten in einer VM, einem Container oder unter einem eigenen Benutzer laufen lassen.

## RunPod
Kompletter Lauf in einem Pod: siehe runpod/ANLEITUNG.md

## Lizenz

MIT, siehe [LICENSE](LICENSE).

Das gilt für den Code und die Auswertungen in diesem Repo. llama.cpp (MIT), das Anthropic-SDK (MIT) und das Bonsai-Modell (Apache-2.0) sind nicht enthalten, sie werden beim Einrichten geladen und behalten ihre eigenen Lizenzen.
