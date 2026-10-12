# Experiment: Maschinencode direkt vs. C mit Compiler (12.10.2026)

Je Aufgabe 3 unabhängige Modell-Instanzen (Claude Opus 5.5) ohne Werkzeuge, nur ein Write-Aufruf.
Binär: komplette ELF64-Datei als Hex, statisch, nur Syscalls. C: Quelltext, gcc -O2.
Prüfung automatisch mit pruefen.py (Testfälle in aufgaben.py), Ergebnisse in ergebnisse.json.

| Aufgabe | Binär abgegeben | Binär korrekt | Binär Größe | C korrekt | C Größe* |
|---|---|---|---|---|---|
| T1 Hallo Welt | 3/3 | 3/3 | 162–164 B | 3/3 | 15960 B |
| T2 Rechnen | 3/3 | 3/3 | 190–211 B | 3/3 | 15968 B |
| T3 FizzBuzz | 1/3 | 1/1 | 309 B | 3/3 | 16008 B |
| T4 Zeile umkehren | 3/3 | 3/3 | 213–233 B | 3/3 | ~16250 B |
| T5 Zeilen zählen | 3/3 | 3/3 | 239–246 B | 3/3 | 16360 B |
| T6 Sortieren | 0/3 | – | – | 3/3 | 16136 B |

*C-Binaries dynamisch gegen libc gelinkt, libc selbst nicht mitgezählt.

Befunde:
- Jedes abgegebene Binary lief beim ersten Versuch fehlerfrei durch alle Tests (13/13). T2 rechnet wirklich (imul im Code geprüft).
- 5 von 18 Binär-Läufen ohne Abgabe: 4 meldeten, ein Sicherheitsfilter habe die Ausgabe abgebrochen, 1 wurde unterbrochen. Lange rohe Maschinencode-Ausgaben ähneln offenbar Shellcode. T6 binär daher nicht messbar.
- Zeitaufwand: Binär 16–170 s je Lauf, C 4–8 s.
- Einschränkung: Regeltreue (nur Write) ist über tool_uses=1 je Agent belegt; kleine Stichprobe (3 je Zelle).

# Lauf 2: Ternary-Bonsai-2-27B PTQ1_0 auf RunPod (12.10.2026)
RTX PRO 4000 Blackwell 24 GB, PrismML-llama.cpp, Denkstufe medium, Denkbudget 24000, max. 30000 Tokens.
Dauer 88 min (11:30 bis 12:58 UTC). Je Aufgabe 3 Läufe pro Modus.

| Aufgabe | Binär | C |
|---|---|---|
| T1 Hallo Welt | 0/3 | 3/3 |
| T2 Rechnen | 0/3 | 3/3 |
| T3 FizzBuzz | 0/3 | 3/3 |
| T4 Zeile umkehren | 0/3 | 3/3 |
| T5 Zeilen zählen | 0/3 | 2/3 |
| T6 Sortieren | 0/3 | 3/3 |
| Summe | 0/18 | 17/18 |

Binär-Fehler: 11x "Exec format error" (ELF-Kopf fehlerhaft: Kennungsblock zu kurz, Typ/Maschine als
4 statt 2 Byte, einmal Maschinenkennung 60 statt 62), 5x Schleife in der Antwort (endlose Nullbytes),
1x ungerade Hexlänge, 1x keine Abgabe. Kein Binary kam bis zur Ausführung des Programmcodes.
Aufwand: Binär 5 bis 11 min / 15000 bis 30000 Tokens je Versuch, C 4 bis 28 s / 200 bis 1400 Tokens.
Vergleich Claude Opus 5.5 (Lauf 1): Binär 13/13 abgegebene korrekt, C 18/18.
Nächster Schritt: gleicher Lauf mit Ternary-Bonsai-2-27B-F16.gguf (80-GB-GPU), um Quantisierung als Ursache zu prüfen.

