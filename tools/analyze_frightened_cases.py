"""OV-35: the frightened-ghost cases that were not provoked before, checked against the log of tools\\altirra_frightened_cases.cmd.

Kind 0 boards (power pellet 60-600 frames after the set-up): a ghost on its start route ($01) becomes $81.  Checked: what the ghost does while it is $81 (the start-route step counter StartRouteStep $D2+g must not move: the
  chase handler runs, not the start route), and how the $81 ends: the frightened time ends -> $20 (corner, $AF9E), or the ghost is eaten -> $42; no store of the start route's end ($B853 / $B8ED) happens to an $81 ghost.
Kind 1 boards (ghosts 1, 2 and Pac-Man put on ghost 0's square while they are frightened): ghosts eaten one after the other, never two in the same frame (the contact loop leaves through AddToScore after the first one),
  the GhostsEaten counter 0, 1, 2 (200, 400, 800 points), the spacing is the freeze of the pop-up.
Kind 2 boards (ghost 0 eaten, then Pac-Man stands on the door square (124,100) while the eyes come back): the eyes walk through Pac-Man, state $42 -> $44 at the door -> $04 inside, and the ghost is not eaten twice.
Usage: python -I tools\\analyze_frightened_cases.py analysis\\raw-logs\\frightened-cases.txt [--summary-file out.txt]
"""
import collections
import re
import sys

ST = re.compile(r"ST site=([0-9A-F]{4}) ghost=(\d) old=\$([0-9A-F]{2}) dots=(\d+) chase=(\d+) gtimer=(\d+) x=(\d+) y=(\d+) fright=(\d+) frame=(\d+)")
FR = re.compile(r"FR f=(\d+) b=(\d+) st=([0-9A-F]{2}),([0-9A-F]{2}),([0-9A-F]{2}),([0-9A-F]{2}) x=(\d+),(\d+),(\d+),(\d+) y=(\d+),(\d+),(\d+),(\d+) d=(\d+),(\d+),(\d+),(\d+) rs=(\d+),(\d+),(\d+),(\d+) p=(\d+),(\d+) ge=(\d+) e5=(\d+) fc=(\d+) fd=(\d+) t5=(-?\d+)")
EAT = re.compile(r"GHOST_EATEN ghost=(\d) eaten=(\d+) frame=(\d+)")
ENDS = re.compile(r"FRIGHT_ENDS ghost=(\d) state=\$([0-9A-F]{2}) frame=(\d+)")
INIT = re.compile(r"INIT_BOARD frame=(\d+) board=(\d+) level=(\d+)")


def parse(path):
    st, fr, eat, ends, boards = [], {}, [], [], []
    for l in open(path, errors="replace"):
        c = l[:2]
        if l.startswith("FRIGHT_ENDS"):
            m = ENDS.match(l)
            if m:
                ends.append((int(m.group(3)), int(m.group(1)), int(m.group(2), 16)))
        elif c == "FR":
            m = FR.match(l)
            if m:
                g = [int(v) if i not in (2, 3, 4, 5) else int(v, 16) for i, v in enumerate(m.groups())]
                fr[g[0]] = dict(f=g[0], b=g[1], st=g[2:6], x=g[6:10], y=g[10:14], d=g[14:18], rs=g[18:22], p=g[22:24], ge=g[24], e5=g[25], fc=g[26], fd=g[27], t5=g[28])
        elif c == "ST":
            m = ST.match(l)
            if m:
                g = m.groups()
                st.append(dict(site=g[0], g=int(g[1]), old=int(g[2], 16), x=int(g[6]), y=int(g[7]), f=int(g[9])))
        elif c == "GH":
            m = EAT.match(l)
            if m:
                eat.append((int(m.group(3)), int(m.group(1)), int(m.group(2))))
        elif l.startswith("INIT_BOARD"):
            m = INIT.match(l)
            if m:
                boards.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return st, fr, eat, ends, boards


def kind_of(board):
    return (board - 1) % 3


