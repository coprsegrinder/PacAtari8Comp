"""The sight test while a ghost is frightened or eaten. Checks the log of tools\\altirra_sight_states.cmd.
Code (docs/15, docs/17): the loop at $B603 (once per frame) calls GhostSeesPacMan ($BA19) only for a ghost whose state is exactly $08 or $10. Everything else - frightened ($88, $90, $8x ...), eaten ($42, $44),
house, start route, chase, corner - is never tested, so it can never be switched to chase ($02, ChaseTimer := $A0) by sight. For every logged frame and ghost this compares:
  * the state at the start of the loop (SL line) with whether GhostSeesPacMan was called for it (CALL lines up to the next SL line);
  * the exact software model of the sight test (tools/sight_model.py, built from the ROM bytes) with whether the ghost was sighted (SIGHTED lines): for $08/$10 they must agree;
    for every other state the model is evaluated anyway ('would see'), and no call and no sighting may follow.
Usage: python -I tools/analyze_sight_states_log.py <log> [--summary-file out]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sight_model as M  # noqa: E402

RE_SL = re.compile(r"SL st=\$(..),\$(..),\$(..),\$(..) x=(\d+),(\d+),(\d+),(\d+) y=(\d+),(\d+),(\d+),(\d+) d=(\d+),(\d+),(\d+),(\d+) p=(\d+),(\d+) rt=(\d+) lv=(\d+) f=(\d+)")
RE_CALL = re.compile(r"CALL g=(\d) st=\$(..) f=(\d+)")
RE_SIGHT = re.compile(r"SIGHTED g=(\d) f=(\d+)")
RE_PEL = re.compile(r"PELLET f=(\d+)")
RE_EAT = re.compile(r"GHOST_EATEN g=(\d) f=(\d+)")


def name(st):
    if st in (0x08, 0x10):
        return "patrol $%02X" % st
    if st & 0x40:
        return "eaten $%02X" % st
    if st & 0x80:
        return "frightened $%02X" % st
    return "other $%02X" % st


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    snaps, calls, sights = [], [], []
    ev = []
    for line in open(path, errors="replace"):
        m = RE_SL.search(line)
        if m:
            g = m.groups()
            snaps.append(dict(st=[int(g[i], 16) for i in range(4)], x=[int(g[4 + i]) for i in range(4)], y=[int(g[8 + i]) for i in range(4)], d=[int(g[12 + i]) for i in range(4)],
                              px=int(g[16]), py=int(g[17]), rt=int(g[18]), lv=int(g[19]), f=int(g[20]), calls=set(), sighted=set()))
            continue
        if snaps:
            m = RE_CALL.search(line)
            if m:
                snaps[-1]["calls"].add((int(m.group(1)), int(m.group(2), 16)))
                continue
            m = RE_SIGHT.search(line)
            if m:
                snaps[-1]["sighted"].add(int(m.group(1)))
                continue
    cnt = collections.Counter()
    bad = collections.defaultdict(list)
    table = collections.defaultdict(lambda: collections.Counter())     # class -> counter(ghost-frames, would_see, called, sighted)
    for s in snaps:
        for g in range(4):
            st = s["st"][g]
            cls = name(st)
            would = M.sees(g, s["x"][g], s["y"][g], s["d"][g], s["px"], s["py"], s["rt"])
            called = any(c[0] == g for c in s["calls"])
            sighted = g in s["sighted"]
            t = table[cls]
            t["ghost-frames"] += 1
            t["model says: would see"] += int(would)
            t["GhostSeesPacMan called"] += int(called)
            t["sighted ($BAB9 executed)"] += int(sighted)
            t["would see AND called"] += int(would and called)
            should_call = st in (0x08, 0x10)
            if called != should_call:
                bad["call does not match 'state is $08 or $10'"].append((s["f"], g, st))
            if called and (g, st) not in s["calls"]:
                bad["state at the call differs from the state at the loop start"].append((s["f"], g, st))
            if should_call:
                if sighted != would:
                    bad["patrol ghost: sighting differs from the model"].append((s["f"], g, st, s["x"][g], s["y"][g], s["d"][g], s["px"], s["py"], s["rt"], would, sighted))
            else:
                if sighted:
                    bad["a ghost not in $08/$10 was sighted"].append((s["f"], g, st))
    P("sight-loop snapshots:", len(snaps), "(frames", snaps[0]["f"] if snaps else "-", "to", snaps[-1]["f"] if snaps else "-", ")  levels:", sorted({s["lv"] for s in snaps}))
    P()
    P("by state of the ghost at the start of the loop:")
    P("  %-18s %12s %12s %12s %12s" % ("state", "ghost-frames", "would see", "called", "sighted"))
    for cls in sorted(table, key=lambda c: (not c.startswith("patrol"), c)):
        t = table[cls]
        P("  %-18s %12d %12d %12d %12d" % (cls, t["ghost-frames"], t["model says: would see"], t["GhostSeesPacMan called"], t["sighted ($BAB9 executed)"]))
    groups = {"patrol ($08/$10)": lambda c: c.startswith("patrol"), "frightened ($80 bit, not eaten)": lambda c: c.startswith("frightened"), "eaten ($42/$44 ...)": lambda c: c.startswith("eaten"), "all other states": lambda c: c.startswith("other")}
    P()
    P("grouped:")
    for gname, fn in groups.items():
        tot = collections.Counter()
        for cls, t in table.items():
            if fn(cls):
                tot.update(t)
        P("  %-34s ghost-frames %7d | would see %6d | called %6d | sighted %5d" % (gname, tot["ghost-frames"], tot["model says: would see"], tot["GhostSeesPacMan called"], tot["sighted ($BAB9 executed)"]))
    k88 = sum(table[c]["model says: would see"] for c in table if c in ("frightened $88", "frightened $90"))
    P()
    P("frightened patrol ghosts ($88 / $90) that the model says would see Pac-Man:", k88, "- sightings among them:", sum(table[c]["sighted ($BAB9 executed)"] for c in ("frightened $88", "frightened $90") if c in table))
    # frightened patrol ghosts in detail: separate episodes (a ghost in that state, gaps of at most 2 frames joined) and separate runs of 'would see' frames, per ghost
    P()
    P("frightened patrol ghosts in detail (episodes = separate frightened periods of one ghost in that state; runs = separate stretches of consecutive 'model says would see' frames):")
    for stv in (0x88, 0x90):
        eps = {g: [] for g in range(4)}
        runs = {g: [] for g in range(4)}
        frames = collections.Counter()
        wsf = collections.Counter()
        for s in snaps:
            for g in range(4):
                if s["st"][g] != stv:
                    continue
                frames[g] += 1
                e = eps[g]
                if e and s["f"] - e[-1][1] <= 2:
                    e[-1][1] = s["f"]
                else:
                    e.append([s["f"], s["f"], s["lv"]])
                if M.sees(g, s["x"][g], s["y"][g], s["d"][g], s["px"], s["py"], s["rt"]):
                    wsf[g] += 1
                    r = runs[g]
                    if r and s["f"] - r[-1][1] <= 2:
                        r[-1][1] = s["f"]
                    else:
                        r.append([s["f"], s["f"], s["lv"]])
        for g in range(4):
            P("  $%02X ghost %d: %5d ghost-frames in %3d episodes (levels %s) | would see: %4d frames in %3d runs (levels %s)" % (stv, g, frames[g], len(eps[g]), sorted({e[2] for e in eps[g]}), wsf[g], len(runs[g]), sorted({r[2] for r in runs[g]})))
        P("  $%02X total: %d episodes, %d runs of 'would see' frames; sightings in this state: %d" % (stv, sum(len(e) for e in eps.values()), sum(len(r) for r in runs.values()), sum(1 for s in snaps for g in range(4) if s["st"][g] == stv and g in s["sighted"])))
    P("violations:", {k: len(v) for k, v in bad.items()} or "none")
    for k, v in bad.items():
        P("  first", k, v[:3])
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
