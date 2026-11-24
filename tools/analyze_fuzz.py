"""OV-64: the cost of adversarial play frames (tools/altirra_fuzz.cmd, run with tools/run_mainloop_audit.ps1 -Only fuzz -Cycles): the elapsed machine cycles from the entry of the handler to its jump to XITVBV, per frame class, against the
window the handler has: from its entry (line 256) to the next vertical-blank interrupt (line 248 of the next frame, 8 lines before the next entry).
Usage: python -I tools/analyze_fuzz.py analysis/raw-logs/fuzzmainloop-fuzz.txt [--write analysis/evidence-fuzz-summary.txt]"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import analyze_mainloop as M  # noqa: E402

FRAME = 262 * 114
WINDOW = FRAME - 8 * 114                     # entry at line 256, the next interrupt at line 248 of the next frame


def lines(paths):
    L = []
    for p in paths:
        fr = [r for r in M.parse(p) if r["f"] > 36 and r["vxc"] is not None]
        by = {}
        for r in fr:
            by.setdefault(r["class"], []).append(r["vxc"])
        L.append("Adversarial play frames (%s): %d frames; the handler's window is %d cycles (entry to the next interrupt; a frame is %d)" % (os.path.basename(p), len(fr), WINDOW, FRAME))
        L.append("class | frames | median / 99.9th percentile / maximum elapsed cycles | cycles left in the window at the maximum")
        for name, _ in M.CLASSES:
            v = by.get(name)
            if not v:
                continue
            v = sorted(v)
            L.append("%-20s %7d | %6d / %6d / %6d | %d" % (name, len(v), v[len(v) // 2], v[min(len(v) - 1, int(len(v) * 0.999))], v[-1], WINDOW - v[-1]))
        play = sorted(by.get("play", []))
        if play:
            top = Counter(play[-50:])
            L.append("the 10 heaviest play frames: " + " ".join(str(x) for x in play[-10:]))
    return L


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
    txt = chr(10).join(lines(paths)) + chr(10)
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
