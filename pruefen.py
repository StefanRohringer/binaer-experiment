"""Baut und testet alle Antworten eines Laufordners und schreibt ergebnisse.json hinein.

Aufruf:  python3 pruefen.py laeufe/<ordner>

Dateinamen im Ordner: <Aufgabe>_<Modus>_<Lauf>.txt, z. B. T3_bin_2.txt oder T7_bin_runden_1.txt
Modi bin_runden / c_runden (frage_modell.py --modi): die Datei enthält die letzte Runde; wie viele
Runden gebraucht wurden, steht im Protokoll und wird in ergebnisse.json übernommen.
Binär-Antworten: Hex zwischen BEGIN_HEX und END_HEX -> Datei -> ausführen.
C-Antworten: Code zwischen BEGIN_C und END_C -> gcc -O2 -> ausführen.
Stehen die Markierungen mehrfach in der Antwort (z. B. in einem Denkblock), zählt der letzte Block.
"""
import glob, json, os, re, subprocess, sys
from collections import defaultdict

BASIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASIS)
from aufgaben import tests_fuer


def letzter_block(text, anfang, ende):
    treffer = re.findall(re.escape(anfang) + r"(.*?)" + re.escape(ende), text, re.S)
    return treffer[-1] if treffer else None


def hex_mit_offsets(block):
    """Ehemaliger Modus bin_offsets (Lauf 7 in ERGEBNIS.md, aus frage_modell.py wieder entfernt): Zeilen der Form
    'OFFSET: BYTES ; Kommentar', Offsets werden gegen die tatsächliche Dateiposition geprüft. Bleibt hier, damit
    laeufe/claude_opus48_offsets weiterhin nachprüfbar ist."""
    daten = bytearray()
    for nr, zeile in enumerate(block.splitlines(), 1):
        z = zeile.split(";", 1)[0].strip()
        if not z or z.startswith("```"):
            continue
        m = re.fullmatch(r"(?:0x)?([0-9a-fA-F]{1,8})\s*:\s*(.*)", z)
        if not m:
            return None, f"Zeile {nr} nicht im Format OFFSET: BYTES: {zeile.strip()[:50]!r}"
        paare = m.group(2).split()
        if not paare or any(len(x) != 2 or not re.fullmatch(r"[0-9a-fA-F]{2}", x) for x in paare):
            return None, f"Zeile {nr}: BYTES müssen Hexpaare mit Leerzeichen sein: {zeile.strip()[:50]!r}"
        offset = int(m.group(1), 16)
        if offset != len(daten):
            return None, f"Offset-Fehler in Zeile {nr}: angegeben 0x{offset:x}, tatsächliche Dateiposition 0x{len(daten):x}"
        daten += bytes.fromhex("".join(paare))
    if not daten:
        return None, "leerer Hexblock"
    return bytes(daten), None


def baue(pfad, modus, ziel):
    text = open(pfad, encoding="utf-8", errors="replace").read()
    if modus.startswith("bin"):
        block = letzter_block(text, "BEGIN_HEX", "END_HEX")
        if block is None:
            return None, "keine Abgabe/Markierung"
        if modus.startswith("bin_offsets"):
            daten, fehler = hex_mit_offsets(block)
            if fehler:
                return None, fehler
        else:
            hexstr = re.sub(r"[^0-9a-fA-F]", "", block)
            if not hexstr:
                return None, "leerer Hexblock"
            if len(hexstr) % 2:
                return None, "ungerade Hexlänge"
            daten = bytes.fromhex(hexstr)
        open(ziel, "wb").write(daten)
        os.chmod(ziel, 0o755)
        return len(daten), None
    block = letzter_block(text, "BEGIN_C", "END_C")
    if block is None:
        return None, "keine Abgabe/Markierung"
    quelle = f"{ziel}.c"
    open(quelle, "w").write(block)
    r = subprocess.run(["gcc", "-O2", "-o", ziel, quelle], capture_output=True, text=True)
    if r.returncode:
        zeilen = r.stderr.strip().splitlines() or ["?"]
        erste = next((z for z in zeilen if "error" in z), zeilen[-1])
        return None, "Compilerfehler: " + erste.replace(quelle, "programm.c")[:120]
    return os.path.getsize(ziel), None


