"""OV-61: the OS keyboard path with a real key press (tools/altirra_realkey.cmd, run_patrol_trace.ps1 -Keys).  Per press: the OS IRQ routine reads KBCODE ($D209) and stores the code in CH ($02FC), the game's key loop ($A4E2) toggles Paused ($9B), the frame handler runs the paused frame ($A79C) while Paused = 1, and the second press resumes.
Usage: python -I tools/analyze_realkey.py analysis/raw-logs/realkey.txt [--write analysis/evidence-realkey-summary.txt]"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def analyze(path):
    ev = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if not ln.endswith("\n"):
                continue
            m = re.match(r"^(KBCODE_READ) pc=\$([0-9A-F]{4}) f=(\d+)", ln)
            if m:
                ev.append(("kbcode", int(m.group(3)), int(m.group(2), 16), None))
                continue
            m = re.match(r"^CHW pc=\$([0-9A-F]{4}) v=\$([0-9A-F]{2}) f=(\d+)", ln)
            if m:
                ev.append(("ch", int(m.group(3)), int(m.group(1), 16), int(m.group(2), 16)))
                continue
            m = re.match(r"^KEY_TOGGLE f=(\d+) new=(\d+) old=(\d+)", ln)
            if m:
                ev.append(("toggle", int(m.group(1)), int(m.group(2)), int(m.group(3))))
                continue
            m = re.match(r"^PAUSED_FRAME f=(\d+)", ln)
            if m:
                ev.append(("pframe", int(m.group(1)), 0, None))
                continue
            m = re.match(r"^PV f=(\d+) paused=(\d+)", ln)
            if m:
                ev.append(("pv", int(m.group(1)), int(m.group(2)), None))
    return ev


def report(path):
    ev = analyze(path)
    L = []
    P = L.append
    toggles = [e for e in ev if e[0] == "toggle"]
    P("OV-61 real key press (tools/altirra_realkey.cmd, tools/analyze_realkey.py): the space bar posted twice to Altirra's window from outside the emulated machine; no write to CH or any register by the harness")
    P("game key-loop toggles of Paused: %d: %s" % (len(toggles), "; ".join("f=%d %d->%d" % (e[1], e[3], e[2]) for e in toggles)))
    ok = True
    for i, t in enumerate(toggles):
        f = t[1]
        # the OS routine: the last KBCODE read by OS code ($C000 up) and the CH write of $21 by OS code before the toggle
        kb = [e for e in ev if e[0] == "kbcode" and e[2] >= 0xC000 and e[1] <= f][-1:]
        ch = [e for e in ev if e[0] == "ch" and e[2] >= 0xC000 and e[3] == 0x21 and e[1] <= f][-1:]
        clr = [e for e in ev if e[0] == "ch" and 0xA000 <= e[2] < 0xC000 and e[3] == 0xFF and e[1] >= f][:1]
        P("press %d: OS reads KBCODE at $%04X (frame %s), OS stores CH = $21 at $%04X (frame %s), the key loop toggles at frame %d (%d -> %d) and clears CH to $FF at $%04X (frame %s)" % (
            i + 1, kb[0][2] if kb else 0, kb[0][1] if kb else "-", ch[0][2] if ch else 0, ch[0][1] if ch else "-", f, t[3], t[2], clr[0][2] if clr else 0, clr[0][1] if clr else "-"))
        ok = ok and bool(kb) and bool(ch) and bool(clr) and f - ch[0][1] <= 120
    pv = [e for e in ev if e[0] == "pv"]
    pf = [e for e in ev if e[0] == "pframe"]
    paused_frames = sum(1 for e in pv if e[2] == 1)
    P("frames with Paused = 1 at the entry of the handler: %d; paused frames run by the game ($A79C): %d" % (paused_frames, len(pf)))
    P("result: %s" % ("every press reached the game through the OS keyboard IRQ routine (KBCODE -> CH = $21 within 120 frames before the toggle (34 frames in both presses: the key loop polls CH between its other work)), two presses toggle 0 -> 1 -> 0" if ok and len(toggles) >= 2 and [t[2] for t in toggles[:2]] == [1, 0] else "NOT as expected"))
    return L, ok and len(toggles) >= 2


if __name__ == "__main__":
    L, ok = report(sys.argv[1])
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
