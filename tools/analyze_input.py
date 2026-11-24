"""Stage 63 (input processing): the live check of the joystick path.  From the logs of tools/altirra_stick.cmd (one player, random stick values, Pac-Man cannot die) and tools/altirra_stick2.cmd (two players, Pac-Man can die so that
the turn passes to player 2 and STICK1 is read): for every frame the state before the input path (`SI`), the stick value the game read (`ST`), the state after it (`SO`) and the case of the dispatch (`MV`) are compared with
tools/input_model.py.  Also the coverage: every stick value, the cases of the code, the buffered turns, the reversals, the corners.
Usage: python -I tools/analyze_input.py analysis/raw-logs/stick*.txt [--write analysis/evidence-input-summary.txt]"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import input_model as I  # noqa: E402

SI = re.compile(r"^SI f=(\d+) x=(\d+) ac=(\d+) pd=(\d+) m=(\d+) at=(\d+) a8=(\d+)")
ST = re.compile(r"^ST f=(\d+) v=(\d+)(?: pia=(\d+))?")
SO = re.compile(r"^SO f=(\d+) ac=(\d+) pd=(\d+) at=(\d+) a8=(\d+)")
MV = re.compile(r"^MV f=(\d+) c=(\w+)")


def frames(path):
    """-> list of dicts: the lines of one pass of the input path (SI, ST, SO, MV) that belong together"""
    out = []
    cur = None
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if not ln.endswith(chr(10)):
                continue
            m = SI.match(ln)
            if m:
                g = [int(x) for x in m.groups()]
                cur = {"f": g[0], "x": g[1], "ac": g[2], "pd": g[3], "m": g[4], "at": g[5], "a8": g[6]}
                out.append(cur)
                continue
            if cur is None:
                continue
            m = ST.match(ln)
            if m and int(m.group(1)) == cur["f"] and "v" not in cur:
                cur["v"] = int(m.group(2))
                if m.group(3) is not None:
                    cur["pia"] = int(m.group(3))                 # the PIA port the OS copied the value from (a real press: tools/altirra_realstick.cmd)
                continue
            m = SO.match(ln)
            if m and int(m.group(1)) == cur["f"] and "ac2" not in cur:
                g = [int(x) for x in m.groups()]
                cur.update({"ac2": g[1], "pd2": g[2], "at2": g[3], "a82": g[4]})
                continue
            m = MV.match(ln)
            if m and int(m.group(1)) == cur["f"] and "case" not in cur:
                cur["case"] = m.group(2)
    return [c for c in out if all(k in c for k in ("v", "ac2", "case"))]


def check(paths):
    st = {"pia_n": 0, "pia_bad": 0, "n": 0, "bad": [], "players": Counter(), "stick": Counter(), "case": Counter(), "open": Counter(), "refused": 0, "multi": 0, "reversal": 0, "buffered": 0, "corner": 0, "immediate": 0, "cornerA": 0}
    for p in paths:
        for c in frames(p):
            w, d, a, cr = I.steer(c["v"], c["m"], c["pd"], c["ac"], c["at"], c["a8"])
            got = (c["ac2"], c["pd2"], c["at2"], c["a82"], c["case"])
            want = (w, d, a, cr, I.motion(d, c["m"]))
            if "pia" in c:
                st["pia_n"] += 1
                if c["v"] != c["pia"] & 0x0F:
                    st["pia_bad"] += 1
            st["n"] += 1
            if got != want:
                st["bad"].append((p, c, got, want))
            st["players"][c["x"]] += 1
            st["stick"][c["v"]] += 1
            st["case"][c["case"]] += 1
            st["open"][c["m"]] += 1
            pressed = (c["v"] ^ 0x0F) & 0xFF
            n = bin(pressed & 15).count("1")
            if pressed and n == 2:
                st["refused"] += 1
            if n >= 3:
                st["multi"] += 1
            if pressed and n in (1, 3, 4) and pressed & c["m"] and pressed != c["pd"]:
                st["immediate"] += 1
                if pressed == ({1: 2, 2: 1, 4: 8, 8: 4}.get(c["pd"])):
                    st["reversal"] += 1
            if c["ac"] & c["m"] and c["ac"] != c["pd"]:
                st["buffered"] += 1                              # the wanted direction became open: taken by the buffer
            if cr and not c["a8"]:
                st["corner"] += 1
    return st


def lines(paths, source="tools/altirra_stick.cmd, tools/altirra_stick2.cmd"):
    st = check(paths)
    L = ["Joystick path of MovePacMan against tools/input_model.py, in the real game (%s; %d logs): %d passes of `$B183-$B1C4`, %d disagree with the model" % (source, len(paths), st["n"], len(st["bad"])),
         "player on turn: " + ", ".join("%s: %d" % (("player %d" % (k + 1)), v) for k, v in sorted(st["players"].items())),
         "stick values read (0 = pressed): " + ", ".join("$%X:%d" % (k, v) for k, v in sorted(st["stick"].items())),
         "cases of the dispatch entered: " + ", ".join("%s %d" % kv for kv in sorted(st["case"].items())),
         "distinct sets of open directions seen at Pac-Man's cell: " + ", ".join("$%X" % k for k in sorted(st["open"])),
         "passes with two directions pressed (refused): %d; with three or four (taken as a wanted value that matches no direction): %d; a direction pressed that was open and different from the current one (taken at once): %d, of which a reversal: %d; buffered turns (the wanted direction became open): %d; corner flags set: %d" % (
             st["refused"], st["multi"], st["immediate"], st["reversal"], st["buffered"], st["corner"])]
    if st["pia_n"]:
        L.append("the OS's copy of the port: in %d passes the value the game read equals the PIA port (`$D300`) masked to four bits, %d differ" % (st["pia_n"], st["pia_bad"]))
    for p, c, got, want in st["bad"][:5]:
        L.append("MISMATCH %s: %r got %r want %r" % (os.path.basename(p), c, got, want))
    return L, st


CT = re.compile(r"^CT f=(\d+) m1=(\d+) m2=(\d+) s=(\d+),(\d+),(\d+),(\d+) y=(\d+),(\d+),(\d+),(\d+) py=(\d+)")
OUTCOME = re.compile(r"^(CE|CD) f=(\d+) x=(\d+)|^(CN) f=(\d+)")


def contacts(paths):
    """the contact test of the real game against `input_model.contact`: -> (passes, mismatches, outcome counts, near-miss passes (both registers set for a ghost and the Y too far))"""
    n, bad, kinds, near_miss, both = 0, [], Counter(), 0, 0
    for p in paths:
        cur = None
        with open(p, encoding="ascii", errors="replace") as fh:
            for ln in fh:
                if not ln.endswith(chr(10)):
                    continue
                m = CT.match(ln)
                if m:
                    g = [int(x) for x in m.groups()]
                    cur = {"f": g[0], "m1": g[1], "m2": g[2], "st": g[3:7], "gy": g[7:11], "py": g[11]}
                    continue
                m = OUTCOME.match(ln)
                if m and cur is not None:
                    if m.group(1):
                        f, kind, x = int(m.group(2)), ("eaten" if m.group(1) == "CE" else "death"), int(m.group(3))
                    else:
                        f, kind, x = int(m.group(5)), "none", None
                    if f != cur["f"]:
                        continue
                    want = contact(cur["m1"], cur["m2"], cur["py"], cur["gy"], cur["st"])
                    got = (kind, x)
                    n += 1
                    kinds[kind] += 1
                    if cur["m1"] & cur["m2"] & 15:
                        both += 1
                    if got != want:
                        bad.append((os.path.basename(p), cur, got, want))
                    cur = None
    return n, bad, kinds, both


def contact(*a):
    return I.contact(*a)


def evidence(stick_logs, contact_logs, real_logs=()):
    """the evidence file of stage 63: the exhaustive comparisons of the model with the code on the concrete 6502, and the two live comparisons"""
    L = ["Input processing (stage 63): the executable model tools/input_model.py against the real code and the real game.", ""]
    n, nb, first = I.check(players=(0, 1))
    L.append("Joystick path `$B182-$B1C4`, EXHAUSTIVE on the concrete 6502: STICK 0-15 x open directions 0-15 x current direction 0-15 x wanted direction 0-15 x the player on turn (STICK0 / STICK1): %d cases, %d mismatches (wanted direction, direction, ATRACT, corner flag and the case of the dispatch compared)" % (n, nb))
    import random
    rng = random.Random(5)
    import algorithm_models as A
    m = A.fresh(A.started_machine())
    bad = 0
    cnt = 0
    for st in list(range(16, 256)):
        for o, d, w in [(rng.randrange(16), rng.randrange(16), rng.randrange(16)) for _ in range(6)]:
            got = I.run_code(m, st, o, d, w)
            w2, d2, a2, c2 = I.steer(st, o, d, w, 0x55)
            cnt += 1
            if got != (w2, d2, a2, c2, I.motion(d2, o)):
                bad += 1
    L.append("Joystick path, the stick values the OS never gives (16-255: the high bits are kept in the wanted direction): %d random cases, %d mismatches" % (cnt, bad))
    n, nb, first = I.check_contacts(full=True)
    L.append("Contact test `$A84D-$A883`, EXHAUSTIVE on the concrete 6502: M1PL 0-15 x M2PL 0-15 x the four ghosts' state classes (bit 7, bit 6) x near / far in Y for each ghost: %d cases, %d mismatches" % (n, nb))
    L.append("")
    L.extend(lines(stick_logs)[0])
    if real_logs:
        L.append("")
        L.append("A REAL press (tools/altirra_realstick.cmd: the arrow keys posted to Altirra's window, nothing written to STICK0):")
        L.extend(lines(real_logs, "tools/altirra_realstick.cmd")[0])
    n, bad, kinds, both = contacts(contact_logs)
    L.append("")
    L.append("Contact test in the real game (tools/run_input_audit.ps1; %d logs): %d passes, %d disagree with the model; outcomes: %s; passes with a ghost's bit set in both registers: %d" % (len(contact_logs), n, len(bad), ", ".join("%s %d" % kv for kv in sorted(kinds.items())), both))
    return L


def main():
    if "--evidence" in sys.argv:
        paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
        L = evidence([p for p in paths if os.path.basename(p).startswith("stick")], [p for p in paths if os.path.basename(p).startswith("contact")], [p for p in paths if os.path.basename(p).startswith("realstick")])
        txt = chr(10).join(L) + chr(10)
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
        print(txt)
        return
    if "--contacts" in sys.argv:
        paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
        n, bad, kinds, both = contacts(paths)
        L = ["Contact test of the real game against tools/input_model.py (tools/run_input_audit.ps1; %d logs): %d passes of `$A84D-$A883`, %d disagree with the model" % (len(paths), n, len(bad)),
             "outcomes: " + ", ".join("%s %d" % kv for kv in sorted(kinds.items())) + "; passes in which at least one ghost's bit was set in both registers: %d" % both]
        for b in bad[:5]:
            L.append("MISMATCH %s: %r got %r want %r" % b)
        txt = chr(10).join(L) + chr(10)
        if "--write" in sys.argv:
            with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
                fh.write(txt)
        print(txt)
        return
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
    L, st = lines(paths)
    txt = chr(10).join(L) + chr(10)
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