Nachanalyse (Gegenprobe mit pruefen.py lokal: identische Tabelle):
- Kopffehler sehr unterschiedlich: Typ 1 (REL) statt 2 (EXEC) in 4 Dateien, Maschinenkennung 0/2/59/60 statt 62,
  Kennungsblock falsch in 6, ELF-Magic selbst falsch in 3. Nur T4_bin_1 hatte die ersten 24 Byte korrekt.
- Probeweise nur Typ und Maschine korrigiert (5 Dateien mit wenigen Kopffehlern): 3 weiter "Exec format error"
  (Programmkopf fehlerhaft, kein LOAD-Segment), 2 starten, stürzen aber sofort ab (SIGSEGV). Fehler sitzen also
  auch tiefer, nicht nur in einem Feld.
- Einziger C-Fehler T5_c_1: Puffer als int-Feld statt char deklariert, vergleicht 4 Byte am Stück mit '\n' -> Ausgabe 0.
- Gesamtaufwand: Binär 459.586 Tokens / 169 min Rechenzeit, C 12.981 Tokens / 4,5 min (Faktor ~35 bei Tokens).

# Lauf 3: Claude Opus 5.5 direkt über die API, Rundenmodus (12.10.2026, 20:24 Uhr)

frage_modell.py --anbieter anthropic, Aufgaben T1, T4, T7, Modi bin_runden und c_runden, je 2 Läufe, bis zu 4 Runden,
adaptives Denken, effort high, max_tokens 64000. Anders als Lauf 1 kein Agent mit Write-Werkzeug, sondern reine
Textantwort über die Messages-API. Rauchtest 20:22 Uhr: T1 bin_runden 1/1, korrekt in Runde 1 (162 B, 14 s, 1673 Tokens).

| Aufgabe | Binär | C | C Größe | C Runden |
|---|---|---|---|---|
| T1 Hallo Welt | 0/2 | 2/2 | 15968 B | 1 |
| T4 Zeile umkehren | 0/2 | 0/2 | – | – |
| T7 Ausdrucksrechner | 0/2 | 2/2 | 16208–16264 B | 1 |
| Summe | 0/6 | 4/6 | | |

Alle 8 Fehlschläge sind Ablehnungen durch den Sicherheitsfilter, stop_reason refusal, Kategorie cyber. Kein einziger
Binär-Lauf kam bis zur Abgabe, auch die zwei C-Läufe zu T4 wurden abgelehnt. Gesamtdauer des Laufs rund 1 Minute,
Kosten vernachlässigbar (Binär 3775, C 3008 Ausgabe-Tokens insgesamt).

Befunde:
- Die Ablehnung ist nicht deterministisch: derselbe Prompt (T1 bin_runden, nur "höchstens 2" statt "höchstens 4 Abgaben")
  lief im Rauchtest 2 Minuten vorher fehlerfrei durch. In Lauf 1 (Claude Code, Write-Werkzeug) kamen 13 von 18 Binär-Läufen durch.
- Zwei Arten von Ablehnung: sofort ohne Ausgabe (T4 C beide Male 0 Tokens, 1 bis 2 s) und mitten im Strom (T1 bin 2:
  1024 Tokens, die Denkzusammenfassung beschreibt bereits ELF-Kopf und write/exit-Syscalls; T7 bin 2: 1418 Tokens, das Modell
  plante einen rekursiven Abstiegsparser in Maschinencode, Abbruch bei "Writing raw assembly/machine code").
- T4 C ist auffällig: "Zeile umkehren" als C-Quelltext wurde zweimal sofort abgelehnt, während T1 C und T7 C (deutlich
  komplexer) durchliefen. In Lauf 1 war T4 C 3/3. Worauf der Filter anspringt, ist von außen nicht erkennbar.
- C-Ergebnis wo nicht abgelehnt: 4/4 in Runde 1, T7 (Ausdrucksrechner, 10 Tests) mit rekursivem Abstieg in 12 s
  und rund 1400 Tokens. Der Rundenmodus wurde damit nie gebraucht, es gibt keine Daten zur Nachbesserung.
