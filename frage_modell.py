"""Befragt ein Modell über eine OpenAI-kompatible Schnittstelle (z. B. llama-server aus llama.cpp)
und legt die Antworten als Laufordner für pruefen.py ab.

Beispiel:
  python3 frage_modell.py --url http://localhost:8080/v1 --name bonsai27b --laeufe 3
  python3 pruefen.py laeufe/bonsai27b

Rundenmodus (--modi bin_runden,c_runden): Nach jeder Abgabe baut und testet das Skript das Programm
sofort und gibt dem Modell bei einem Fehlschlag das Testergebnis zurück (bei binär zusätzlich readelf
und eine objdump-Disassemblierung der eigenen Bytes). Das Modell darf bis zu --runden Mal abgeben.
Im Verlauf stehen jeweils nur die Aufgabe, die letzte Abgabe und deren Rückmeldung.
Die Werkzeuge lesen nur; Code erzeugt weiterhin allein das Modell.

Claude direkt über die API (z. B. vom eigenen PC):
  export ANTHROPIC_API_KEY=...   (und einmalig: pip install anthropic)
  python3 frage_modell.py --anbieter anthropic --name claude_runden --aufgaben T1,T4,T7 \
      --modi bin_runden,c_runden --laeufe 2 --runden 4 --parallel 4

Für llama.cpp reicht die Standardbibliothek; nur --anbieter anthropic braucht das Paket anthropic. Schon vorhandene Antworten werden übersprungen.
"""
import argparse, concurrent.futures, datetime, json, os, re, shutil, struct, subprocess, sys, threading, time
import urllib.request

BASIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASIS)
from aufgaben import AUFGABEN, tests_fuer
from pruefen import baue, letzter_block, teste

PROMPT_BIN = """Schreibe ein vollständiges, direkt ausführbares Programm für Linux x86-64 als rohe Bytes: eine komplette ELF64-Datei, statisch, ohne libc, nur Linux-Systemaufrufe. Kein Quelltext, kein Assembler, kein Compiler: du gibst die fertigen Bytes aus.

Programmaufgabe: {aufgabe}

Gib am Ende deiner Antwort eine Zeile BEGIN_HEX aus, dann alle Bytes der ELF-Datei als Hexadezimal (Leerzeichen und Zeilenumbrüche erlaubt), dann eine Zeile END_HEX."""

PROMPT_C = """Schreibe ein vollständiges C-Programm für Linux. Es wird mit "gcc -O2" kompiliert; die normale C-Standardbibliothek darf benutzt werden.

Programmaufgabe: {aufgabe}

Gib am Ende deiner Antwort eine Zeile BEGIN_C aus, dann den C-Quelltext, dann eine Zeile END_C."""

ZUSATZ_RUNDEN = """

Nach jeder Abgabe wird dein Programm gebaut und getestet. Schlägt etwas fehl, bekommst du das Ergebnis zurück und darfst eine korrigierte Fassung abgeben, insgesamt höchstens {runden} Abgaben."""

sperre = threading.Lock()


