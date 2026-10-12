# Binär-Experiment auf RunPod (alles in einem Pod)

Das Skript `runpod/start.sh` macht im Pod alles selbst: PrismML-Fork von llama.cpp mit CUDA bauen,
Ternary-Bonsai-2-27B von Hugging Face laden, llama-server starten, alle Aufgaben stellen,
die erzeugten Programme bauen und testen, Ergebnis als .tar.gz ablegen.
Die vom Modell erzeugten Programme laufen dabei nur im Wegwerf-Pod, nicht auf deinem PC.

## 1. Pod anlegen
- Vorlage: **RunPod PyTorch** (CUDA-"devel"-Image, enthält nvcc, gcc, Python, JupyterLab)
- GPU: ab 16 GB (z. B. RTX A4000, RTX 4000 Ada); das Modell selbst belegt rund 6 GB.
  Das Skript startet mit 2 gleichzeitigen Anfragen; passt das nicht in den Speicher,
  schaltet es selbst auf 1 zurück. Mit 24 GB oder mehr kannst du `PARALLEL=4` probieren,
  das Skript halbiert bei Bedarf ebenfalls von selbst.
- Volume (/workspace): mindestens 30 GB. Container-Disk: Standard.
- Preise vorher im Dashboard prüfen.

## 2. Paket hochladen und entpacken
JupyterLab des Pods öffnen (Connect → Jupyter), `binaer_experiment.tar.gz` per Drag & Drop
nach /workspace ziehen, dann im Jupyter-Terminal:

    cd /workspace && tar xzf binaer_experiment.tar.gz && cd binaer_experiment

## 3. Rauchtest (eine Aufgabe, ein Lauf)
Baut beim ersten Mal llama.cpp (5 bis 15 Minuten) und lädt das Modell (~6 GB):

    AUFGABEN=T1 LAEUFE=1 NAME=rauchtest bash runpod/start.sh

Läuft er durch und zeigt am Ende eine kleine Tabelle, ist alles bereit.

## 4. Voller Lauf (36 Anfragen)
Im Hintergrund starten, damit ein geschlossener Browser den Lauf nicht abbricht:

    nohup bash runpod/start.sh > /workspace/lauf.log 2>&1 &
    tail -f /workspace/lauf.log        # mitlesen, Strg+C beendet nur das Mitlesen

Build und Download werden beim zweiten Mal übersprungen, schon fertige Antworten auch.
Bricht etwas ab: einfach denselben Befehl noch einmal starten.

## 5. Ergebnis holen und Pod stoppen
`/workspace/ergebnis_<name>.tar.gz` im Jupyter-Dateibaum rechts anklicken → Download.
Darin: alle Antworten, ergebnisse.json, zusammenfassung.txt, protokoll.jsonl (Dauer, Tokens,
abgeschnittene Antworten) und das Server-Log. Danach den Pod **stoppen oder löschen**.

## Einstellungen (Umgebungsvariablen vor dem Befehl)
| Variable | Standard | Bedeutung |
|---|---|---|
| MODELL_DATEI | Ternary-Bonsai-2-27B-PTQ1_0.gguf | oder Ternary-Bonsai-2-27B-PQ2_0.gguf / -F16.gguf |
| AUFGABEN | T1,...,T6 | Auswahl |
| LAEUFE | 3 | Läufe je Aufgabe und Modus |
| PARALLEL | 2 | gleichzeitige Anfragen |
| REASONING | medium | Denkstufe; xhigh ist der Modell-Standard und denkt sehr lange |
| DENK_BUDGET | 24000 | max. Denk-Tokens, danach muss das Modell antworten |
| CTX_PRO_SLOT | 49152 | Kontext je Anfrage |
| MAX_TOKENS | DENK_BUDGET + 6000 | Antwortlänge inkl. Denkteil; mehr bringt nur längere Schleifen |
| NAME | bonsai27b_PTQ1_0_medium | Laufordner |

## F16-Lauf (unquantisiertes Modell, Vergleich mit PTQ1_0)
- Pod: GPU mit 80 GB (A100 80 GB oder H100 80 GB), Volume **mindestens 80 GB** (Modell 54 GB,
  dazu llama.cpp-Build). Das Skript prüft den Platz vor dem Download und bricht sonst gleich ab.
- Speicher auf der GPU: rund 54 GB Gewichte plus rund 3,5 GB für 2 Slots x 49152 Kontext und
  Rechenpuffer, also etwa 58 von 80 GB. Alle anderen Einstellungen bleiben wie beim PTQ1_0-Lauf.
