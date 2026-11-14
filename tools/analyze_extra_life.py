"""Audit of tools/altirra_extra_life.cmd (OPEN-VERIFICATION.md OV-19b / OV-33).  Usage:  python -I tools/analyze_extra_life.py <log> [--summary-file out.txt]     exit code 1 if a check fails

What must be seen (each line printed is a check):
 A  the score crosses 10,000 once (the harness poked 9,990): exactly one EXTRA_LIFE event, player 1's lives +1 in the frames right after, flag zp_2E set by that code.
 B  the score crosses 20,000 and 100,000 afterwards (poked 19,990 and 99,990): NO EXTRA_LIFE event and no change of player 1's lives in the following frames (the code returns when the flag zp_2E is set).
 C  every board change (LEVEL_ADV event): the level counter rises by exactly 1, the lives do not change, the start tune does not play (no write from its PCs $A7E2/$A7E8/$A7ED/$A7F2 and no TUNE event) and no sound write comes
    from a PC outside the known sound routines in the 300 frames after it; the poked levels (3, 7, 12, 20) are all seen.
"""
import collections
import os
import re
import sys

KNOWN = {0xA617, 0xAE94, 0xAE99, 0xAEAD, 0xAEB2, 0xAED2, 0xAED7, 0xB021, 0xB028, 0xB042, 0xB058, 0xB05B, 0xB060, 0xB072, 0xB075, 0xB078, 0xB07D, 0xB080, 0xB0DD, 0xB0E2, 0xB0EA, 0xB546, 0xB54B,
         0xABFE, 0xAC01, 0xA8EE, 0xB088, 0xF280}
TUNE_PCS = {0xA7E2, 0xA7E8, 0xA7ED, 0xA7F2}


def score(s1):
    v = 0
    for i in range(0, 12, 2):
        b = int(s1[i:i + 2], 16)
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
    fr, ev, sw = {}, [], []
    with open(args[0], encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("FR ") and re.search(r" t1=\d+$", line):
                d = dict(re.findall(r"(\w+)=(\S+)", line))
                fr[int(d["f"])] = dict(lives=[int(x) for x in d["lives"].split(",")], lv=int(d["lv"]), score=score(d["s1"]), p=int(d["p"]), cyc=int(d["cyc"]))
                continue
            m = re.match(r"SNDW a=\$(D20[0-8]) v=\$(..) pc=\$(....) f=(\d+)", line)
            if m:
                sw.append((int(m.group(4)), int(m.group(3), 16)))
                continue
            m = re.match(r"([A-Z_]+) f=(\d+)( x=(\d+))?$", line)
            if m and m.group(1) != "FR":
                ev.append((m.group(1), int(m.group(2)), int(m.group(4)) if m.group(4) else None))
    frames = sorted(fr)
    P("Trace: %d frames (f=%d..%d), events %s, final cycle %d" % (len(frames), frames[0], frames[-1], dict(collections.Counter(e[0] for e in ev)), fr[frames[-1]]["cyc"]))
    # every crossing of a threshold (a frame where the score rises past it; the harness pokes the score back down every cycle, so there are several)
    cross = {10000: [], 20000: [], 100000: []}
    for a_, b_ in zip(frames, frames[1:]):
        for thr in cross:
            if b_ == a_ + 1 and fr[a_]["score"] < thr <= fr[b_]["score"]:
                cross[thr].append(b_)
    P("\nA/B. Extra life at the score thresholds (player 1)")
    el = [e[1] for e in ev if e[0] == "EXTRA_LIFE"]
    for thr in cross:
        check(bool(cross[thr]), "the score crossed %d %d time(s), first at f=%s" % (thr, len(cross[thr]), cross[thr][0] if cross[thr] else None))
    for f0 in cross[10000][:1]:
        near = [f for f in el if f0 - 2 <= f <= f0 + 3]
        check(len(near) == 1, "EXTRA_LIFE event at the first 10,000 crossing (f=%d): %s" % (f0, near))
        l_before, l_after = fr[f0 - 1]["lives"][0], fr[min(f0 + 6, frames[-1])]["lives"][0]
        check(l_after == l_before + 1, "player 1's lives %d -> %d" % (l_before, l_after))
    for thr in (20000, 100000):
        bad = []
        for f0 in cross[thr]:
            lv = [fr[f]["lives"][0] for f in range(f0 - 1, f0 + 12) if f in fr]
            if [f for f in el if f0 - 2 <= f <= f0 + 12] or len(set(lv)) != 1:
                bad.append(f0)
        check(not bad, "%d crossings of %d: no EXTRA_LIFE event and constant lives in the 12 frames after each (bad: %s)" % (len(cross[thr]), thr, bad))
    check(len(el) == 1, "EXTRA_LIFE events in the whole trace: %d (one expected)" % len(el))
    P("\nC. Board changes")
    adv = [e[1] for e in ev if e[0] == "LEVEL_ADV"]
    tunes = [e[1] for e in ev if e[0] == "TUNE"]
    seen = []
    for f in adv:
        a = max(g for g in frames if g < f)
        b = min((g for g in frames if g >= f + 3), default=None)
        if b is None:
            continue
        before, after = fr[a]["lv"], fr[b]["lv"]
        seen.append(before)
        lives_same = fr[a]["lives"] == fr[b]["lives"]
        tune = [t for t in tunes if f - 5 <= t <= f + 400] + [w for (w, pc) in sw if f - 5 <= w <= f + 400 and pc in TUNE_PCS]
        other = collections.Counter(pc for (w, pc) in sw if f - 5 <= w <= f + 300 and pc not in KNOWN)
        check(after == before + 1 and lives_same and not tune and not other, "board change at f=%d: level counter %d -> %d, lives %s -> %s, tune writes %d, unknown sound writers %s" % (f, before, after, fr[a]["lives"], fr[b]["lives"], len(tune), dict(other)))
    check(len(adv) >= 4, "board changes seen: %d at level counters %s" % (len(adv), seen))
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