def run(path):
    st, fr, eat, ends, boards = parse(path)
    L = []
    P = L.append
    problems = []
    P("Log: %d state stores, %d frames, %d boards (kind 0: %d, kind 1: %d, kind 2: %d), %d ghosts eaten." %
      (len(st), len(fr), len(boards), sum(1 for b in boards if kind_of(b[1]) == 0), sum(1 for b in boards if kind_of(b[1]) == 1), sum(1 for b in boards if kind_of(b[1]) == 2), len(eat)))
    # ---- $81 ----
    P("")
    P("A. Frightened ghosts on the start route ($01 -> $81 at the pellet):")
    pel = [s for s in st if s["site"] == "B40A" and s["old"] == 0x01]
    P("  pellet stores with old state $01: %d (ghosts %s)" % (len(pel), dict(sorted(collections.Counter(s["g"] for s in pel).items()))))
    # episodes: for each ghost that was $81, follow the per-frame state
    frames = sorted(fr)
    by_f = fr
    ends_of = collections.Counter()
    moved, still = 0, 0
    rs_changed = 0
    n81 = 0
    fl_ends = []
    outcome = collections.Counter()
    seen = set()
    bad_next = []
    for i, f in enumerate(frames[:-1]):
        a, b = by_f[f], by_f.get(f + 1)
        if not b:
            continue
        for g in range(4):
            if a["st"][g] == 0x81 and b["st"][g] != 0x81:
                key = (a["b"], g, f)
                nxt = b["st"][g]
                outcome[("$81 -> $%02X" % nxt)] += 1
                if nxt not in (0x20, 0x42):
                    bad_next.append((f, g, nxt))
            if a["st"][g] == 0x81 and b["st"][g] == 0x81:
                n81 += 1
                if b["rs"][g] != a["rs"][g]:
                    rs_changed += 1
                if (b["x"][g], b["y"][g]) != (a["x"][g], a["y"][g]):
                    moved += 1
                else:
                    still += 1
    P("  frames in which a ghost held $81 (frame pairs): %d; the ghost moved in %d of them (half speed or frozen in the others); StartRouteStep changed in %d of them" % (n81, moved, rs_changed))
    P("  how the $81 ended: " + ", ".join("%s: %d" % (k, v) for k, v in sorted(outcome.items())))
    sites_81 = collections.Counter((s["site"], "$%02X" % s["old"]) for s in st if s["old"] == 0x81)
    P("  stores that replaced an $81 (site, old state): " + ", ".join("%s %s: %d" % (k[0], k[1], v) for k, v in sorted(sites_81.items())))
    route_end = [s for s in st if s["old"] == 0x81 and s["site"] in ("B853", "B8ED")]
    P("  start-route-end stores ($B853 / $B8ED) on an $81 ghost: %d" % len(route_end))
    if rs_changed:
        problems.append("StartRouteStep moved while $81")
    if route_end:
        problems.append("route end while $81")
    if bad_next:
        problems.append("$81 followed by %s" % bad_next[:3])
    for ends_f, g, state in ends:
        if state == 0x81:
            nf = [x for x in frames if x > ends_f][:3]
            nxt = by_f[nf[0]]["st"][g] if nf else None
            fl_ends.append(nxt)
    P("  the frightened time ended while a ghost held $81: %d times; that ghost's next logged state: %s" % (len(fl_ends), dict(collections.Counter("$%02X" % v for v in fl_ends))))
    if any(v != 0x20 for v in fl_ends):
        problems.append("$81 at the end of the frightened time is not followed by $20")
    # ---- two ghosts ----
    P("")
    P("B. Several ghosts touching Pac-Man at once (kind 1 boards, ghosts 1, 2 and Pac-Man put on ghost 0):")
    by_board = collections.defaultdict(list)
    for f, g, ge in eat:
        b = fr[f]["b"] if f in fr else None
        by_board[b].append((f, g, ge))
    k1 = {b: v for b, v in by_board.items() if b is not None and kind_of(b) == 1}
    same = sum(1 for v in k1.values() for (f1, *_), (f2, *_) in zip(v, v[1:]) if f1 == f2)
    gaps = [f2 - f1 for v in k1.values() for (f1, *_), (f2, *_) in zip(v, v[1:])]
    P("  boards with ghosts eaten: %d; ghosts eaten per board: %s; two ghosts eaten in the same frame: %d" % (len(k1), dict(sorted(collections.Counter(len(v) for v in k1.values()).items())), same))
    if gaps:
        P("  frames between two eatings on one board: min %d, max %d (the pop-up freeze); GhostsEaten counter at each eating: %s" % (min(gaps), max(gaps), dict(collections.Counter(tuple(x[2] for x in v) for v in k1.values()))))
    sim = 0
    for v in k1.values():
        f0 = v[0][0]
        a = fr.get(f0)                           # logged at the start of the frame, after the pokes of the frame before
        if a:
            n = sum(1 for g in range(4) if abs(a["x"][g] - a["p"][0]) <= 4 and abs(a["y"][g] - a["p"][1]) <= 4)
            if n >= 2:
                sim += 1
    P("  boards where at least two ghosts were within 4 pixels of Pac-Man in the frame of the first eating: %d of %d" % (sim, len(k1)))
    if same:
        problems.append("two eaten in one frame")
    if any(len(v) < 2 for v in k1.values()) and k1:
        P("  boards with only one ghost eaten: %d (the others were not frightened or not in contact; listed, not a failure)" % sum(1 for v in k1.values() if len(v) < 2))
    # ---- door square ----
    P("")
    P("C. The eaten ghost on the door square while Pac-Man stands on it (kind 2 boards):")
    k2 = {b: v for b, v in by_board.items() if b is not None and kind_of(b) == 2}
    ok = n = 0
    seq_ok = 0
    twice = 0
    for b, v in k2.items():
        f0, g, ge = v[0]
        n += 1
        if len([1 for x in v if x[1] == g]) > 1:
            twice += 1
        s = [x for x in st if x["g"] == g and x["f"] >= f0 and x["site"] in ("B6D0", "B764", "B756", "A888")][:3]
        door = [x for x in s if x["site"] == "B6D0"]
        home = [x for x in s if x["site"] == "B764"]
        if door:
            fd = door[0]["f"]
            a = fr.get(fd) or fr.get(fd - 1)
            if a and abs(a["p"][0] - 124) <= 2 and abs(a["p"][1] - 100) <= 2 and (door[0]["x"], door[0]["y"]) == (124, 100) and door[0]["old"] == 0x42:     # Pac-Man is put on (124,100) every frame and moves at most a pixel in between
                ok += 1
            if home and home[0]["old"] == 0x44:
                seq_ok += 1
    P("  boards with a ghost eaten: %d; the eyes reached the door square (124,100) with Pac-Man on it ($42 -> $44): %d; then went home ($44 -> $04): %d; the same ghost eaten twice: %d" % (n, ok, seq_ok, twice))
    if n and (ok != n or seq_ok != n or twice):
        problems.append("door square sequence")
    P("")
    P("PROBLEMS: " + ("none" if not problems else "; ".join(str(p) for p in problems)))
    return L, problems


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    L, problems = run(args[0])
    txt = "\n".join(L)
    print(txt)
    if summ:
        open(summ, "w", encoding="utf-8").write(txt + "\n")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
