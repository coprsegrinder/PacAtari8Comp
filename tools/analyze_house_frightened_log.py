"""A frightened ghost still INSIDE the ghost house ($00 -> $80 at a power pellet, $AF9A turns $80 back into $00 when the frightened time ends). Checks the log of tools\\altirra_house_frightened.cmd.
Every GhostState write is logged (ST lines, with the state it replaces, the ghost's x/y, the frame). A power-pellet episode = the PELLET events of one frightened period (the test aid keeps the pellet being eaten
for 16 frames, so one episode has many PELLET lines; the LAST pellet of the run starts the countdown). For each ghost that held $80 after the last pellet of an episode: what was its next state change,
at which site, where was it, and how long after the pellet?
Usage: python -I tools/analyze_house_frightened_log.py <log> [--summary-file out]
"""
import collections
import re
import sys

RE_ST = re.compile(r"ST site=([0-9A-F]{4}) ghost=(\d) old=\$([0-9A-F]{2}) dots=(\d+) chase=(\d+) gtimer=(\d+) x=(\d+) y=(\d+) fright=(\d+) frame=(\d+)")
RE_PEL = re.compile(r"PELLET frame=(\d+)")
RE_ENDS = re.compile(r"FRIGHT_ENDS ghost=(\d) state=\$([0-9A-F]{2}) level=(\d+) frame=(\d+)")
HOUSE = (lambda x, y: 108 <= x <= 140 and 104 <= y <= 124)       # the house interior incl. the bobbing range y 112-120 and the door column


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    events = []
    for line in open(path, errors="replace"):
        m = RE_ST.search(line)
        if m:
            events.append(("st", m)); continue
        m = RE_PEL.search(line)
        if m:
            events.append(("pel", m)); continue
        m = RE_ENDS.search(line)
        if m:
            events.append(("ends", m))
    # episodes: group B40A writes by frame; the episode's last frame of pellets is the one that counts
    cnt = collections.Counter()
    rows = []
    i = 0
    n = len(events)
    # state of each ghost after each ST write is not logged; reconstruct from "old" of the NEXT write of the same ghost: the new state of a write = old of the next write of that ghost
    last_state = {}
    hist = collections.defaultdict(list)            # ghost -> [(frame, site, old, x, y, gtimer)]
    for kind, m in events:
        if kind == "st":
            site, g, old, dots, chase, gt, x, y, fr, f = m.groups()
            hist[int(g)].append((int(f), site, int(old, 16), int(x), int(y), int(gt), int(fr)))
    pellets = sorted({int(m.group(1)) for k, m in events if k == "pel"})
    # episodes = runs of consecutive pellet frames (gap <= 2)
    eps = []
    for f in pellets:
        if eps and f - eps[-1][1] <= 2:
            eps[-1][1] = f
        else:
            eps.append([f, f])
    cnt["power-pellet episodes"] = len(eps)
    for (f0, f1) in eps:
        # the writes of the last pellet of the run: B40A at frame f1+1 (the trace fires at the next frame number)
        for g in range(4):
            wr = [h for h in hist[g] if h[1] == "B40A" and f1 <= h[0] <= f1 + 2]
            if not wr:
                continue
            w = wr[-1]
            if w[2] not in (0x00, 0x80):          # was in the house (waiting) when the last pellet was eaten: old $00 or already $80
                continue
            cnt["ghosts in a house-waiting state ($00/$80) at the last pellet"] += 1
            # next write for this ghost after the pellet other than B40A
            nxt = [h for h in hist[g] if h[0] > w[0] and h[1] != "B40A"]
            if not nxt:
                cnt["  ... no later write in the log"] += 1
                continue
            nx = nxt[0]
            rows.append((f1, g, w[3], w[4], nx[0], nx[1], nx[2], nx[3], nx[4], nx[5]))
            site_old = (nx[1], nx[2])
            cnt["  ... next write by site %s replacing $%02X" % site_old] += 1
    P("episodes and ghosts that were waiting in the house when the countdown started (last pellet of the episode):")
    for k in sorted(cnt):
        P("  %-80s %d" % (k, cnt[k]))
    P()
    P("sample (pellet frame, ghost, x, y at the pellet | next write: frame, site, replaced state, x, y, house timer):")
    shown = 0
    for r in rows:
        if r[5] == "AFA0":
            P("  ", r, "frames after the pellet:", r[4] - r[0], "| stayed in the house square:", HOUSE(r[7], r[8]))
            shown += 1
            if shown >= 12:
                break
    ends = collections.Counter()
    for kind, m in events:
        if kind == "ends":
            ends["$" + m.group(2)] += 1
    P("states seen by the end-of-frightened loop ($AF8C), all ghosts:", dict(ends))
    afa0 = [h for g in range(4) for h in hist[g] if h[1] == "AFA0"]
    p80 = [h for h in afa0 if h[2] == 0x80]
    P("writes at $AFA0 (the end of the frightened time): %d, of which the ghost held $80 (-> $00): %d, inside the house square: %d" % (len(afa0), len(p80), sum(1 for h in p80 if HOUSE(h[3], h[4]))))
    # the NEW state of a write is the OLD state of the next write of the same ghost (the log has the old value only); chains of the three transitions of interest
    P()
    P("transitions of a ghost that was waiting in the house (state AND $7F = 0) while frightened:")
    chk = collections.Counter()
    first = {}
    for g in range(4):
        h = hist[g]
        for k in range(len(h) - 1):
            f, site, old, x, y, gt, fr = h[k]
            nxt_old = h[k + 1][2]
            if site == "B40A" and old == 0x00:
                chk["power pellet: house-waiting $00 became $80 (next write sees $80)" + (" OK" if nxt_old == 0x80 or h[k + 1][1] == "B40A" else " WRONG")] += 1
            if site == "AFA0" and old == 0x80:
                natural = h[k + 1][1] != "B40A"          # the test aid keeps eating the pellet for 16 frames: a write followed at once by another pellet is not a natural end
                ok = nxt_old == 0x00
                chk["frightened time ends, ghost still $80: became $00 (next write sees $00) - %s: %s" % ("natural end" if natural else "aid pellet re-eaten at once", "OK" if ok else "WRONG")] += 1
                if natural:
                    first.setdefault("afa0", []).append((f, g, x, y, gt, h[k + 1][1], h[k + 1][0], h[k + 1][3], h[k + 1][4], h[k + 1][2]))
                    chk["   ... natural end: ghost inside the house square" if HOUSE(x, y) else "   ... natural end: ghost in the exit corridor, not yet at the door row"] += 1
            if site == "B756" and old == 0x80:
                chk["frightened ghost reaches the door row still frightened: $80 became $82 (next write sees $82)" + (" OK" if nxt_old == 0x82 else " WRONG")] += 1
            if site == "B756" and old == 0x00:
                chk["normal release at the door row: $00 became $01"] += 1
    for k in sorted(chk):
        P("  %-110s %d" % (k, chk[k]))
    P("natural ends, $80 -> $00 (frame, ghost, x, y, house timer at the write | next write: site, frame, x, y, state it replaces):")
    for r in first.get("afa0", []):
        P("  ", r)
    P("after $80 -> $00 the ghost's next write is:", dict(collections.Counter(r[5] for r in first.get("afa0", []))))
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