- Folge für das Experiment: Über die API lässt sich die eigentliche Frage (bis zu welcher Größe hält Binär) mit Claude
  derzeit nicht messen, weil der Filter die Binär-Anfragen praktisch vollständig blockt (1 von 7 Versuchen in dieser
  Sitzung durchgekommen, inkl. Rauchtest). Gemäß README wird bewusst kein Ersatzmodell eingesetzt.
- Nächste Möglichkeiten: Ablehnungsrate über mehrere Wiederholungen messen (ein Lauf kostet Cent-Beträge), oder
  Binär-Läufe wie in Lauf 1 über Claude Code fahren, wo die Durchlassquote höher war.

# Lauf 4: Claude Opus 5.5 mit serverseitigem Ersatzmodell (12.10.2026, 20:55 Uhr)

Gleicher Aufbau wie Lauf 3, zusätzlich `--ersatz` (Anthropic-Beta `fallbacks=default`): angefragt wird Opus 5.5, lehnt
der Sicherheitsfilter ab, wiederholt Anthropic dieselbe Anfrage auf Opus 4.8. Das antwortende Modell steht je Lauf im
Protokoll. Achtung: gemischte Modelle, kein sauberer Binär-gegen-C-Vergleich (dafür Lauf 5 mit Opus 4.8 allein).

| Lauf | Modell | Runden | Größe | Dauer | Tokens |
|---|---|---|---|---|---|
| T1 bin 1 | Opus 4.8 (klebend) | 2 | 167 B | 54 s | 3937 |
| T1 bin 2 | Opus 5.5 | 1 | 164 B | 14 s | 1694 |
| T1 c 1, 2 | Opus 5.5 | 1 | 15968 B | 3 s | 123–130 |
| T4 bin 1, 2 | Opus 4.8 (Wechsel cyber) | 1 | 215–220 B | 120–123 s | 10251–10440 |
| T4 c 1, 2 | Opus 4.8 (1x Wechsel cyber, 1x klebend) | 1 | 16192 B | 4–5 s | 336–355 |
| T7 bin 1, 2 | Opus 4.8 (Wechsel cyber) | 1 | 468 / 613 B | 291 / 355 s | 26920 / 32569 |
| T7 c 1, 2 | Opus 5.5 | 1 | 16248–16272 B | 10 s | 1075–1155 |

Ergebnis 12/12 korrekt (Binär 6/6, C 6/6). Opus 5.5 selbst beantwortete 5 Anfragen (T1 C, T7 C, einmal T1 binär),
7 gingen an Opus 4.8: alle T4 (auch C) und alle T7 binär per Wechsel mit Grund cyber, T1 bin 1 und T4 c 2 landeten
"klebend" direkt beim Ersatz (Anthropic leitet nach einem Wechsel gleiche Anfragen etwa eine Stunde lang weiter).

Befunde:
- Opus 4.8 löst T7 (Ausdrucksrechner mit Klammern und Vorrang, 10 Tests) direkt als Maschinencode in einem Versuch,
  468 bzw. 613 Byte. Die Schätzung im README (1 bis 2 KB) war zu hoch. Aufwand aber 5 bis 6 Minuten und 27000 bis 33000
  Tokens je Lauf, gegenüber 10 s und rund 1100 Tokens in C. Faktor ~25 bei Tokens, ~30 bei Zeit.
- Rundenmodus erstmals belegt: T1 bin 1 von Opus 4.8 startete nicht (ELF-Kopf ab e_flags um 2 Byte verschoben,
  e_phnum=0). Mit der Rückmeldung (readelf-Ausgabe) kam in Runde 2 eine korrekte Datei; das Modell benannte den Fehler
  selbst richtig. Alle anderen 11 Läufe gelangen in Runde 1.
- Ablehnungsmuster von Opus 5.5 wie in Lauf 3: T4 (auch als C) und alle Binär-Anfragen außer T1 bin 2. Wieder nicht
  deterministisch (T1 bin 2 durch, T1 bin 1 nicht; T1 C und T7 C nie abgelehnt).