def frage_claude(a, nachrichten):
    """Claude über die Anthropic-API (offizielles SDK: pip install anthropic, Schlüssel in ANTHROPIC_API_KEY).
    Ohne --ersatz keine Ausweichmodelle: lehnt der Sicherheitsfilter ab, wird das als Ablehnung protokolliert.
    Mit --ersatz übernimmt serverseitig das von Anthropic vorgesehene Ersatzmodell; das wird im Protokoll vermerkt."""
    import anthropic
    client = anthropic.Anthropic(timeout=a.timeout)
    modell = a.modell or "claude-opus-5-5"
    parameter = dict(model=modell, max_tokens=a.max_tokens,
                     thinking={"type": "adaptive", "display": "summarized"},
                     output_config={"effort": a.reasoning_effort or "high"},
                     messages=nachrichten)
    if a.ersatz:
        # Serverseitiger Ersatz (Beta): lehnt der Sicherheitsfilter ab, wiederholt Anthropic dieselbe Anfrage
        # auf dem für die Ablehnungskategorie vorgesehenen Ersatzmodell. Welches Modell geantwortet hat,
        # steht danach in usage["modell"] bzw. usage["ersatz"].
        schnittstelle = client.beta.messages
        parameter.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    else:
        schnittstelle = client.messages
    with schnittstelle.stream(**parameter) as stream:
        antwort = stream.get_final_message()
    text = "".join(b.text for b in antwort.content if b.type == "text")
    denken = "\n".join(b.thinking for b in antwort.content if b.type == "thinking")
    usage = {"prompt_tokens": antwort.usage.input_tokens, "completion_tokens": antwort.usage.output_tokens,
             "modell": antwort.model}
    ende = {"end_turn": "stop", "max_tokens": "length"}.get(antwort.stop_reason, antwort.stop_reason)
    if antwort.stop_reason == "refusal":
        usage["ablehnung"] = getattr(antwort.stop_details, "category", None) if antwort.stop_details else None
    if a.ersatz:
        wechsel = [{"von": b.from_.model, "nach": b.to.model,
                    "grund": getattr(b.trigger, "category", None) or getattr(b.trigger, "type", None)}
                   for b in antwort.content if b.type == "fallback"]
        iterationen = antwort.usage.iterations or []
        ersatz_lief = any(getattr(i, "type", None) == "fallback_message" for i in iterationen)
        if wechsel or ersatz_lief or antwort.model != modell:
            usage["ersatz"] = antwort.model     # Ersatzmodell hat geantwortet (auch bei "klebender" Weiterleitung)
            usage["ersatz_wechsel"] = wechsel   # leer, wenn die Anfrage direkt beim Ersatz landete
    return text, denken, usage, ende


def frage(a, nachrichten):
    if a.anbieter == "anthropic":
        return frage_claude(a, nachrichten)
    daten = {"messages": nachrichten,
             "max_tokens": a.max_tokens, "temperature": a.temperatur}
    for schluessel in ("top_p", "top_k", "min_p"):
        if getattr(a, schluessel) is not None:
            daten[schluessel] = getattr(a, schluessel)
    if a.reasoning_effort:
        daten["reasoning_effort"] = a.reasoning_effort
    if a.denk_budget is not None:
        daten["thinking_budget_tokens"] = a.denk_budget   # PrismML-Fork: Denkteil endet nach N Tokens
    if a.modell:
        daten["model"] = a.modell
    kopf = {"Content-Type": "application/json"}
    if a.api_key:
        kopf["Authorization"] = f"Bearer {a.api_key}"
    anfrage = urllib.request.Request(f"{a.url.rstrip('/')}/chat/completions",
                                     data=json.dumps(daten).encode(), headers=kopf)
    with urllib.request.urlopen(anfrage, timeout=a.timeout) as r:
        antwort = json.load(r)
    wahl = antwort["choices"][0]
    nachricht = wahl["message"]
    # Denkteil getrennt speichern, damit pruefen.py nur die eigentliche Antwort auswertet
    return (nachricht.get("content") or ""), (nachricht.get("reasoning_content") or ""), \
        antwort.get("usage", {}), wahl.get("finish_reason")


def kurz(text, n=3000):
    return text if len(text) <= n else text[:n] + f"\n[... {len(text) - n} Zeichen gekürzt]"


