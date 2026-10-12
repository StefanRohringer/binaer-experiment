# Anleitung: Rundenlauf mit Claude über die API, vom eigenen PC

Kein RunPod nötig. Claude rechnet bei Anthropic, dein PC baut und testet nur die Programme.
Weil die Programme Linux-x86-64-Dateien sind, laufen sie unter Windows in **WSL** (Linux im Windows).
Die Programme kommen vom Modell und sind ungeprüft: WSL trennt sie zumindest vom normalen Windows.

## Schritt 1: API-Schlüssel holen
1. https://console.anthropic.com öffnen, anmelden, unter **Billing** etwas Guthaben aufladen.
2. **API Keys → Create Key**, Schlüssel kopieren (beginnt mit `sk-ant-`). Nirgends speichern, wo andere ihn sehen.

## Schritt 2: WSL einrichten (nur unter Windows, einmalig)
1. **PowerShell als Administrator** öffnen, eingeben: `wsl --install -d Ubuntu`
2. PC neu starten. Danach öffnet sich Ubuntu und fragt nach Benutzername und Passwort (frei wählbar).
3. Später startest du Ubuntu über das Startmenü („Ubuntu“).

Unter Linux entfällt dieser Schritt. Auf einem Mac geht es nicht direkt (andere Programmart), dort bitte melden.

## Schritt 3: Werkzeuge installieren (im Ubuntu-Fenster, einmalig)

    sudo apt update && sudo apt install -y gcc binutils python3-venv
    python3 -m venv ~/claude-env
    ~/claude-env/bin/pip install anthropic

## Schritt 4: Archiv auspacken
`binaer_experiment_v2.tar.gz` herunterladen. Im Windows-Explorer liegt der Downloads-Ordner in Ubuntu unter
`/mnt/c/Users/<DeinName>/Downloads`. Im Ubuntu-Fenster:

    cd ~ && tar xzf /mnt/c/Users/<DeinName>/Downloads/binaer_experiment_v2.tar.gz && cd binaer_experiment_v2

## Schritt 5: Schlüssel setzen und Rauchtest

    export ANTHROPIC_API_KEY=sk-ant-...dein-schlüssel...
    ~/claude-env/bin/python frage_modell.py --anbieter anthropic --name rauchtest --aufgaben T1 --modi bin_runden --laeufe 1 --runden 2
    ~/claude-env/bin/python pruefen.py laeufe/rauchtest

**In Ordnung, wenn** am Ende eine kleine Tabelle mit T1 erscheint. Steht dort „Ablehnung durch Sicherheitsfilter“,
hat Claude die Anfrage abgelehnt; das ist ein Messergebnis, kein Fehler im Skript.

## Schritt 6: Der eigentliche Lauf

    ~/claude-env/bin/python frage_modell.py --anbieter anthropic --name claude_runden --aufgaben T1,T4,T7 --modi bin_runden,c_runden --laeufe 2 --runden 4 --parallel 4
    ~/claude-env/bin/python pruefen.py laeufe/claude_runden

- Läuft 4 Anfragen gleichzeitig, im Fenster siehst du je Runde eine Zeile, z. B. `T7_bin_runden_1 Runde 2: Test 3: falsche Ausgabe ...`.
- Dauer grob 30 bis 60 Minuten. Fenster offen lassen. Bricht etwas ab, denselben Befehl erneut starten: fertige Läufe werden übersprungen.
- Kosten: Claude Opus 5.5 kostet 20 $ je Million Ausgabe-Tokens. Im schlechtesten Fall (alle Binär-Runden scheitern)
  rechne mit grob 10 bis 30 $. Die genaue Tokenzahl steht danach in `laeufe/claude_runden/protokoll.jsonl`.

## Schritt 7: Ergebnis schicken

    tar czf /mnt/c/Users/<DeinName>/Downloads/ergebnis_claude_runden.tar.gz -C laeufe --exclude=bau claude_runden

Die Datei `ergebnis_claude_runden.tar.gz` aus deinem Downloads-Ordner hier im Projekt hochladen, dann werte ich sie aus.

## Wenn es hakt
- **`AuthenticationError`:** Schlüssel falsch kopiert oder `export` im aktuellen Fenster vergessen (gilt nur bis zum Schließen).
- **`RateLimitError` oder viele Wartezeiten:** `--parallel 2` statt 4.
- **`No module named anthropic`:** mit `~/claude-env/bin/python` starten, nicht mit `python3`.
