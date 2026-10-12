#!/usr/bin/env bash
# Kompletter Lauf in EINEM RunPod-Pod:
#   PrismML-llama.cpp bauen -> Bonsai-GGUF laden -> llama-server starten
#   -> alle Anfragen stellen -> Programme bauen und testen -> Ergebnis packen.
# Alles liegt unter /workspace und überlebt damit einen Pod-Neustart; erneuter Aufruf
# überspringt Build, Download und schon vorhandene Antworten.
#
# Aufruf (im Experiment-Ordner):   bash runpod/start.sh
# Einstellungen per Umgebungsvariable, z. B.:
#   AUFGABEN=T1 LAEUFE=1 NAME=rauchtest bash runpod/start.sh
set -euo pipefail

EXP="$(cd "$(dirname "$0")/.." && pwd)"
WS="${WS:-/workspace}"
HF_REPO="${HF_REPO:-prism-ml/Ternary-Bonsai-2-27B-gguf}"
MODELL_DATEI="${MODELL_DATEI:-Ternary-Bonsai-2-27B-PTQ1_0.gguf}"   # oder ...-PQ2_0.gguf / ...-F16.gguf (54 GB, 80-GB-GPU)
REASONING="${REASONING:-medium}"      # Denkstufe: medium oder xhigh (Modell-Standard, denkt sehr lange)
DENK_BUDGET="${DENK_BUDGET:-24000}"   # max. Denk-Tokens, danach muss das Modell antworten
AUFGABEN="${AUFGABEN:-T1,T2,T3,T4,T5,T6}"   # T7 (Ausdrucksrechner) gibt es seit v2, Standard bleibt T1-T6
LAEUFE="${LAEUFE:-3}"
MODI="${MODI:-bin,c}"                # bin, c, bin_runden, c_runden (Rundenmodus mit Rückmeldung)
RUNDEN="${RUNDEN:-5}"                # max. Abgaben je Lauf in den _runden-Modi
NAME="${NAME:-bonsai27b_$(echo "$MODELL_DATEI" | sed -E 's/.*-([A-Za-z0-9_]+)\.gguf/\1/')_$REASONING$(case "$MODI" in *runden*) echo _runden;; esac)}"
PARALLEL="${PARALLEL:-2}"            # gleichzeitige Anfragen = Server-Slots
CTX_PRO_SLOT="${CTX_PRO_SLOT:-49152}"
MAX_TOKENS="${MAX_TOKENS:-$((DENK_BUDGET + 6000))}"  # Denkbudget plus Platz für die Antwort (300 Byte Hex ~ 1000 Tokens)
PORT="${PORT:-8080}"
CUDA="${CUDA:-ON}"                    # nur zum Testen ohne GPU auf OFF setzen

LLAMA="$WS/prism-llama.cpp"
MODELLE="$WS/modelle"
LOG="$WS/llama-server.log"
schritt() { echo; echo "=== $(date +%H:%M:%S) $* ==="; }

schritt "1/6 Werkzeuge prüfen"
if [ "$CUDA" = "ON" ]; then
  command -v nvidia-smi >/dev/null || { echo "Keine NVIDIA-GPU sichtbar. GPU-Pod gewählt?"; exit 1; }
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi
if ! command -v git >/dev/null || ! command -v gcc >/dev/null || ! command -v cmake >/dev/null \
   || ! command -v curl >/dev/null; then
  apt-get update -qq && apt-get install -y -qq git build-essential cmake curl >/dev/null
fi
pipi() { python3 -m pip install -q "$@" 2>/dev/null || python3 -m pip install -q --break-system-packages "$@"; }
if [ "$CUDA" = "ON" ]; then
  command -v nvcc >/dev/null || export PATH="/usr/local/cuda/bin:$PATH"
  command -v nvcc >/dev/null || { echo "nvcc fehlt: Pod-Image mit CUDA-'devel' wählen (z. B. RunPod PyTorch)."; exit 1; }
fi
# CMAKE_CUDA_ARCHITECTURES=native braucht cmake >= 3.24; ältere Images haben weniger
if ! cmake --version | awk 'NR==1{split($3,v,"."); exit !(v[1]>3 || (v[1]==3 && v[2]>=24))}'; then
  pipi --upgrade cmake && hash -r
  export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
  cmake --version | head -1
fi
command -v hf >/dev/null || { pipi -U "huggingface_hub[cli]"; hash -r; export PATH="$HOME/.local/bin:$PATH"; }
command -v hf >/dev/null || { echo "hf-Befehl nicht gefunden"; exit 1; }

schritt "2/6 PrismML-llama.cpp bauen (einmalig, ca. 5-15 min)"
if [ ! -x "$LLAMA/build/bin/llama-server" ]; then
  [ -d "$LLAMA" ] || git clone -q -b prism https://github.com/PrismML-Eng/llama.cpp "$LLAMA"
  CUDA_OPT=(-DGGML_CUDA=OFF)
  [ "$CUDA" = "ON" ] && CUDA_OPT=(-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=native)
  cmake -S "$LLAMA" -B "$LLAMA/build" -DCMAKE_BUILD_TYPE=Release "${CUDA_OPT[@]}" >/dev/null
  JOBS=$(nproc); [ "$JOBS" -gt 16 ] && JOBS=16   # CUDA-Build braucht viel RAM je Job
  echo "Baue mit $JOBS Jobs, Fortschritt: tail -f $WS/build.log"
  cmake --build "$LLAMA/build" --target llama-server -j "$JOBS" > "$WS/build.log" 2>&1 \
    || { echo "Build fehlgeschlagen, letzte Zeilen:"; tail -30 "$WS/build.log"; exit 1; }
  [ -x "$LLAMA/build/bin/llama-server" ] || { echo "Build lieferte kein llama-server"; exit 1; }
  echo "Build fertig"