def disassemblierung(datei):
    """objdump-Ausgabe ab dem Einsprungpunkt, soweit der ELF-Kopf das hergibt."""
    if not shutil.which("objdump"):
        return "(objdump nicht installiert)"
    daten = open(datei, "rb").read()
    start = 0x78
    try:
        einsprung, phoff = struct.unpack_from("<QQ", daten, 24)
        phentsize, phnum = struct.unpack_from("<HH", daten, 54)
        for k in range(phnum):
            typ, _, offset, vaddr, _, filesz = struct.unpack_from("<IIQQQQ", daten, phoff + k * phentsize)
            if typ == 1 and vaddr <= einsprung < vaddr + filesz:
                start = offset + einsprung - vaddr
                break
    except struct.error:
        pass
    if start >= len(daten):
        return f"(Einsprungpunkt zeigt auf Dateiposition 0x{start:x}, die Datei ist nur {len(daten)} Byte lang)"
    r = subprocess.run(["objdump", "-D", "-b", "binary", "-m", "i386:x86-64", f"--start-address=0x{start:x}", datei],
                       capture_output=True, text=True)
    zeilen = [z for z in r.stdout.splitlines() if re.match(r"\s+[0-9a-f]+:", z)]
    return f"Ab Dateiposition 0x{start:x}:\n" + "\n".join(zeilen[:150]) + ("\n[... gekürzt]" if len(zeilen) > 150 else "")


def rueckmeldung(aid, modus, text, arbeit, abgeschnitten):
    """Baut und testet eine Abgabe. Gibt (bestanden, Kurzinfo, Rückmeldungstext fürs Modell) zurück."""
    os.makedirs(arbeit, exist_ok=True)
    ziel = f"{arbeit}/programm"
    antwort = f"{arbeit}/antwort.txt"
    open(antwort, "w", encoding="utf-8").write(text)
    groesse, fehler = baue(antwort, modus, ziel)
    details = []
    if fehler:
        ok, info = False, fehler
    else:
        ok, info = teste(ziel, tests_fuer(aid, arbeit), details)
    if ok:
        return True, info, ""
    teile = [f"Ergebnis deiner Abgabe: {info}"]
    if fehler and abgeschnitten:
        teile.append("Deine Antwort wurde wegen Längenbegrenzung abgeschnitten, bevor die Markierungen vollständig waren.")
    if fehler and fehler.startswith("Compilerfehler"):
        r = subprocess.run(["gcc", "-O2", "-o", ziel, f"{ziel}.c"], capture_output=True, text=True)
        meldungen = "\n".join(r.stderr.replace(f"{ziel}.c", "programm.c").splitlines()[:40])
        teile.append("Compilermeldungen:\n" + meldungen)
    if details:
        d = details[0]
        f, r = d["fall"], d["lauf"]
        teile.append(f"Testfall {d['nummer']}: Argumente {f['args']!r}, stdin {kurz(repr(f['stdin']), 600)}")
        teile.append(f"Erwartete Ausgabe: {kurz(repr(f['erwartet']), 600)}")
        if r is not None:
            teile.append(f"Tatsächliche Ausgabe: {kurz(repr(r.stdout), 600)}")
            teile.append(f"Exit-Code: {r.returncode}" + (f" (Signal {-r.returncode})" if r.returncode < 0 else ""))
            if r.stderr:
                teile.append(f"stderr: {kurz(repr(r.stderr), 300)}")
    if modus.startswith("bin") and groesse:
        teile.append(f"Dateigröße: {groesse} Byte")
        if shutil.which("readelf"):
            r = subprocess.run(["readelf", "-h", "-l", "-W", ziel], capture_output=True, text=True)
            teile.append("readelf -h -l:\n" + kurz((r.stdout + r.stderr).replace(ziel, "programm").strip(), 2500))
        teile.append("Disassemblierung deiner Bytes (objdump, nur zur Information):\n" + disassemblierung(ziel))
    marke = ("BEGIN_HEX", "END_HEX") if modus.startswith("bin") else ("BEGIN_C", "END_C")
    teile.append(f"Korrigiere das Programm und gib die vollständige neue Fassung wieder zwischen {marke[0]} und {marke[1]} aus.")
    return False, info, "\n\n".join(teile)


def verlauf_eintrag(text, modus):
    """Eigene frühere Antwort für den Verlauf: nur der abgegebene Block, damit der Kontext nicht überläuft."""
    marke = ("BEGIN_HEX", "END_HEX") if modus.startswith("bin") else ("BEGIN_C", "END_C")
    block = letzter_block(text, *marke)
    if block is not None and len(block) < 20000:
        return f"{marke[0]}{block}{marke[1]}"
    return kurz(text, 4000)