- Laden des Modells dauert einige Minuten; das Skript wartet bis zu 30 Minuten auf den Server.
- Rauchtest: `MODELL_DATEI=Ternary-Bonsai-2-27B-F16.gguf AUFGABEN=T1 LAEUFE=1 NAME=rauchtest_f16 bash runpod/start.sh`
- Voller Lauf: `MODELL_DATEI=Ternary-Bonsai-2-27B-F16.gguf nohup bash runpod/start.sh > /workspace/lauf_f16.log 2>&1 &`
- Ergebnis: /workspace/ergebnis_bonsai27b_F16_medium.tar.gz. Die Laufbedingungen (GPU, llama.cpp-Stand,
  Einstellungen) stehen in lauf_info.txt im Laufordner.

Beispiel PQ2_0-Variante zum Vergleich:
`MODELL_DATEI=Ternary-Bonsai-2-27B-PQ2_0.gguf nohup bash runpod/start.sh > /workspace/lauf2.log 2>&1 &`

## Rundenmodus und T7 (Archiv binaer_experiment_v2.tar.gz)
Das v2-Archiv entpackt nach `binaer_experiment_v2/` und lässt einen vorhandenen `binaer_experiment/`-Ordner
samt Läufen unberührt. llama.cpp-Build und Modell unter /workspace werden weiterverwendet.
**Erst starten, wenn ein laufender Lauf fertig ist:** start.sh beendet einen llama-server auf demselben Port.

    cd /workspace && tar xzf binaer_experiment_v2.tar.gz && cd binaer_experiment_v2

Rauchtest (T1 binär, höchstens 2 Runden):

    MODELL_DATEI=Ternary-Bonsai-2-27B-F16.gguf AUFGABEN=T1 MODI=bin_runden LAEUFE=1 RUNDEN=2 NAME=rauchtest_runden bash runpod/start.sh

Empfohlener Lauf für heute (T1, T4, T7, je 2 Läufe, bis zu 4 Runden, binär und C):

    MODELL_DATEI=Ternary-Bonsai-2-27B-F16.gguf AUFGABEN=T1,T4,T7 MODI=bin_runden,c_runden LAEUFE=2 RUNDEN=4 \
      nohup bash runpod/start.sh > /workspace/lauf_runden.log 2>&1 &

Laufname wird automatisch bonsai27b_F16_medium_runden, Ergebnis: /workspace/ergebnis_bonsai27b_F16_medium_runden.tar.gz.
Dauer im schlechtesten Fall (alle Binär-Runden scheitern, 5 bis 11 min je Antwort wie beim PTQ1_0-Lauf,
2 Slots): 3 Aufgaben x 2 Läufe x 4 Runden / 2 = 12 Antworten nacheinander, also etwa 1 bis 2 Stunden; C ist in Minuten fertig.
Mit dem kleineren Modell geht derselbe Lauf ohne MODELL_DATEI (dann PTQ1_0, Name bonsai27b_PTQ1_0_medium_runden).

| Variable | Standard | Bedeutung |
|---|---|---|
| MODI | bin,c | zusätzlich bin_runden, c_runden (Nachbessern mit Rückmeldung) |
| RUNDEN | 5 | max. Abgaben je Lauf im Rundenmodus |

## Wenn es hakt
- **Server startet auch mit 1 Slot nicht:** `CTX_PRO_SLOT=24576` setzen; die genaue Meldung steht in
  /workspace/llama-server.log.
- **Build schlägt fehl:** letzte Zeilen werden angezeigt, das ganze Log steht in /workspace/build.log.
- **Viele "ABGESCHNITTEN" im Log:** `DENK_BUDGET` senken oder `MAX_TOKENS` und `CTX_PRO_SLOT`
  erhöhen. Der Denkteil jeder Antwort steht in laeufe/<name>/denken/.
- **Vergleich der Denkstufen:** `REASONING=xhigh DENK_BUDGET=60000 MAX_TOKENS=70000 CTX_PRO_SLOT=73728`
- **"nvcc fehlt":** Pod mit anderem Image (PyTorch-Vorlage) neu anlegen.

Hinweis: Laut Modellkarte brauchen PTQ1_0 und PQ2_0 den PrismML-Fork; normales llama.cpp
(und damit vermutlich auch Ollama) liefert mit diesen Dateien unbrauchbare Ausgaben.
