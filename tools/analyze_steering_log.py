"""Step C11, frightened steering / eaten return / ghost house: check the log of tools\\altirra_steering.cmd against the rules read from the code.

SteerToTarget ($B999) rule (exact, from the ROM bytes; tests/test_frightened_house.py):
  vertical want   V: y = ty -> 0;  y > ty -> up (1) for a normal ghost, down (2) for a frightened one;  y < ty -> down (2) / up (1)
  horizontal want H: x = tx -> 0;  x > tx -> left (4) / right (8);                                        x < tx -> right (8) / left (4)
  mask M = the exits of the junction after the no-reverse filter (zp_2A);  RANDOM is the only random input.
  V available (V & M) and H available -> V or H (RANDOM bit 7 decides); V available only -> V; H available only -> H;
  neither -> the lowest set bit of (RANDOM & M), or of M if that is 0 (a random exit); M = 0 -> right (8).
  Special squares (x = $76 or $82, y = $64, beside the door): normal ghosts lose the 'up' exit (M & $0E); frightened ghosts get M = 1 (up only).
Usage: python -I tools\\analyze_steering_log.py F:\\Ports\\steering.txt [--summary-file analysis\\evidence-frightened-house-summary.txt]
"""
import collections
import re
import sys

STEER = re.compile(r"STEER ghost=(\d) state=\$([0-9A-F]{2}) x=(\d+) y=(\d+) tx=(\d+) ty=(\d+) mask=\$([0-9A-F]{2}) dir=(\d+) pacx=(\d+) pacy=(\d+) frame=(\d+)")
OUT = re.compile(r"STEER_OUT ghost=(\d) dir=(\d+) wv=(\d+) wh=(\d+)")
HOUSE = re.compile(r"HOUSE kind=(\w+) ghost=(\d) state=\$([0-9A-F]{2}) x=(\d+) y=(\d+) dir=(\d+) timer=(\d+) frame=(\d+)")
ST = re.compile(r"ST site=([0-9A-F]{4}) ghost=(\d) old=\$([0-9A-F]{2}) dots=(\d+) chase=(\d+) gtimer=(\d+) x=(\d+) y=(\d+) fright=(\d+) frame=(\d+)")
DIRN = {0: "-", 1: "up", 2: "down", 4: "left", 8: "right"}


def wants(frightened, x, y, tx, ty):
    if y == ty:
        v = 0
    elif y > ty:
        v = 2 if frightened else 1
    else:
        v = 1 if frightened else 2
    if x == tx:
        h = 0
    elif x > tx:
        h = 8 if frightened else 4
    else:
        h = 4 if frightened else 8
    return v, h