- Die Größen der Opus-4.8-Binaries entsprechen denen von Opus 5.5 in Lauf 1 (T4: 215–220 B gegen 213–233 B; T1: 167 B
  gegen 162–164 B). Zur Denkzeit gibt es keinen sauberen Vergleich: Lauf 1 lief über Claude Code ohne Zeitmessung je Aufgabe.
- Gesamtaufwand: Binär 958 s / 85811 Tokens, C 35 s / 3174 Tokens (Faktor ~27 bei Tokens).

# Lauf 5: Claude Opus 4.8 allein, Rundenmodus (12.10.2026, 21:10 Uhr)

Gleicher Aufbau wie Lauf 3, aber `--modell claude-opus-4-8`, kein Ersatz. Einheitliches Modell, damit Binär und C
sauber vergleichbar sind. Keine einzige Ablehnung durch den Sicherheitsfilter.

| Aufgabe | Binär | Binär Größe | Binär Runden | Binär Dauer / Tokens je Lauf | C | C Runden | C Dauer / Tokens je Lauf |
|---|---|---|---|---|---|---|---|
| T1 Hallo Welt | 2/2 | 162 B | 1, 1 | 30–34 s / 2881–3064 | 2/2 | 1, 1 | 2 s / 53–54 |
| T4 Zeile umkehren | 2/2 | 219–226 B | 1, 1 | 115–128 s / 10317–12047 | 2/2 | 2, 1 | 5–9 s / 352–721 |
| T7 Ausdrucksrechner | 2/2 | 736 / 445 B | 2, 2 | 372 / 621 s / 33189 / 51230 | 2/2 | 1, 1 | 7–9 s / 592–897 |
| Summe | 6/6 | | | 1300 s / 112728 | 6/6 | | 34 s / 2669 |

Befunde:
- Opus 4.8 löst alle drei Aufgaben als Maschinencode, T1 und T4 in Runde 1, T7 beide Male erst in Runde 2.
  Aufwand Binär gegen C: Faktor ~42 bei Tokens, ~38 bei Zeit. Je Aufgabe steigt der Faktor mit der Größe
  (T1 ~55x, T4 ~21x, T7 ~57x bei Tokens).
- T7 ist die erste Aufgabe, bei der Binär in Runde 1 scheitert, und zwar an Logik, nicht am ELF-Kopf:
  - Lauf 1 rechnete 2*(3+4)-5 = 77: ein überflüssiger skipspaces-Aufruf nach der Klammer überschrieb al mit ')' (0x29=41),
    also 2*41-5. Korrektur in Runde 2: 5 Bytes call durch NOPs ersetzt (76 s, 6384 Tokens).
  - Lauf 2 stürzte bei 1+2 ab (SIGSEGV): in der Dezimalausgabe stand mov rax,rcx statt mov rcx,rax (ModRM C8 statt C1),
    der Quotient wurde nie zurückgeschrieben, Endlosschleife lief aus dem Speicher. Korrektur: 1 Byte (330 s, 25205 Tokens).
  Beide Fehler fand das Modell anhand der objdump-Disassemblierung seiner eigenen Bytes aus der Rückmeldung und
  benannte Ursache und Offset korrekt. Der Rundenmodus mit Lesewerkzeugen ist damit das, was Binär bei T7 trägt.