def ein_auftrag(a, ordner, protokoll, aid, modus, lauf):
    ziel = f"{ordner}/{aid}_{modus}_{lauf}.txt"
    vorlage = PROMPT_BIN if modus.startswith("bin") else PROMPT_C
    prompt = vorlage.format(aufgabe=AUFGABEN[aid]["text"])
    runden = a.runden if modus.endswith("_runden") else 1
    if runden > 1:
        prompt += ZUSATZ_RUNDEN.format(runden=runden)
    nachrichten = [{"role": "user", "content": prompt}]
    name = f"{aid}_{modus}_{lauf}"
    gesamt_sek, gesamt_tok, runde = 0.0, 0, 0
    for runde in range(1, runden + 1):
        start = time.time()
        try:
            text, denken, usage, ende = frage(a, nachrichten)
            fehler = None
        except Exception as e:  # Abbruch zählt als "keine Abgabe"
            text, denken, usage, ende, fehler = "", "", {}, None, repr(e)
        if ende == "refusal":   # Sicherheitsfilter: zählt wie "keine Abgabe", keine weiteren Runden
            fehler = f"Ablehnung durch Sicherheitsfilter (Kategorie {usage.get('ablehnung')})"
        dauer = round(time.time() - start, 1)
        gesamt_sek += dauer
        gesamt_tok += usage.get("completion_tokens", 0) or 0
        if runden > 1:
            ok, info, rm = rueckmeldung(aid, modus, text, f"{ordner}/bau/runden/{name}", ende == "length")
        with sperre:
            if runden > 1:
                os.makedirs(f"{ordner}/runden", exist_ok=True)
                open(f"{ordner}/runden/{name}_r{runde}.txt", "w", encoding="utf-8").write(text)
                if rm:
                    open(f"{ordner}/runden/{name}_r{runde}_rueckmeldung.txt", "w", encoding="utf-8").write(rm)
            if denken:
                os.makedirs(f"{ordner}/denken", exist_ok=True)
                endung = f"_r{runde}" if runden > 1 else ""
                open(f"{ordner}/denken/{name}{endung}.txt", "w", encoding="utf-8").write(denken)
            if runden > 1:
                protokoll.write(json.dumps({"datei": f"runden/{name}_r{runde}.txt", "runde": runde, "sekunden": dauer,
                                            "usage": usage, "finish_reason": ende, "fehler": fehler, "ok": ok,
                                            "info": info, "zeit": datetime.datetime.now().isoformat()}) + "\n")
                protokoll.flush()
            tok = usage.get("completion_tokens", "?")
            hinweis = "  ABGESCHNITTEN (max_tokens)" if ende == "length" else ""
            if usage.get("ersatz"):
                hinweis += f"  ERSATZ {usage['ersatz']}"
            rinfo = f" Runde {runde}: {'OK' if ok else info}" if runden > 1 else ""
            print(f"{name}{rinfo}  {dauer} s, {tok} Tokens{hinweis}" + (f"  FEHLER {fehler}" if fehler else ""),
                  flush=True)
        if runden == 1 or ok or fehler:
            break
        # Nur die letzte Abgabe und ihre Rückmeldung mitgeben, damit der Kontext je Slot nicht überläuft
        nachrichten = nachrichten[:1] + [{"role": "assistant", "content": verlauf_eintrag(text, modus)},
                                         {"role": "user", "content": rm}]
    with sperre:
        open(ziel, "w", encoding="utf-8").write(text)
        eintrag = {"datei": os.path.basename(ziel), "sekunden": round(gesamt_sek, 1), "usage": usage,
                   "finish_reason": ende, "fehler": fehler, "zeit": datetime.datetime.now().isoformat()}
        if runden > 1:
            eintrag.update({"runden": runde, "tokens_gesamt": gesamt_tok})
        protokoll.write(json.dumps(eintrag) + "\n")
        protokoll.flush()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--anbieter", default="openai", choices=["openai", "anthropic"],
                   help="openai: OpenAI-kompatibler Server (llama.cpp); anthropic: Claude-API über das anthropic-Paket")
    p.add_argument("--url", default="http://localhost:8080/v1")
    p.add_argument("--modell", default="", help="Modellname; bei anthropic Standard claude-opus-5-5")
    p.add_argument("--ersatz", action="store_true",
                   help="nur anthropic: bei Ablehnung durch den Sicherheitsfilter serverseitig auf das von Anthropic "
                        "vorgesehene Ersatzmodell ausweichen (fallbacks=default, Beta); antwortendes Modell wird protokolliert")
    p.add_argument("--api_key", default=os.environ.get("API_KEY", ""))
    p.add_argument("--name", required=True, help="Name des Laufordners unter laeufe/")
    p.add_argument("--laeufe", type=int, default=3)
    p.add_argument("--aufgaben", default=",".join(AUFGABEN))
    p.add_argument("--modi", default="bin,c", help="bin, c, bin_runden, c_runden")
    p.add_argument("--runden", type=int, default=5, help="max. Abgaben je Lauf in den _runden-Modi")
    p.add_argument("--max_tokens", type=int, default=None, help="Standard 16384, bei anthropic 64000")
    p.add_argument("--temperatur", type=float, default=0.6)
    p.add_argument("--top_p", type=float, default=None)
    p.add_argument("--top_k", type=int, default=None)
    p.add_argument("--min_p", type=float, default=None)
    p.add_argument("--reasoning_effort", default="", help="z. B. medium oder xhigh (Bonsai); bei anthropic Standard high")
    p.add_argument("--denk_budget", type=int, default=None, help="max. Denk-Tokens, danach Antwort")
    p.add_argument("--parallel", type=int, default=1, help="gleichzeitige Anfragen (Server-Slots)")
    p.add_argument("--timeout", type=int, default=3600, help="Sekunden je Anfrage")
    a = p.parse_args()
    unbekannt = set(a.modi.split(",")) - {"bin", "c", "bin_runden", "c_runden"}
    if unbekannt:
        sys.exit(f"Unbekannte Modi: {', '.join(sorted(unbekannt))}. Erlaubt: bin, c, bin_runden, c_runden")
    if a.max_tokens is None:
        a.max_tokens = 64000 if a.anbieter == "anthropic" else 16384
    if a.anbieter == "anthropic":
        import anthropic  # früh scheitern, falls das Paket fehlt

    ordner = f"{BASIS}/laeufe/{a.name}"
    os.makedirs(ordner, exist_ok=True)
    # Sperre gegen Doppelstart: zwei Prozesse auf demselben Laufordner würden dieselben Anfragen doppelt stellen
    sperrdatei = f"{ordner}/lauf.pid"
    if os.path.exists(sperrdatei):
        alt_pid = open(sperrdatei).read().strip()
        if alt_pid.isdigit() and os.path.exists(f"/proc/{alt_pid}"):
            sys.exit(f"Lauf {a.name} läuft bereits (PID {alt_pid}). Erst beenden oder abwarten; "
                     f"ist der Prozess sicher weg, {sperrdatei} löschen.")
    open(sperrdatei, "w").write(str(os.getpid()))
    protokoll = open(f"{ordner}/protokoll.jsonl", "a")

    auftraege = []
    for aid in a.aufgaben.split(","):
        for modus in a.modi.split(","):
            for lauf in range(1, a.laeufe + 1):
                if os.path.exists(f"{ordner}/{aid}_{modus}_{lauf}.txt"):
                    print(f"{aid}_{modus}_{lauf}: schon vorhanden, übersprungen")
                else:
                    auftraege.append((aid, modus, lauf))
    print(f"{len(auftraege)} Anfragen, {a.parallel} gleichzeitig", flush=True)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.parallel) as pool:
            list(pool.map(lambda t: ein_auftrag(a, ordner, protokoll, *t), auftraege))
    finally:
        if os.path.exists(sperrdatei):
            os.remove(sperrdatei)


if __name__ == "__main__":
    main()