def allowed(v, h, m):
    """The set of directions the code can output."""
    if v and v & m:
        return {v, h} if h and h & m else {v}
    if h and h & m:
        return {h}
    if m == 0:
        return {8}
    return {b for b in (1, 2, 4, 8) if m & b}


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    steers, houses, sts = [], [], []
    pending = None
    for line in open(path, errors="replace"):
        m = STEER.search(line)
        if m:
            g, s, x, y, tx, ty, mk, d, px, py, fr = m.groups()
            pending = dict(g=int(g), state=int(s, 16), x=int(x), y=int(y), tx=int(tx), ty=int(ty), mask=int(mk, 16), dir=int(d), pacx=int(px), pacy=int(py), frame=int(fr))
            continue
        m = OUT.search(line)
        if m and pending and pending["g"] == int(m.group(1)):
            pending.update(out=int(m.group(2)), wv=int(m.group(3)), wh=int(m.group(4)))
            steers.append(pending)
            pending = None
            continue
        m = HOUSE.search(line)
        if m:
            k, g, s, x, y, d, t, fr = m.groups()
            houses.append(dict(kind=k, g=int(g), state=int(s, 16), x=int(x), y=int(y), dir=int(d), timer=int(t), frame=int(fr)))
            continue
        m = ST.search(line)
        if m:
            s, g, o, dots, c, gt, x, y, fr, fm = m.groups()
            sts.append(dict(site=int(s, 16), g=int(g), old=int(o, 16), x=int(x), y=int(y), frame=int(fm), gtimer=int(gt)))
    P("steering decisions logged:", len(steers), " house/eaten steps:", len(houses), " state writes:", len(sts))
    # ---------------------------------------------------------------- steering
    cls = collections.Counter()
    bad = []
    special_bad = []
    for r in steers:
        fright = bool(r["state"] & 0x80)
        kind = "frightened" if fright else ("eaten" if r["state"] & 0x40 else "normal")
        v, h = wants(fright, r["x"], r["y"], r["tx"], r["ty"])
        cls[kind] += 1
        if (v, h) != (r["wv"], r["wh"]):
            bad.append(("wanted directions differ from the rule", r, (v, h)))
            continue
        cls[kind + " wants == rule"] += 1
        al = allowed(v, h, r["mask"])
        if r["out"] not in al:
            bad.append(("chosen direction not allowed by the rule", r, sorted(al)))
            continue
        cls[kind + " choice allowed"] += 1
        if len(al) == 1:
            cls[kind + " choice forced (one candidate), equal"] += 1
        else:
            cls[kind + " random choice (%s)" % ("V or H" if v and h and v & r["mask"] and h & r["mask"] else "random exit")] += 1
        if (r["x"], r["y"]) in ((0x76, 0x64), (0x82, 0x64)):
            cls[kind + " at the door-side squares"] += 1
            ok = (r["mask"] & 0x01 == 0) if not fright else (r["mask"] == 0x01)
            if not ok:
                special_bad.append(r)
        # targets
        if fright and (r["state"] & 0x7F) in (0x02, 0x10, 0x20, 0x01, 0x08):
            cls["frightened target == Pac-Man"] += int((r["tx"], r["ty"]) == (r["pacx"], r["pacy"]))
            cls["frightened target != Pac-Man"] += int((r["tx"], r["ty"]) != (r["pacx"], r["pacy"]))
        if r["state"] == 0x42:
            cls["eaten target == door square (124,100)"] += int((r["tx"], r["ty"]) == (0x7C, 0x64))
            cls["eaten target != door square"] += int((r["tx"], r["ty"]) != (0x7C, 0x64))
        if r["state"] == 0x02:
            cls["chase target == Pac-Man"] += int((r["tx"], r["ty"]) == (r["pacx"], r["pacy"]))
            cls["chase target != Pac-Man"] += int((r["tx"], r["ty"]) != (r["pacx"], r["pacy"]))
    for k in sorted(cls):
        P("  %-58s %d" % (k, cls[k]))
    P("steering decisions that break the rule:", len(bad), "   door-side special squares that break it:", len(special_bad))
    for b in bad[:8]:
        P("   ", b)
    # fleeing: at a junction a frightened ghost with a free choice moves away from Pac-Man more often than toward
    away = toward = 0
    for r in steers:
        if r["state"] & 0x80 and r["state"] & 0x7F in (0x02, 0x10, 0x20, 0x08):
            d = r["out"]
            dx = r["x"] - r["pacx"]
            dy = r["y"] - r["pacy"]
            good = (d == 4 and dx < 0) or (d == 8 and dx > 0) or (d == 1 and dy < 0) or (d == 2 and dy > 0)      # moving away along an axis
            bad_ = (d == 4 and dx > 0) or (d == 8 and dx < 0) or (d == 1 and dy > 0) or (d == 2 and dy < 0)
            away += good
            toward += bad_
    P("frightened ghosts: choices that increase the distance along their axis:", away, " decrease it:", toward)
    # ---------------------------------------------------------------- the house and the return
    P()
    P("steps inside the house / eaten steps by kind and state:")
    c = collections.Counter((h["kind"], "$%02X" % h["state"]) for h in houses)
    for k, v in sorted(c.items()):
        P("  ", k, v)
    # eaten journeys: from A888 (eaten) to B764 (inside)
    P()
    P("eaten ghosts: frames from being eaten to the door square ($B6D0) and to the inside of the house ($B764):")
    journeys = []
    pend = {}
    for s in sts:
        if s["site"] == 0xA888:
            pend[s["g"]] = dict(eaten=s["frame"], at=(s["x"], s["y"]))
        elif s["site"] == 0xB6D0 and s["g"] in pend:
            pend[s["g"]]["door"] = s["frame"]
        elif s["site"] == 0xB764 and s["g"] in pend and "door" in pend[s["g"]]:
            j = pend.pop(s["g"])
            j["inside"] = s["frame"]
            j["g"] = s["g"]
            j["end"] = (s["x"], s["y"])
            journeys.append(j)
    for j in journeys[:12]:
        P("   ghost %d eaten at %s frame %d: door +%d, inside +%d (x,y inside %s)" % (j["g"], j["at"], j["eaten"], j["door"] - j["eaten"], j["inside"] - j["eaten"], j["end"]))
    n_eaten = sum(1 for s_ in sts if s_["site"] == 0xA888)
    P("   ghosts eaten:", n_eaten, "  reached the door:", len(journeys), "  (the others were eaten after frame 79,380, when a test-aid artefact had zeroed ReverseDir[1] and [2] in RAM -- see docs/18-frightened-eaten-house.md)")
    P("   journeys:", len(journeys), "  inside positions:", dict(collections.Counter((j["g"], j["end"]) for j in journeys)))
    # eaten steps near the door: dirs used inside the house after $44
    inside = collections.Counter((h["g"], h["state"], h["x"], h["y"], h["dir"]) for h in houses if h["kind"] == "walk" and h["state"] in (0x44, 0x04))
    P("   walking steps by (ghost, state, x, y, dir) for states $44 / $04, first 30 by count:")
    for k, v in inside.most_common(30):
        P("      ", k, v)
    # ---------------------------------------------------------------- release walk
    P()
    P("release walks (state 0, timer 0): steps and frames from the first walking step to the move into state 1 ($B756):")
    rel = []
    walks = collections.defaultdict(list)
    for h in houses:
        if h["kind"] == "walk" and h["state"] == 0:
            walks[h["g"]].append(h)
    for s in sts:
        if s["site"] == 0xB756 and s["old"] == 0:
            w = [h for h in walks[s["g"]] if h["frame"] <= s["frame"] and s["frame"] - h["frame"] < 400]
            # take the last continuous run ending at the release
            run = []
            for h in reversed(w):
                if run and run[-1]["frame"] - h["frame"] > 12:
                    break
                run.append(h)
            run.reverse()
            if run:
                rel.append((s["g"], run[0]["frame"], s["frame"], len(run), (run[0]["x"], run[0]["y"]), (run[-1]["x"], run[-1]["y"])))
    by_g = collections.defaultdict(list)
    for g, f0, f1, n, a, b in rel:
        by_g[g].append((f1 - f0, n, a, b))
    for g in sorted(by_g):
        v = by_g[g]
        P("   ghost %d: %d releases; frames walking %s; steps %s; from %s to %s" % (g, len(v), sorted(set(d for d, _, _, _ in v)), sorted(set(n for _, n, _, _ in v)),
                                                                              sorted(set(a for _, _, a, _ in v)), sorted(set(b for _, _, _, b in v))))
    # bobbing: y range while waiting, and the timer
    bob = [h for h in houses if h["kind"] == "bob"]
    P("bobbing steps:", len(bob), " y range per ghost:", {g: (min(h["y"] for h in bob if h["g"] == g), max(h["y"] for h in bob if h["g"] == g)) for g in range(1, 4) if any(h["g"] == g for h in bob)})
    dts = collections.Counter()
    last = {}
    for h in bob:
        if h["g"] in last and last[h["g"]]["timer"] != h["timer"] and h["frame"] - last[h["g"]]["frame"] < 20:
            dts[(last[h["g"]]["timer"] - h["timer"], h["frame"] - last[h["g"]]["frame"])] += 1
        last[h["g"]] = h
    P("bobbing: (timer decrease between consecutive bob steps, frames between them):", dict(dts.most_common(6)))
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad or special_bad else 0


if __name__ == "__main__":
    sys.exit(main())