- Einziger C-Fehlschlag: T4 c 1 setzte Markdown-Backticks (```c) in den C-Block, Compilerfehler, in Runde 2 behoben.
  Kein Logikfehler in C in diesem Lauf.
- Opus 4.8 lehnt nichts ab, Opus 5.5 (Lauf 3) fast alles Binäre. Für Binär-Messungen über die API ist Opus 4.8 das
  nutzbare Modell; mit `--ersatz` landet man ohnehin dort.

# Gesamtvergleich Claude (Aufgaben T1, T4, T7; Erfolg in max. 4 Runden)

| Lauf | Modell | Weg | Binär | C | Binär Tokens je Lauf (T1 / T4 / T7) |
|---|---|---|---|---|---|
| 1 | Opus 5.5 | Claude Code, 1 Runde | T1 3/3, T4 3/3 (T7 nicht gestellt) | 6/6 | – |
| 3 | Opus 5.5 | API, Runden | 0/6 (alle Ablehnung) | 4/6 (T4 Ablehnung) | – |
| 4 | Opus 5.5 + Ersatz 4.8 | API, Runden | 6/6 (5 davon 4.8) | 6/6 (2 davon 4.8) | 1694–3937 / ~10300 / 26920–32569 |
| 5 | Opus 4.8 | API, Runden | 6/6 | 6/6 | 2881–3064 / 10317–12047 / 33189–51230 |

Stand der Kernfrage nach Lauf 5: Bis T7 (445 bis 736 Byte Maschinencode) hält Binär mit Nachbesserung noch, braucht aber
ab T7 eine zweite Runde und 40- bis 60-mal so viele Tokens wie C. Fortsetzung mit T8 in Lauf 6.

# Lauf 6: T8 Variablenrechner mit Claude Opus 4.8 (12.10.2026, 21:40 Uhr)

Neue Aufgabe T8 (aufgaben.py): T7 plus Variablen, Zuweisungen, print-Zeilen, Rest-Operator %, Leerzeilen, Lesen bis
Dateiende; 10 Tests bis 26 Variablen und 700 Byte Programmtext. `--modell claude-opus-4-8`, je 2 Läufe, bis zu 4 Runden.

| Modus | Ergebnis | Größe | Runden | Dauer je Lauf | Tokens je Lauf |
|---|---|---|---|---|---|
| Binär | 2/2 | 727 / 860 B | 2 / 1 | 701 / 619 s | 63678 / 57499 |
| C | 2/2 | 16544–16552 B | 1 / 1 | 15 s | 1404–1419 |

Befunde:
- Opus 4.8 schreibt auch den Variablenrechner direkt als Maschinencode: Lauf 2 fehlerfrei in Runde 1 (860 B, 10 min,
  57000 Tokens), Lauf 1 nach einer Korrektur in Runde 2. Binär gegen C: Faktor ~43 bei Tokens, ~45 bei Zeit.
- Die Größenschätzung (1 bis 1,5 KB) war zu hoch: 727 bis 860 B, nur rund 20 % mehr als T7 (445 bis 736 B). Symboltabelle
  und Zeilenschleife kosten im Maschinencode wenig; die Tokenzahl je Lauf stieg trotzdem von 26000–33000 auf 57000–64000.
- Derselbe Fehler wie bei T7 Lauf 1 in Lauf 5: Nach der Klammerauswertung ruft das Modell nochmals skipspaces auf, das
  movzbl (%r15),%eax überschreibt das Ergebnis in rax mit dem Zeichen ')' (0x29=41); (0-7)/2 wurde so zu 41/2=20. Erst
  Test 5 deckt das auf, Tests 1 bis 4 waren bestanden. Korrektur wieder 5 NOPs in Runde 2 (104 s, 8844 Tokens), Analyse
  anhand der objdump-Rückmeldung mit korrektem Offset. Ein wiederkehrendes Muster: Rückgabewert in rax wird durch
  einen Hilfsaufruf zerstört, der rax als Scratch-Register nutzt.
- Einfache Fehler (ELF-Kopf) sind bei Opus 4.8 ab T4 nicht mehr aufgetreten; die Fehler sitzen jetzt in der
  Registerdisziplin zwischen handgeschriebenen Unterprogrammen.

Stand der Kernfrage nach Lauf 6: Auch T8 (727 bis 860 Byte) hält Binär bei Opus 4.8 in höchstens 2 Runden. Der
Einbruch ist noch nicht erreicht. Der Aufwand je Lauf verdoppelt sich aber von T7 zu T8 (Tokens) bei nur 20 % mehr Code,
und je Binär-Lauf fallen 10 bis 12 Minuten an. Nächste Stufe T9 sollte deutlich größer sein (z. B. Schleifen oder
Zeichenkettenverarbeitung mit Datenstruktur, Ziel 2 bis 3 KB), sonst bleibt die Grenze außer Reichweite.

# Lauf 7: Versuch Modus bin_offsets mit Claude Opus 4.8 (12.10.2026, 21:28 bis 21:59 Uhr)

Frage: Hilft es dem Modell, wenn es die Bytes zeilenweise mit Dateioffset und Kommentar ausgibt (`OFFSET: BYTES ; asm`)
statt als reinen Hexblock? pruefen.py prüft dabei jeden Offset. Gleiche Aufgaben T7 und T8, gleiches Modell, gleiche
Einstellungen wie Lauf 5 und 6, Modus bin_offsets_runden, je 2 Läufe. Hinweis: Der Lauf wurde versehentlich doppelt
gestartet (zwei Prozesse, 10 s Abstand); der zweite wurde nach 6,5 min beendet, lieferte aber vorher zwei zusätzliche
Runde-1-Antworten, die hier als Zusatzstichprobe gezählt sind. Seitdem verhindert eine Sperrdatei (lauf.pid) Doppelstarts.

| Lauf | Ergebnis | Runden | Größe | Tokens gesamt | Runde 1 ohne Offsets (Lauf 5/6) |
|---|---|---|---|---|---|
| T7 Lauf 1 | OK | 3 | 477 B | 123109 (R1 29709 Fehler 77, R2 64000 abgeschnitten ohne Abgabe, R3 29400) | 2 Runden, 33189 |
| T7 Lauf 1, Zweitprobe | R1 Fehler 77 | – | – | 31281 (Prozess danach beendet) | – |
| T7 Lauf 2 | OK | 1 | 497 B | 25291 | 2 Runden, 51230 |
| T7 Lauf 2, Zweitprobe | OK | 1 | 497 B | 32968 | – |
| T8 Lauf 1 | OK | 1 | 838 B | 61092 | 2 Runden, 63678 |
| T8 Lauf 2 | OK | 2 | 906 B | 66527 (R1 Fehler doppelte Ausgabe, R2 10287) | 1 Runde, 57499 |

Befunde:
- Kein einziger Offset-Fehler in 8 Abgaben. Das Modell hält das Format sauber ein, eine Anweisung je Zeile mit
  Assembler-Kommentar (T8 Lauf 1: 236 Zeilen). Die Adressbuchhaltung war also auch vorher nicht die Fehlerquelle.
- Die Fehler sind dieselben wie ohne Offsets: zweimal der 77er-Fehler bei T7 (Klammerergebnis durch Hilfsaufruf
  zerstört), bei T8 einmal doppelte Ausgabe des Puffers. Das Format ändert nichts an der Registerdisziplin.
- Tokenaufwand: T8 gleich (61000 bis 67000 gegen 57000 bis 64000). T7 in Runde 1 etwas niedriger (25000 bis 33000 gegen
  33000 bis 51000), dafür ein Ausreißer: In Runde 2 von T7 Lauf 1 dachte das Modell 64000 Tokens lang (Umbau auf einen
  rbp-basierten Operandenstapel, Durchspielen aller Aufrufe) und gab nichts ab; erst Runde 3 brachte einen kompletten
  Neuentwurf mit 477 B. Teuerster Einzellauf des Experiments.
- Runde-1-Erfolge: mit Offsets 4 von 6 Abgaben (T7 2/3, T8 1/2), ohne Offsets 1 von 4 (T7 0/2, T8 1/2). Kleine Stichprobe,
  Unterschied bei T7 möglicherweise real, bei T8 keiner.
- Fazit: kein messbarer Vorteil bei Tokens oder Fehlerart, ein möglicher kleiner Vorteil bei der Runde-1-Quote von T7,
  dazu ein Totalausfall einer Runde. Als Stütze für die Adressbuchhaltung ist der Modus überflüssig, weil Adressen nie
  das Problem waren. Der Modus bleibt als Zelle dokumentiert; ob er in frage_modell.py bleibt, ist Geschmackssache.

# Lauf 8: T9 Funktionsrechner mit Claude Opus 4.8 (12.10.2026, 22:06 bis 23:07 Uhr)

Neue Aufgabe T9 (aufgaben.py): T8 plus Funktionsdefinitionen mit 1 bis 4 Parametern, Vergleiche, Bedingungsausdruck ? :
mit Auswertung nur des gewählten Zweigs, Rekursion bis Tiefe 200; 10 Tests (Fakultät, ggT, Fibonacci rekursiv mit 21891
Aufrufen, Collatz, Rangfolge). `--modell claude-opus-4-8`, je 2 Läufe, `--max_tokens 128000` (Maximum des Modells),
bis zu 4 Runden. Der Lauf wurde nach Runde 2 abgebrochen, weil alle vier Binär-Runden identisch endeten.

| Modus | Ergebnis | Runden | Größe | Dauer je Runde | Tokens je Runde |
|---|---|---|---|---|---|
| Binär | 0/2, abgebrochen nach Runde 2 | 2 + 2 ohne Abgabe | – | 22 bis 24 min | 128000 (Grenze) |
| C | 2/2 | 1 / 1 | 20,8 KB gebaut (Quelltext 224 Zeilen) | 104 / 116 s | 9288 / 10553 |

Befunde:
- Hier bricht Binär ein. In vier Runden (zwei Läufe mal zwei Runden) kam keine einzige Datei. Jede Runde verbrauchte die
  vollen 128000 Tokens, der sichtbare Antworttext blieb jedes Mal leer: Das Modell hat alles im Denken verbraucht.
- Die Denkzusammenfassungen (50 bis 63 KB je Runde) zeigen das Muster: Das Modell entwirft den Parser samt Aufrufrahmen,
  schreibt den Code, prüft ihn dann Routine für Routine von Hand nach ("Still tracing disassembly...", mehrfach
  hintereinander) und kommt nie zum Aufschreiben. In Lauf 1 Runde 2 war es kurz davor: "120 Byte Header plus 1464 Byte
  Code gibt 1584, passt zu filesz 0x630", dann endete die Runde. Der fertige Code hätte also rund 1,5 KB gehabt,
  etwa das Doppelte von T8.
- Die Rückmeldung "Antwort wurde abgeschnitten" ändert nichts, weil es keinen Fehler zum Korrigieren gibt; Runde 2
  begann jeweils von vorn und endete gleich. Runden 3 und 4 (je ~3 Dollar und 24 min) wurden deshalb gestrichen.
- C bleibt stabil, wird aber ebenfalls teurer: rund 10000 Tokens und zwei Minuten je Lauf, siebenmal T8. Beide Lösungen
  rekursiver Abstieg mit Funktionstabelle, fehlerfrei in Runde 1.
- Kosten der vier Binär-Runden: 512000 Ausgabe-Tokens, rund 13 Dollar, Ergebnis null.

# Stand der Kernfrage nach Lauf 8

Mit Claude Opus 4.8 über die API, Rundenmodus und Lesewerkzeugen:

| Aufgabe | Maschinencode | Binär | C |
|---|---|---|---|
| T1 Hallo Welt | 162 B | 2/2, Runde 1 | 2/2 |
| T4 Zeile umkehren | 219–226 B | 2/2, Runde 1 | 2/2 |
| T7 Ausdrucksrechner | 445–736 B | 2/2, Runde 2 | 2/2 |
| T8 Variablenrechner | 727–860 B | 2/2, Runde 1–2 | 2/2 |
| T9 Funktionsrechner | ~1,5 KB (geplant, nie abgegeben) | 0/2, Grenze 128000 Tokens | 2/2, Runde 1 |

Die Grenze liegt zwischen rund 900 Byte und 1,5 KB Maschinencode. Sie zeigt sich nicht als falsches Programm, sondern
als Verstummen: Das Modell schafft den Entwurf, aber die Verifikation im Kopf wächst schneller als das Antwortbudget.
C hält bei allen Größen mit 40- bis 60-mal weniger Tokens.