def teste(ziel, faelle, details=None):
    """Führt alle Testfälle aus. details (Liste) bekommt beim ersten Fehlschlag den Testfall und die Ausgabe."""
    for i, f in enumerate(faelle):
        try:
            r = subprocess.run([ziel] + f["args"], input=f["stdin"], capture_output=True, timeout=3)
        except subprocess.TimeoutExpired:
            fehler, r = f"Test {i+1}: Zeitüberschreitung", None
        except OSError as e:
            fehler, r = f"Test {i+1}: startet nicht ({e.strerror})", None
        else:
            fehler = None
            if r.returncode < 0:
                fehler = f"Test {i+1}: Absturz (Signal {-r.returncode})"
            elif r.stdout != f["erwartet"]:
                fehler = f"Test {i+1}: falsche Ausgabe {r.stdout[:40]!r}"
            elif r.returncode != 0:
                fehler = f"Test {i+1}: Exit-Code {r.returncode}"
        if fehler:
            if details is not None:
                details.append({"fall": f, "nummer": i + 1, "lauf": r})
            return False, fehler
    return True, f"{len(faelle)}/{len(faelle)} Tests bestanden"


def main():
    if len(sys.argv) != 2:
        sys.exit("Aufruf: python3 pruefen.py laeufe/<ordner>")
    ordner = os.path.abspath(sys.argv[1])
    arbeit = f"{ordner}/bau"
    os.makedirs(arbeit, exist_ok=True)

    # Abgeschnittene Antworten aus dem Protokoll von frage_modell.py erkennen
    abgeschnitten, abgelehnt = set(), set()
    runden, ersatz = {}, {}
    if os.path.exists(f"{ordner}/protokoll.jsonl"):
        for zeile in open(f"{ordner}/protokoll.jsonl"):
            e = json.loads(zeile)
            if e.get("finish_reason") == "length":
                abgeschnitten.add(e["datei"][:-4])
            if e.get("finish_reason") == "refusal":
                abgelehnt.add(e["datei"][:-4])
            if "runden" in e:   # Rundenmodus: letzter Eintrag je Datei zählt
                runden[e["datei"][:-4]] = e["runden"]
            if (e.get("usage") or {}).get("ersatz"):   # frage_modell.py --ersatz: Ersatzmodell hat geantwortet
                ersatz[e["datei"][:-4]] = e["usage"]["ersatz"]

    ergebnisse = []
    for pfad in sorted(glob.glob(f"{ordner}/T*_*_*.txt")):
        name = os.path.basename(pfad)[:-4]
        aid, *teile, lauf = name.split("_")
        modus = "_".join(teile)
        ziel = f"{arbeit}/{name}"
        groesse, fehler = baue(pfad, modus, ziel)
        ok, info = (False, fehler) if fehler else teste(ziel, tests_fuer(aid, arbeit))
        if fehler and name in abgelehnt:
            info = "Ablehnung durch Sicherheitsfilter"
        elif fehler and name in abgeschnitten:
            laenge = len(open(pfad, encoding="utf-8", errors="replace").read().strip())
            info = ("abgeschnitten: Schleife in der Antwort" if laenge > 2000
                    else "abgeschnitten: im Denken steckengeblieben")
        ergebnisse.append({"aufgabe": aid, "modus": modus, "lauf": int(lauf), "ok": ok, "info": info,
                           "groesse_byte": groesse,
                           "antwort_zeichen": len(open(pfad, encoding="utf-8", errors="replace").read())})
        if name in runden:
            ergebnisse[-1]["runden"] = runden[name]
            info += f"  (Runde {runden[name]})"
        if name in ersatz:
            ergebnisse[-1]["ersatz"] = ersatz[name]
            info += f"  [Ersatz: {ersatz[name]}]"
        print(f"{name:18} {'OK  ' if ok else 'FEHL'}  {str(groesse):>7} B  {info}")

    json.dump(ergebnisse, open(f"{ordner}/ergebnisse.json", "w"), indent=1, ensure_ascii=False)

    zusammen = defaultdict(lambda: [0, 0])
    for e in ergebnisse:
        zusammen[(e["aufgabe"], e["modus"])][0] += e["ok"]
        zusammen[(e["aufgabe"], e["modus"])][1] += 1
    reihenfolge = ["bin", "bin_offsets", "c", "bin_runden", "bin_offsets_runden", "c_runden"]
    modi = sorted({m for _, m in zusammen}, key=lambda m: (reihenfolge.index(m) if m in reihenfolge else 99, m))
    print("\nAufgabe  " + "".join(f"{m:>12}" for m in modi))
    for aid in sorted({a for a, _ in zusammen}):
        zeile = "".join(f"{'%d/%d' % tuple(zusammen[(aid, m)]) if (aid, m) in zusammen else '-':>12}" for m in modi)
        print(f"{aid:8} {zeile}")


if __name__ == "__main__":
    main()
