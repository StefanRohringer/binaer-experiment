"""Aufgaben und Testfälle für das Experiment: Maschinencode direkt vs. C mit Compiler."""
import random

AUFGABEN = {
    "T1": {
        "name": "Hallo Welt",
        "text": 'Gib genau "Hallo Welt" gefolgt von einem Zeilenumbruch auf stdout aus und beende dich mit Exit-Code 0.',
        "tests": [{"stdin": b"", "args": [], "erwartet": b"Hallo Welt\n"}],
    },
    "T2": {
        "name": "Rechnen",
        "text": "Berechne zur Laufzeit 12345 * 6789 und gib das Ergebnis als Dezimalzahl gefolgt von einem Zeilenumbruch auf stdout aus. Exit-Code 0.",
        "tests": [{"stdin": b"", "args": [], "erwartet": b"83810205\n"}],
    },
    "T3": {
        "name": "FizzBuzz",
        "text": 'Gib für die Zahlen 1 bis 30 je eine Zeile aus: "FizzBuzz" wenn durch 15 teilbar, sonst "Fizz" wenn durch 3 teilbar, sonst "Buzz" wenn durch 5 teilbar, sonst die Zahl selbst. Jede Zeile endet mit Zeilenumbruch. Exit-Code 0.',
        "tests": [{"stdin": b"", "args": [], "erwartet": "".join(
            ("FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i)) + "\n"
            for i in range(1, 31)).encode()}],
    },
    "T4": {
        "name": "Zeile umkehren",
        "text": "Lies eine Zeile (höchstens 200 Byte, endet mit Zeilenumbruch) von stdin und gib ihren Inhalt ohne den Zeilenumbruch rückwärts aus, gefolgt von einem Zeilenumbruch. Exit-Code 0.",
        "tests": [
            {"stdin": b"Hallo Stefan\n", "args": [], "erwartet": b"nafetS ollaH\n"},
            {"stdin": b"a\n", "args": [], "erwartet": b"a\n"},
            {"stdin": b"Spritzguss 2026!\n", "args": [], "erwartet": b"!6202 ssugztirpS\n"},
        ],
    },
    "T5": {
        "name": "Zeilen zählen",
        "text": "Das erste Kommandozeilenargument ist ein Dateipfad. Öffne die Datei (höchstens 1 MB), zähle die Zeilenumbruch-Zeichen darin und gib die Anzahl als Dezimalzahl gefolgt von einem Zeilenumbruch auf stdout aus. Exit-Code 0.",
        "tests": "datei",  # wird im Runner erzeugt
    },
    "T6": {
        "name": "Zahlen sortieren",
        "text": "Lies von stdin bis zum Dateiende bis zu 100 nicht-negative ganze Zahlen (jede kleiner als 1000000), eine pro Zeile, jede Zeile endet mit Zeilenumbruch. Gib sie aufsteigend sortiert aus, eine pro Zeile mit Zeilenumbruch. Exit-Code 0.",
        "tests": "sortieren",
    },
    "T7": {
        "name": "Ausdrucksrechner",
        "text": "Lies eine Zeile (höchstens 200 Byte, endet mit Zeilenumbruch) von stdin. Sie enthält einen Rechenausdruck aus nicht-negativen ganzen Zahlen, den Operatoren + - * / und runden Klammern; Leerzeichen können zwischen allen Teilen vorkommen. Es gilt Punkt vor Strich, Klammern zuerst, gleichrangige Operatoren werden von links nach rechts ausgewertet. / ist ganzzahlige Division, die Richtung null abschneidet (-7/2 ergibt -3). Alle Zwischenergebnisse passen in eine 64-Bit-Zahl mit Vorzeichen, es wird nie durch null geteilt. Gib das Ergebnis als Dezimalzahl aus (negativ mit führendem Minuszeichen), gefolgt von einem Zeilenumbruch. Exit-Code 0.",
        "tests": [{"stdin": e.encode() + b"\n", "args": [], "erwartet": w.encode() + b"\n"} for e, w in [
            ("1+2", "3"),
            ("2*(3+4)-5", "9"),
            ("2+3*4*5-6/2", "59"),
            ("100/7", "14"),
            ("7-10", "-3"),
            ("(0-7)/2", "-3"),
            ("((15)) * 2 - 3*4/5", "28"),
            ("123456*1000+789-(42/(3+3))", "123456782"),
            ("1000000000*1000000000-1", "999999999999999999"),
            ("10-2-3-(1-(2-3))", "3"),
        ]],
    },
    "T8": {
        "name": "Variablenrechner",
        "text": 'Lies von stdin bis zum Dateiende ein kleines Programm (höchstens 4000 Byte, jede Zeile höchstens 200 Byte und mit Zeilenumbruch beendet). Jede Zeile ist entweder leer, eine Zuweisung der Form name = ausdruck oder eine Ausgabe der Form print ausdruck. Namen bestehen aus 1 bis 8 Kleinbuchstaben a bis z (print ist kein Name); es kommen höchstens 30 verschiedene Namen vor. Ein Ausdruck besteht aus nicht-negativen ganzen Zahlen, Namen, den Operatoren + - * / % und runden Klammern; Leerzeichen können zwischen allen Teilen vorkommen. Es gilt Punkt vor Strich (* / % vor + -), Klammern zuerst, gleichrangige Operatoren werden von links nach rechts ausgewertet. / ist ganzzahlige Division, die Richtung null abschneidet (-7/2 ergibt -3), % der zugehörige Rest mit dem Vorzeichen des Dividenden wie in C (-7%2 ergibt -1). Jeder Name ist zugewiesen, bevor er benutzt wird; eine erneute Zuweisung überschreibt den Wert. Alle Zwischenergebnisse passen in eine 64-Bit-Zahl mit Vorzeichen, es wird nie durch null geteilt. Gib für jede print-Zeile in Programmreihenfolge den Wert als Dezimalzahl aus (negativ mit führendem Minuszeichen), gefolgt von einem Zeilenumbruch. Exit-Code 0.',
        "tests": [
            {"stdin": b'print 1+2\n', "args": [], "erwartet": b'3\n'},
            {"stdin": b'x = 5\nprint x*2\n', "args": [], "erwartet": b'10\n'},
            {"stdin": b'a = 3\nb = 4\nc = a*a + b*b\nprint c\nprint c / 5\n', "args": [], "erwartet": b'25\n5\n'},
            {"stdin": b'n = 10\nn = n - 3\nn = n * n\nprint n\n', "args": [], "erwartet": b'49\n'},
            {"stdin": b'x = 7 - 10\nprint x\nprint x % 2\nprint 17 % 5\nprint (0-7)/2\n', "args": [], "erwartet": b'-3\n-1\n2\n-3\n'},
            {"stdin": b'breite = 12\nhoehe=7\n\nflaeche   =breite*hoehe\nprint (flaeche + 16) / breite\n', "args": [], "erwartet": b'8\n'},
            {"stdin": b'x = 2\ny = 3\nprint ((x+y)*(x-y)) / (x - y + 2)\nprint 10-2-3-(1-(2-3))\n', "args": [], "erwartet": b'-5\n3\n'},
            {"stdin": b'big = 1000000000 * 1000000000\nprint big - 1\nprint big / 7 % 1000\n', "args": [], "erwartet": b'999999999999999999\n857\n'},
            # Fibonacci-Kette: 30 Durchläufe mit drei Zuweisungen, dann zwei Ausgaben
            {"stdin": ("a = 0\nb = 1\n" + "c = a + b\na = b\nb = c\n" * 30 + "print b\nprint a * b % 1000\n").encode(),
             "args": [], "erwartet": b"1346269\n760\n"},
            # 26 Variablen a bis z
            {"stdin": ("".join(f"{chr(97 + i)} = {i + 1}\n" for i in range(26))
                       + "print " + "+".join(chr(97 + i) for i in range(26)) + "\nprint z*y*x\n").encode(),
             "args": [], "erwartet": b"351\n15600\n"},
        ],
    },
    "T9": {
        "name": "Funktionsrechner",
        "text": 'Lies von stdin bis zum Dateiende ein kleines Programm (höchstens 8000 Byte, jede Zeile höchstens 200 Byte und mit Zeilenumbruch beendet). Jede Zeile ist entweder leer, eine Zuweisung name = ausdruck, eine Ausgabe print ausdruck oder eine Funktionsdefinition def name(p1, p2, ...) = ausdruck mit 1 bis 4 Parametern. Namen bestehen aus 1 bis 8 Kleinbuchstaben a bis z; print und def sind Schlüsselwörter, keine Namen. Es gibt höchstens 30 Variablen und 20 Funktionen. Ein Ausdruck besteht aus nicht-negativen ganzen Zahlen, Namen, Funktionsaufrufen name(arg, ...), den Operatoren + - * / % < > <= >= == != sowie dem Bedingungsausdruck bedingung ? a : b und runden Klammern; Leerzeichen können zwischen allen Teilen vorkommen. Rangfolge von stark nach schwach: Klammern und Aufrufe, dann * / %, dann + -, dann die Vergleiche (Ergebnis 1 oder 0, nie verkettet), dann ? : (schwächste Stufe, rechtsgebunden: a ? b : c ? d : e bedeutet a ? b : (c ? d : e)). Gleichrangige Operatoren werden von links nach rechts ausgewertet. / ist ganzzahlige Division mit Abschneiden Richtung null, % der Rest mit dem Vorzeichen des Dividenden wie in C. Bei ? : wird nur der gewählte Zweig ausgewertet. Im Rumpf einer Funktion bezeichnen Namen zuerst ihre Parameter, sonst Variablen mit dem Wert zur Zeit des Aufrufs. Eine Funktion darf sich selbst und alle vorher definierten Funktionen aufrufen; die Rekursionstiefe ist höchstens 200. Jeder Name ist definiert, bevor er benutzt wird; eine erneute Zuweisung an eine Variable überschreibt den Wert. Alle ausgewerteten Zwischenergebnisse passen in eine 64-Bit-Zahl mit Vorzeichen, es wird nie durch null geteilt. Gib für jede print-Zeile in Programmreihenfolge den Wert als Dezimalzahl aus (negativ mit führendem Minuszeichen), gefolgt von einem Zeilenumbruch. Exit-Code 0.',
        "tests": [
            {"stdin": b'def quadrat(x) = x * x\nprint quadrat(7)\n', "args": [], "erwartet": b'49\n'},
            {"stdin": b'print 3 < 5\nprint 5 < 3\nprint 2 == 2\nprint 2 != 2\nprint 7 >= 7\nprint 6 <= 5\nprint 1 ? 10 : 20\nprint 0 ? 10 : 20\n', "args": [], "erwartet": b'1\n0\n1\n0\n1\n0\n10\n20\n'},
            {"stdin": b'def fak(n) = n < 2 ? 1 : n * fak(n - 1)\nprint fak(10)\nprint fak(20)\n', "args": [], "erwartet": b'3628800\n2432902008176640000\n'},
            {"stdin": b'def ggt(a, b) = b == 0 ? a : ggt(b, a % b)\nprint ggt(1071, 462)\nprint ggt(17, 5)\n', "args": [], "erwartet": b'21\n1\n'},
            {"stdin": b'faktor = 3\ndef lin(a, b) = a * faktor + b\nprint lin(4, 5)\nfaktor = 10\nprint lin(4, 5)\n', "args": [], "erwartet": b'17\n45\n'},
            {"stdin": b'def inc(x) = x + 1\ndef twice(x) = inc(inc(x))\ndef addd(a, b, c) = a + b + c\nprint twice(5)\nprint addd(twice(1), inc(2), 4)\nprint twice(twice(twice(0)))\n', "args": [], "erwartet": b'7\n10\n6\n'},
            {"stdin": b'def fib(n) = n < 2 ? n : fib(n - 1) + fib(n - 2)\nprint fib(20)\n', "args": [], "erwartet": b'6765\n'},
            {"stdin": b'def summe(n) = n == 0 ? 0 : n + summe(n - 1)\nprint summe(150)\ndef sicher(a, b) = b == 0 ? 0 - 1 : a / b\nprint sicher(10, 0)\nprint sicher(10, 3)\n', "args": [], "erwartet": b'11325\n-1\n3\n'},
            {"stdin": b'x = 5\nprint x * 2 > 9 ? x + 1 : x - 1\nprint (x > 3) + (x > 10) * 5\nprint 1 + 2 * 3 == 7 ? 100 % 7 : 0\nprint (0 - 7) / 2\nprint (0 - 7) % 2\n', "args": [], "erwartet": b'6\n1\n2\n-3\n-1\n'},
            {"stdin": b'def pot(b, e) = e == 0 ? 1 : b * pot(b, e - 1)\ndef collatz(n, s) = n == 1 ? s : n % 2 == 0 ? collatz(n / 2, s + 1) : collatz(3 * n + 1, s + 1)\n\nprint pot(2, 62) - 1\nprint collatz(27, 0)\nprint pot(3, 4) * pot(2, 10)\n', "args": [], "erwartet": b'4611686018427387903\n111\n82944\n'},
        ],
    },
}


def tests_fuer(aid, arbeitsordner):
    t = AUFGABEN[aid]["tests"]
    if t == "datei":
        faelle = []
        for i, inhalt in enumerate([b"eins\nzwei\ndrei\n", b"", b"x" * 5000 + b"\n" * 777 + b"ende",
                                    b"\n".join(b"zeile %d" % k for k in range(20000)) + b"\n"]):
            p = f"{arbeitsordner}/eingabe_{i}.txt"
            open(p, "wb").write(inhalt)
            faelle.append({"stdin": b"", "args": [p], "erwartet": b"%d\n" % inhalt.count(b"\n")})
        return faelle
    if t == "sortieren":
        rnd = random.Random(42)
        faelle = []
        for zahlen in ([5, 3, 9, 1], [42], [0, 999999, 7, 7, 100000, 3],
                       [rnd.randrange(1000000) for _ in range(100)]):
            faelle.append({"stdin": "".join(f"{z}\n" for z in zahlen).encode(), "args": [],
                           "erwartet": "".join(f"{z}\n" for z in sorted(zahlen)).encode()})
        return faelle
    return t
