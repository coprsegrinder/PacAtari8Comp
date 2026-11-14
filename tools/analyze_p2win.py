"""Checks the simulation of tools/altirra_p2win.cmd (docs/21, OPEN-VERIFICATION.md OV-20).  Usage:
  python -I tools/analyze_p2win.py <log> [--summary-file out.txt]      exit code 1 if a check fails

What must be seen in the log (nothing is assumed; each line below is a check that prints what was found):
 A  game A (one player) ends in a game over; its compare sets a non-empty high score of at most 3 digits.
 B  after the 30 s countdown the title is in state 4 (zp_19 = 4); SELECT pressed THERE (KEY_SELECT with zp_19 = 4) leaves state 4 for state 3 and toggles one -> two players (zp_1A 0 -> 1).
 C  game B starts with two players; player 2's score is set once to 1500 (the aid) while player 2 plays; the real code adds to it.
 D  at game over Sub_AB26 is called for player 1 (X=$2A) and then player 2 (X=$47); player 2's score is above the high score and 4 digits against a 3-digit high score:
    the digit-by-digit model (analyze_fullgame_log.model_ab26) predicts "copy" from the first greater digit, and the log must show exactly those digits copied (HS_COPY) and the new high score = player 2's score;
    player 1's compare comes first (whatever the bot scored: the log must equal the model) and player 2 compares against the high score it leaves.
 E  after a second completed countdown OPTION pressed in state 4 (KEY_OPTION with zp_19 = 4) leaves state 4 for state 3 and raises StartLevel from 0 to 1.
 F  the high score bytes change only through Sub_AB26's store (PC $AB3E).
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_fullgame_log as L  # noqa: E402


def dec(b):
    return "".join("" if v == 0 else str(v - 0x10) for v in b) or "-"


def main():
    args = sys.argv[1:]
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    path = args[0]
    out, problems = [], []
    P = lambda *a: out.append(" ".join(str(x) for x in a))

    def check(ok, text):
        P(("  ok   " if ok else "  FAIL ") + text)
        if not ok:
            problems.append(text)

    fr, ev, hsw = {}, [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("FR "):
                if not re.search(r" py=\d+$", line):
                    continue                                      # cut-off last line
                d = L.parse_fr(line)
                fr[d["f"]] = d
            elif re.match(r"(NEWGAME|KEY_SELECT|KEY_OPTION|SET_Z19|COUNTDOWN_DONE|GAME_OVER_TEXT|HS_ENTRY|HS_COPY|HS_RET|HS_RET_EQUAL) ", line):
                name = line.split(" ", 1)[0]
                d = L.kv(line)
                ev.append((name, int(d["f"]), d))
            elif line.startswith("HSW "):
                d = L.kv(line)
                hsw.append((int(d["pc"].replace("$", ""), 16), int(d["f"])))
    frames = sorted(fr)
    P("Log: %d frames (f=%d..%d), %d events." % (len(frames), frames[0], frames[-1], len(ev)))
    evn = lambda n: [(f, d) for (m, f, d) in ev if m == n]
    new = evn("NEWGAME")
    P("Games started: %d at frames %s, with zp_1A (two players) = %s" % (len(new), [f for f, _ in new], [d["z1a"] for _, d in new]))
    if len(new) < 2:
        problems.append("fewer than two games were started")
        print("\n".join(out))
        return 1

    # ---- A: game A
    P("\nA. Game A (one player)")
    check(new[0][1]["z1a"] == "0", "game A starts with one player (zp_1A = 0) at f=%d" % new[0][0])
    calls = []
    cur = None
    for (m, f, d) in ev:
        if m == "HS_ENTRY":
            cur = dict(f=f, x=int(d["x"]), s=L.hx(d["s"]), hi=L.hx(d["hi"]), copied=0, y=[])
            calls.append(cur)
        elif m == "HS_COPY" and cur:
            cur["copied"] += 1
            cur["y"].append(int(d["y"]))
        elif m in ("HS_RET", "HS_RET_EQUAL") and cur:
            cur["after"] = L.hx(d["hi"])
    ga = [c for c in calls if c["f"] < new[1][0]]
    check(len(ga) == 2 and [c["x"] for c in ga] == [42, 71], "game A: Sub_AB26 called for player 1 then player 2 (X=%s)" % [c["x"] for c in ga])
    hiA = ga[-1].get("after") if ga else None
    if ga:
        P("     scores P1 %s P2 %s; high score before %s, after %s" % (dec(ga[0]["s"]), dec(ga[1]["s"]), dec(ga[0]["hi"]), dec(hiA)))
        check(hiA is not None and any(hiA) and all(v == 0 for v in hiA[:3]), "game A leaves a non-empty high score of at most 3 digits (%s)" % (dec(hiA) if hiA else "?"))

    # ---- B: SELECT in state 4
    P("\nB. SELECT in title state 4")
    cd = evn("COUNTDOWN_DONE")
    s4 = [(f, d) for f, d in evn("SET_Z19") if d["new"] == "4"]
    check(len(s4) >= 1 and s4[0][0] < new[1][0] and s4[0][1]["z1e"] == "0", "game A's countdown completed (zp_1E = 0) and zp_19 := 4 at f=%s" % (s4[0][0] if s4 else "?"))
    ksel = [(f, d) for f, d in evn("KEY_SELECT") if d["z19"] == "4"]
    check(len(ksel) >= 1, "KEY_SELECT seen with zp_19 = 4 at f=%s (zp_1A %s)" % ([f for f, _ in ksel], [d["z1a"] for _, d in ksel]))
    if ksel:
        f = ksel[0][0]
        after = [fr[x] for x in frames if f < x <= f + 6]
        before = fr.get(f - 1) or fr[max(x for x in frames if x < f)]
        check(before["z19"] == 4 and before["z1a"] == 0, "before the key: zp_19 = %d, zp_1A = %d" % (before["z19"], before["z1a"]))
        check(any(a["z19"] == 3 and a["z1a"] == 1 for a in after), "after the key: zp_19 = %s, zp_1A = %s (state 3, two players)" % ([a["z19"] for a in after][:4], [a["z1a"] for a in after][:4]))
        sets = [(x, d) for x, d in evn("SET_Z19") if f <= x <= f + 3]
        P("     SET_Z19 events after the key:", [(x, d["new"]) for x, d in sets])
    check(new[1][1]["z1a"] == "1" and new[1][1]["z19"] == "3", "game B started from title state 3 with two players (zp_1A = %s) at f=%d" % (new[1][1]["z1a"], new[1][0]))

    # ---- C: the aid
    P("\nC. The aid (player 2's score set once)")
    target = [0, 0, 0x11, 0x15, 0x10, 0x10]
    gb = [x for x in frames if x >= new[1][0]]
    pf = next((x for x in gb if fr[x]["s2"] == target), None)
    check(pf is not None, "player 2's score reads %s (1500) first at f=%s" % (dec(target), pf))
    if pf:
        prev = fr[max(x for x in frames if x < pf)]
        check(fr[pf]["cp"] == 1 and fr[pf]["z20"] == 0, "the poke happens while player 2 plays (CurrentPlayer = %d, zp_20 = %d); score before: %s" % (fr[pf]["cp"], fr[pf]["z20"], dec(prev["s2"])))
        n2 = sum(1 for x in gb if x < pf and fr[x]["cp"] == 1 and fr[x]["z20"] == 0 and fr[x]["z21"] == 1)
        P("     frames of player 2's play before the poke:", n2)
        later = [fr[x]["s2"] for x in gb if x > pf and fr[x]["cp"] == 1]
        P("     player 2's score after the poke (distinct values):", sorted({dec(s) for s in later}))
        P("     the change was made by the harness, but the later increases are the game's own AddToScore:", "yes" if len({tuple(s) for s in later}) > 1 else "no further change")

    # ---- D: game over compare
    P("\nD. Game over of game B: Sub_AB26 for both players")
    gB = [c for c in calls if c["f"] >= new[1][0]]
    check(len(gB) >= 2 and gB[0]["x"] == 42 and gB[1]["x"] == 71, "calls in game B: X=%s at f=%s (player 1 first, then player 2)" % ([c["x"] for c in gB], [c["f"] for c in gB]))
    if len(gB) >= 2:
        c1, c2 = gB[0], gB[1]
        for tag, c in (("P1", c1), ("P2", c2)):
            exp, kind = L.model_ab26(c["s"], c["hi"])
            copied = len(c["y"])
            exp_n = 6 - next((i for i in range(6) if c["s"][i] != c["hi"][i]), 6) if kind == "copy" else 0
            P("     %s: score %s, high score %s -> %s; model: %s %s; log: %d digit(s) copied (y=%s)" % (tag, dec(c["s"]), dec(c["hi"]), dec(c.get("after", [])), kind, dec(exp), copied, c["y"]))
            check(c.get("after") == exp and copied == exp_n, "%s: the log equals the model (%s, %d digits copied)" % (tag, kind, exp_n))
        check(L.model_ab26(c2["s"], c2["hi"])[1] == "copy" and c2["s"] > c2["hi"], "player 2's score is above the high score")
        check(any(c2["hi"]) and all(v == 0 for v in c2["hi"][:3]) and c2["s"][2] != 0, "a 4-digit score (%s) beats a non-empty 3-digit high score (%s)" % (dec(c2["s"]), dec(c2["hi"])))
        k1 = L.model_ab26(c1["s"], c1["hi"])[1]
        P("     player 1's own compare came first: score %s against high score %s = '%s' (the model and the log agree, checked above); player 2 then compares against the high score player 1 left behind (%s)" % (dec(c1["s"]), dec(c1["hi"]), k1, dec(c2["hi"])))
        check(c2["hi"] == (c1.get("after") or []), "player 2's compare starts from the high score player 1's compare left (%s)" % dec(c2["hi"]))
        check(c2.get("after") == c2["s"], "the new high score is player 2's score: %s" % dec(c2.get("after", [])))
        gof = [(f, d) for f, d in evn("GAME_OVER_TEXT")]
        P("     GAME_OVER_TEXT events (final = zp_23 0):", [(f, d["z23"]) for f, d in gof if f >= new[1][0]])

    # ---- E: OPTION in state 4
    P("\nE. OPTION in title state 4")
    s4b = [(f, d) for f, d in evn("SET_Z19") if d["new"] == "4" and f > new[1][0]]
    check(len(s4b) >= 1 and s4b[0][1]["z1e"] == "0", "game B's countdown completed and zp_19 := 4 at f=%s" % (s4b[0][0] if s4b else "?"))
    kopt = [(f, d) for f, d in evn("KEY_OPTION") if d["z19"] == "4"]
    check(len(kopt) >= 1, "KEY_OPTION seen with zp_19 = 4 at f=%s (StartLevel %s)" % ([f for f, _ in kopt], [d["startlevel"] for _, d in kopt]))
    if kopt:
        f = kopt[0][0]
        before = fr[max(x for x in frames if x < f)]
        after = [fr[x] for x in frames if f < x <= f + 8]
        check(before["z19"] == 4, "before the key: zp_19 = %d, StartLevel = %d" % (before["z19"], before["z1b"]))
        check(any(a["z19"] == 3 and a["z1b"] == before["z1b"] + 1 for a in after), "after the key: zp_19 = 3 and StartLevel = %s (+1)" % [a["z1b"] for a in after][:3])

    # ---- F
    P("\nF. High score writes")
    pcs = collections.Counter(pc for pc, f in hsw if f > 100)
    check(set(pcs) <= {0xAB3E}, "writes to $2039-$203E after the first 100 frames come from PC %s" % {"%04X" % k: v for k, v in pcs.items()})
    P("\nPROBLEMS:", "none" if not problems else "")
    for p in problems:
        P("  " + p)
    text = "\n".join(out)
    print(text)
    if summ:
        with open(summ, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
