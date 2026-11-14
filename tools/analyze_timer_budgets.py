"""OV-30: the length of the ghost time budgets in frames and in emulated seconds, measured on the log of tools\\altirra_transitions.cmd.

The code decrements GhostTimer (per ghost, $CA+x) and ChaseTimer (one byte for all four ghosts, $AD) once every 8th jiffy (`RTCLOK2 AND 7 = 0`, $A9DD / $B5C7), so a timer set to N runs out after
8*N - 7 .. 8*N frames, depending on the phase of RTCLOK2 at the moment it was set.  The log has one line per store to GhostState (site, ghost, old state, ChaseTimer, GhostTimer of that ghost, frame).
Checks:
  1. The decrement period: in every stretch where the ChaseTimer only falls (no reset), the line (frame, value) has slope -1/8 per frame, the values all lie within one step of the straight line.
     Same for the GhostTimer of each ghost.
  2. The budgets: for every time-up store ($B8C7 with old state $08 / $10 / $02) the frames since the last store that set the timer ($B853 for GhostTimer := $96 of that ghost; $BAB9 sighting
     ChaseTimer := $A0, $B8ED ghost 0 start ChaseTimer := $50 for the ChaseTimer) must lie in 8*N-7 .. 8*N (+ a margin for the steps of the ghost routine that stores the new state, 0-4 frames).
  3. The time in seconds: frames / FRAME_HZ of the machine (tools/video.py: NTSC 59.9227 Hz, PAL 49.86 Hz).
Usage: python -I tools\\analyze_timer_budgets.py analysis\\raw-logs\\transitions.txt [--summary-file out.txt]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LINE = re.compile(r"ST site=([0-9A-F]{4}) ghost=(\d) old=\$([0-9A-F]{2}) dots=(\d+) chase=(\d+) gtimer=(\d+) x=(\d+) y=(\d+) fright=(\d+) frame=(\d+)")
MARGIN = 4          # frames between the timer reaching 0 and the ghost routine storing the new state (the routine runs once per ghost step, not every frame)
NTSC_HZ = 315e6 / 88 / 2 / (262 * 114)
PAL_HZ = 1773447.0 / (312 * 114)


def parse(path):
    rows = []
    for l in open(path, errors="replace"):
        m = LINE.match(l)
        if m:
            s, g, o, d, c, t, x, y, fr, f = m.groups()
            rows.append(dict(f=int(f), site=s, g=int(g), old=int(o, 16), dots=int(d), chase=int(c), gt=int(t), fright=int(fr)))
    return rows


SETTERS = {"BAB9", "B8ED", "B626", "B74C", "AFA0"}      # state stores next to a write of ChaseTimer: sighting $BABD ($A0), ghost 0 start route end $B84C ($50), late board $B616 ($FF), a frightened ghost leaving the house $B74C ($82), end of the frightened time $AFAF ($A0)
FREEZE = (20, 45)                                # frames missing after a ghost is eaten ($A888): the game stands still for about 32 frames (measured below)


def classify_pairs(rows):
    """Every pair of consecutive log frames, by what happened to the ChaseTimer between them (one class per pair).  The decrement is 1 per 8 frames (RTCLOK2 AND 7 = 0), so with
    gap = frames - 8 * fall the pair is 'ok' when |gap| <= 8 (the phase of RTCLOK2 at the two samples allows +-7)."""
    bf = collections.defaultdict(list)
    for r in rows:
        bf[r["f"]].append(r)
    fs = sorted(bf)
    cls = collections.Counter()
    freeze_gaps, unexplained = [], []
    last_eat = -10 ** 9
    for f1, f2 in zip(fs, fs[1:]):
        if "A888" in set(r["site"] for r in bf[f1]):
            last_eat = f1
        v1, v2 = bf[f1][-1]["chase"], bf[f2][0]["chase"]
        s1, s2 = set(r["site"] for r in bf[f1]), set(r["site"] for r in bf[f2])
        gap = (f2 - f1) - 8 * (v1 - v2)
        if v1 == 0 and v2 == 0:
            cls["timer at 0 (stays 0)"] += 1
        elif v1 >= 0xF0 and v2 >= 0xF0:
            cls["permanent chase ($FF, late board)"] += 1
        elif v2 > v1 or (s1 | s2) & SETTERS or "A800" in s2:
            cls["reset (a setter store, a rise, or a board start $A800)"] += 1
        elif v2 == 0 and 8 * v1 - 7 <= (f2 - f1) + 40:
            cls["reached 0 between the two frames"] += 1
        elif abs(gap) <= 8:
            cls["ok: 1 step per 8 frames"] += 1
        elif f1 - last_eat <= 35 and FREEZE[0] <= gap <= FREEZE[1]:        # the pair starts at the eating or inside its freeze
            cls["ghost-eaten freeze (no decrement for ~32 frames)"] += 1
            freeze_gaps.append(gap)
        else:
            cls["unexplained"] += 1
            unexplained.append((f1, f2, v1, v2, gap, sorted(s1), sorted(s2)))
    return cls, freeze_gaps, unexplained


def analyse(rows):
    out = {}
    out["pairs"] = classify_pairs(rows)
    # budgets: frames from the store that set a timer to the store that ends the state
    last_patrol = {}
    budgets = {"patrol": [], "travel": [], "chase": []}
    for r in rows:
        if r["site"] == "B853":
            last_patrol[r["g"]] = r["f"]
        elif r["site"] == "B8C7" and r["old"] in (0x08, 0x10) and r["g"] in last_patrol:
            budgets["patrol" if r["old"] == 0x10 else "travel"].append((r["g"], r["f"] - last_patrol[r["g"]]))
            del last_patrol[r["g"]]
    # ChaseTimer: (1) the value right after each store that sets it ($BAB9 sighting $A0, $B8ED ghost 0 start route end $50) against the value written; (2) the value at every chase time-up
    chase_set, chase_up = [], []
    for i, r in enumerate(rows):
        if r["site"] in ("BAB9", "B8ED"):
            want = 0xA0 if r["site"] == "BAB9" else 0x50
            nxt = next((q for q in rows[i + 1:i + 40] if q["f"] > r["f"]), None)
            if nxt and nxt["f"] - r["f"] <= 60 and nxt["chase"] <= 0xA0 and nxt["site"] not in ("B626",):
                chase_set.append((r["site"], want, nxt["f"] - r["f"], nxt["chase"]))
        elif r["site"] == "B8C7" and r["old"] == 0x02:
            chase_up.append((r["g"], r["f"], r["chase"]))
    out["budgets"] = budgets
    out["chase_set"] = chase_set
    out["chase_up"] = chase_up
    return out


def report(rows, res):
    L = []
    P = L.append
    problems = []
    P("Log: %d state stores, frames %d..%d." % (len(rows), rows[0]["f"], rows[-1]["f"]))
    cls, fg, un = res["pairs"]
    P("")
    P("ChaseTimer between consecutive log frames (%d pairs):" % sum(cls.values()))
    for k, v in cls.most_common():
        P("  %6d  %s" % (v, k))
    if fg:
        P("  ghost-eaten freeze: %d cases, %d..%d frames missing (mean %.1f; the phase of RTCLOK2 allows +-7)" % (len(fg), min(fg), max(fg), sum(fg) / len(fg)))
    if un:
        P("  unexplained pairs (frame, frame, value, value, gap, sites):")
        for x in un[:12]:
            P("    %s" % (x,))
        problems.append("%d unexplained ChaseTimer pairs" % len(un))
    P("")
    P("Budgets (frames from the store that set the timer to the store that ends the state; allowed 8*N-7 .. 8*N + %d; the game decrements only when it runs, so a ghost-eaten freeze would add ~32):" % MARGIN)
    for name in ("patrol", "travel"):
        v = [x[1] for x in res["budgets"][name]]
        lo, hi = 8 * 0x96 - 8, 8 * 0x96 + MARGIN
        bad = [x for x in v if not lo <= x <= hi]
        P("  %-7s ($B8C7, old $%s, GhostTimer $96 = 150 steps): %d cases, frames %s, allowed %d..%d, outside: %d" %
          (name, "10" if name == "patrol" else "08", len(v), (min(v), max(v)) if v else "-", lo, hi, len(bad)))
        if bad:
            problems.append("%s budget outside" % name)
    cs = res["chase_set"]
    for site, want in (("BAB9", 0xA0), ("B8ED", 0x50)):
        v = [x for x in cs if x[0] == site]
        if not v:
            continue
        bad = [x for x in v if abs((want - x[3]) - x[2] / 8) > 1.0]
        P("  ChaseTimer right after $%s: %d cases, value written $%02X (%d steps = %d frames); value seen after 0..%d frames: %d of %d within one step of $%02X - frames/8" %
          (site, len(v), want, want, 8 * want, max(x[2] for x in v), len(v) - len(bad), len(v), want))
        if bad:
            problems.append("ChaseTimer after $%s differs from the value written" % site)
    cu = res["chase_up"]
    nz = [x for x in cu if x[2] != 0]
    P("  chase time-ups ($B8C7, old $02): %d, ChaseTimer = 0 in %d of them" % (len(cu), len(cu) - len(nz)))
    if nz:
        problems.append("a chase time-up with ChaseTimer <> 0")
    P("")
    P("In seconds (frames / frame rate of the machine): $96 = 1,200 frames = %.2f s NTSC (%.4f Hz), %.2f s PAL (%.4f Hz);  $A0 = 1,280 frames = %.2f s / %.2f s;  $50 = 640 frames = %.2f s / %.2f s." %
      (1200 / NTSC_HZ, NTSC_HZ, 1200 / PAL_HZ, PAL_HZ, 1280 / NTSC_HZ, 1280 / PAL_HZ, 640 / NTSC_HZ, 640 / PAL_HZ))
    P("")
    P("PROBLEMS: " + ("none" if not problems else "; ".join(problems)))
    return L, problems


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    rows = parse(args[0])
    res = analyse(rows)
    L, problems = report(rows, res)
    txt = "\n".join(L)
    print(txt)
    if summ:
        open(summ, "w", encoding="utf-8").write(txt + "\n")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