else
  echo "schon gebaut"
fi
LLAMA_STAND="$(git -C "$LLAMA" rev-parse --short HEAD 2>/dev/null || echo unbekannt)"
echo "llama.cpp-Stand: $LLAMA_STAND"

schritt "3/6 Modell laden: $MODELL_DATEI"
mkdir -p "$MODELLE"
if [ ! -f "$MODELLE/$MODELL_DATEI" ]; then
  # Platz vorab prüfen: F16 braucht rund 54 GB, ein volles Volume bricht sonst erst nach langem Download ab
  BRAUCHT_GB=8; case "$MODELL_DATEI" in *F16*|*BF16*) BRAUCHT_GB=56;; esac
  FREI_GB=$(df -P -BG "$MODELLE" | awk 'NR==2{gsub("G","",$4); print $4}')
  echo "Frei auf $MODELLE: ${FREI_GB} GB, benötigt: ca. ${BRAUCHT_GB} GB"
  [ "$FREI_GB" -ge "$BRAUCHT_GB" ] || { echo "Zu wenig Platz: Volume vergrößern (für F16 mind. 80 GB)."; exit 1; }
fi
[ -f "$MODELLE/$MODELL_DATEI" ] || hf download "$HF_REPO" "$MODELL_DATEI" --local-dir "$MODELLE"
ls -lh "$MODELLE/$MODELL_DATEI"

SERVER_PID=""
trap '[ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null || true' EXIT

# Startet den Server mit $1 Slots; gibt 0 zurück, sobald /health antwortet.
starte_server() {
  local slots=$1
  pkill -f "llama-server.*--port $PORT" 2>/dev/null || true; sleep 2
  nohup "$LLAMA/build/bin/llama-server" -m "$MODELLE/$MODELL_DATEI" \
    --host 127.0.0.1 --port "$PORT" -ngl 99 -fa on --jinja \
    -np "$slots" -c $((slots * CTX_PRO_SLOT)) -ctk q8_0 -ctv q8_0 \
    > "$LOG" 2>&1 &
  SERVER_PID=$!
  for i in $(seq 1 360); do   # bis 30 min: F16 (54 GB) vom Netzwerk-Volume zu laden dauert
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && return 0
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "Server mit $slots Slots beendet. Letzte Zeilen aus $LOG:"; tail -8 "$LOG"; return 1
    fi
    sleep 5
  done
  echo "Server nach 30 min nicht bereit"; tail -8 "$LOG"; return 1
}

schritt "4/6 llama-server starten (bis $PARALLEL Slots x $CTX_PRO_SLOT Kontext)"
SLOTS=$PARALLEL
until starte_server "$SLOTS"; do
  [ "$SLOTS" -le 1 ] && { echo "Server startet auch mit 1 Slot nicht. Ursache steht oben bzw. in $LOG (bei Speichermangel CTX_PRO_SLOT verkleinern)."; exit 1; }
  SLOTS=$((SLOTS / 2)); echo "Neuer Versuch mit $SLOTS Slot(s) ..."
done
PARALLEL=$SLOTS
echo "Server bereit mit $PARALLEL Slot(s)"
if [ "$CUDA" = "ON" ]; then nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader; fi
# Laufbedingungen festhalten, damit Läufe verschiedener Modelle vergleichbar bleiben
mkdir -p "$EXP/laeufe/$NAME"
{ echo "datum: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "modell: $MODELL_DATEI"
  echo "llama_cpp: $LLAMA_STAND"
  [ "$CUDA" = "ON" ] && echo "gpu: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"
  echo "slots: $PARALLEL  ctx_pro_slot: $CTX_PRO_SLOT  kv_cache: q8_0"
  echo "reasoning: $REASONING  denk_budget: $DENK_BUDGET  max_tokens: $MAX_TOKENS"
  echo "aufgaben: $AUFGABEN  laeufe: $LAEUFE  modi: $MODI  runden: $RUNDEN"
} > "$EXP/laeufe/$NAME/lauf_info.txt"
cat "$EXP/laeufe/$NAME/lauf_info.txt"

schritt "5/6 Anfragen stellen: $AUFGABEN, Modi $MODI, $LAEUFE Läufe je Modus, Denkstufe $REASONING -> laeufe/$NAME"
# Empfohlene Sampling-Werte für den Denkmodus laut Modellkarte
python3 "$EXP/frage_modell.py" --url "http://127.0.0.1:$PORT/v1" --name "$NAME" \
  --aufgaben "$AUFGABEN" --modi "$MODI" --runden "$RUNDEN" --laeufe "$LAEUFE" --parallel "$PARALLEL" --max_tokens "$MAX_TOKENS" \
  --temperatur 1.0 --top_p 0.95 --top_k 20 --min_p 0.05 \
  --reasoning_effort "$REASONING" --denk_budget "$DENK_BUDGET"

schritt "6/6 Programme bauen und testen"
python3 "$EXP/pruefen.py" "$EXP/laeufe/$NAME" | tee "$EXP/laeufe/$NAME/zusammenfassung.txt"
cp "$LOG" "$EXP/laeufe/$NAME/llama-server.log"
tar czf "$WS/ergebnis_$NAME.tar.gz" -C "$EXP/laeufe" --exclude=bau "$NAME"
echo
echo "Fertig. Ergebnis zum Herunterladen: $WS/ergebnis_$NAME.tar.gz"
echo "Pod danach stoppen, sonst läuft die Abrechnung weiter."
