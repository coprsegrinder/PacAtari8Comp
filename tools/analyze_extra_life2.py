"""Audit of tools/altirra_extra_life2.cmd (OPEN-VERIFICATION.md OV-45).  Usage:  python -I tools/analyze_extra_life2.py <log> [--summary-file out.txt]     exit code 1 if a check fails

Checks (each line printed is one):
 N  every NEWGAME: the flags zp_2E/zp_2F are 0 in the first frames after it (the $20-$3F clear), whatever they were before.
 A  g=1 and g=2 (one player): the score of player 1 crosses 10,000 once per game: one EXTRA_LIFE event (cur=0), lives of player 1 +1, flag zp_2E = 1 afterwards.  The award in g=2 is the 'new game after the flag' case.
 B  g=3 and g=4 (two players), player 2 playing: crossings of 10,000 give exactly one EXTRA_LIFE (cur=1, lives[1] +1, zp_2F set) per game; crossings of 20,000 and 100,000 afterwards give none and lives[1] stays constant.
"""
import collections
import re
import sys


def score(s):
    v = 0
    for i in range(0, 12, 2):
        b = int(s[i:i + 2], 16)
        v = v * 10 + (b - 0x10 if 0x10 <= b <= 0x19 else 0)
    return v


def main():
    args = sys.argv[1:]
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    out, problems = [], []
    P = lambda *a: out.append(" ".join(str(x) for x in a))

    def check(ok, text):
        P(("  ok   " if ok else "  FAIL ") + text)
        if not ok:
            problems.append(text)
    fr, ev = {}, []
    with open(args[0], encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("FR "):
                d = dict(re.findall(r"(\w+)=(\S+)", line))
                if "p9" not in d:
                    continue
                fr[int(d["f"])] = dict(g=int(d["g"]), cur=int(d["cur"]), lives=[int(x) for x in d["lives"].split(",")], fl=[int(x) for x in d["fl"].split(",")],
                                       s1=score(d["s1"]), s2=score(d["s2"]), z19=int(d["z19"]), z1a=int(d["z1a"]))
                continue
            m = re.match(r"([A-Z_]+) f=(\d+) g=(\d+)(.*)$", line)
            if m:
                d = dict(re.findall(r"(\w+)=(\S+)", m.group(4)))
                ev.append((m.group(1), int(m.group(2)), int(m.group(3)), d))
    frames = sorted(fr)
    P("Trace: %d frames (f=%d..%d), events %s, games started %d" % (len(frames), frames[0], frames[-1], dict(collections.Counter(e[0] for e in ev)), max(v["g"] for v in fr.values())))
    P("\nN. New game clears the flags")
    prev = None
    for name, f, g, d in ev:
        if name != "NEWGAME":
            continue
        before = fr[max(x for x in frames if x < f)]["fl"] if any(x < f for x in frames) else None
        after = [fr[x]["fl"] for x in frames if f + 2 <= x <= f + 6]
        check(bool(after) and all(a == [0, 0] for a in after), "NEWGAME g=%d f=%d: flags before %s, after %s" % (g, f, before, after[:1]))
    els = [e for e in ev if e[0] == "EXTRA_LIFE"]
    P("\nEXTRA_LIFE events: %s" % [(e[1], "g=%d" % e[2], "cur=%s" % e[3]["cur"], "lives=%s" % e[3]["lives"]) for e in els])
    P("\nA. One player (g=1, g=2)")
    for g in (1, 2):
        fg = [f for f in frames if fr[f]["g"] == g and fr[f]["z1a"] == 0]
        cross = [b for a, b in zip(fg, fg[1:]) if b == a + 1 and fr[a]["s1"] < 10000 <= fr[b]["s1"]]
        e = [x for x in els if x[2] == g]
        check(len(cross) >= 1, "g=%d: player 1's score crossed 10,000 %d time(s)" % (g, len(cross)))
        check(len(e) == 1 and e[0][3]["cur"] == "0", "g=%d: EXTRA_LIFE events: %d (one expected, player 1)" % (g, len(e)))
        if e and cross:
            f0 = e[0][1]
            l0 = fr[max(x for x in frames if x < f0 - 1)]["lives"][0]
            l1 = fr[min(x for x in frames if x >= f0 + 6)]["lives"][0]
            fl = fr[min(x for x in frames if x >= f0 + 6)]["fl"]
            check(l1 == l0 + 1 and fl[0] == 1, "g=%d: player 1's lives %d -> %d, flags after %s" % (g, l0, l1, fl))
    P("\nB. Two players, player 2 (g=3, g=4)")
    for g in (3, 4):
        fg = [f for f in frames if fr[f]["g"] == g]
        if not fg:
            check(False, "g=%d never started" % g)
            continue
        e = [x for x in els if x[2] == g]
        for thr in (10000, 20000, 100000):
            cr = [b for a, b in zip(fg, fg[1:]) if b == a + 1 and fr[a]["s2"] < thr <= fr[b]["s2"]]
            if thr == 10000:
                P("  g=%d: player 2's score crossed 10,000 at %s" % (g, cr))
                check(len(cr) >= 1, "g=%d: player 2 crossed 10,000" % g)
                p2 = [x for x in e if x[3]["cur"] == "1"]
                check(len(p2) == 1 and len(e) == len(p2), "g=%d: EXTRA_LIFE events %d, all for player 2, exactly one" % (g, len(e)))
                if p2:
                    f0 = p2[0][1]
                    a = fr[max(x for x in frames if x < f0 - 1)]
                    b = fr[min(x for x in frames if x >= f0 + 6)]
                    check(b["lives"][1] == a["lives"][1] + 1 and b["lives"][0] == a["lives"][0] and b["fl"] == [a["fl"][0], 1], "g=%d: lives %s -> %s, flags %s -> %s" % (g, a["lives"], b["lives"], a["fl"], b["fl"]))
            else:
                bad = []
                for f0 in cr:
                    lv = [fr[f]["lives"][1] for f in range(f0 - 1, f0 + 12) if f in fr and fr[f]["cur"] == 1]
                    if [x for x in e if f0 - 2 <= x[1] <= f0 + 12] or len(set(lv)) > 1:
                        bad.append(f0)
                check(not bad, "g=%d: %d crossing(s) of %d by player 2 (at %s): no award and constant lives (bad %s)" % (g, len(cr), thr, cr, bad))
                check(len(cr) >= 1, "g=%d: threshold %d was reached" % (g, thr))
    P("\nPROBLEMS: " + ("none" if not problems else ""))
    for t in problems:
        P("  " + t)
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
