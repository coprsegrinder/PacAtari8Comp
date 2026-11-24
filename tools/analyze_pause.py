"""Stage 53-56 / OV: the pause key (space bar, keyboard code $21) tested live - the one key of the key loop that was only read from the code.

Input: analysis/raw-logs/pause.txt of tools/altirra_pause.cmd (run with tools/run_patrol_trace.ps1 -Seconds 25), lines
  PV f= paused= rtclok= px= py= g=x0,x1,x2,x3,y0,y1,y2,y3 ch=      at every vertical blank (the deferred VBI handler entry $A5FD)
  KEY_TOGGLE f= new= old=                                         the key loop toggles `Paused` ($A4E2)
  PAUSED_FRAME f=                                                  the frame routine takes the pause exit ($A79C: `jmp ClearPokeyRegisters`)
Checks: two toggles (0 -> 1 at the first key, 1 -> 0 at the second); while paused (from the second paused frame on) no entity changes position and the jiffy clock goes on; every paused frame takes the pause exit;
after the resume the entities move again and the pause exit is not taken.
Usage: python -I tools/analyze_pause.py analysis/raw-logs/pause.txt [--write analysis/evidence-pause-summary.txt]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PV = re.compile(r"^PV f=(\d+) paused=(\d+) rtclok=(\d+) px=(\d+) py=(\d+) g=([\d,]+) ch=(\d+)")
TG = re.compile(r"^KEY_TOGGLE f=(\d+) new=(\d+) old=(\d+)")
PF = re.compile(r"^PAUSED_FRAME f=(\d+)")


def parse(path):
    pv, tg, pf = [], [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = PV.match(line)
            if m:
                pv.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), tuple(int(v) for v in m.group(6).split(",")), int(m.group(7))))
                continue
            m = TG.match(line)
            if m:
                tg.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
                continue
            m = PF.match(line)
            if m:
                pf.append(int(m.group(1)))
    return pv, tg, pf


def summarise(path):
    pv, tg, pf = parse(path)
    r = {"toggles": tg}
    first = [p for p in pv if p[1] == 1]
    r["paused_frames"] = len(first)
    if first:
        f0, f1 = first[0][0], first[-1][0]
        r["span"] = (f0, f1)
        body = first[1:]                                        # the frame in which the flag is set still moves things
        r["frozen"] = all((p[3], p[4], p[5]) == (body[0][3], body[0][4], body[0][5]) for p in body) if body else False
        r["clock_runs"] = all(b[2] == (a[2] + 1) & 0xFF for a, b in zip(first, first[1:]))
        r["exit_taken"] = sum(1 for f in pf if f0 <= f <= f1 + 1)
        after = [p for p in pv if p[0] > f1 + 1][:200]
        r["moves_after"] = any((a[3], a[4], a[5]) != (b[3], b[4], b[5]) for a, b in zip(after, after[1:]))
        before = [p for p in pv if p[0] < f0][-200:]
        r["moves_before"] = any((a[3], a[4], a[5]) != (b[3], b[4], b[5]) for a, b in zip(before, before[1:]))
        r["exit_outside"] = sum(1 for f in pf if not (f0 <= f <= f1 + 1))
    r["pf_total"] = len(pf)
    return r


def report(path):
    r = summarise(path)
    L = []
    P = L.append
    P("Pause key audit (tools/altirra_pause.cmd, tools/analyze_pause.py)")
    P("Key presses seen by the key loop (frame, Paused after, before): %s" % ", ".join("f=%d %d<-%d" % t for t in r["toggles"]))
    P("Paused frames: %d (frames %d-%d)" % (r["paused_frames"], r["span"][0], r["span"][1]))
    P("While paused, from the second paused frame: every entity keeps its position: %s; the jiffy clock goes on (+1 per frame): %s" % (r["frozen"], r["clock_runs"]))
    P("Frames that took the pause exit (jmp ClearPokeyRegisters at $A79C): %d inside the pause, %d outside it" % (r["exit_taken"], r["exit_outside"]))
    P("Entities moved in the 200 frames before the pause: %s; in the 200 frames after the resume: %s" % (r["moves_before"], r["moves_after"]))
    return L, r


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        args = [a for a in args if a != out]
    L, r = report(args[0])
    txt = "\n".join(L) + "\n"
    if out:
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
