"""Step C11, ghost state transitions: check the log of tools\\altirra_transitions.cmd against what the code says.

Every write to GhostState ($CE+ghost) in the ROM is one of 13 store instructions (found by searching the whole listing).
The log has one line per store with the old value, the new value, and the game's variables at that moment:
  ST site=B853 ghost=1 old=$01 dots=12 chase=0 gtimer=0 x=124 y=100 fright=0 frame=1234
Checks: (1) per site, the rule the code implies (old value and the condition that makes the store run; the new value is derived from the code); (2) continuity: for each ghost, the old value of
each store equals the value the previous store wrote (derived per site), except after a board start, so nothing else changes the state (no hidden writer); (3) a table of (old -> new, site) with counts.
Usage: python -I tools\\analyze_transitions_log.py F:\\Ports\\transitions.txt [--summary-file analysis\\evidence-ghost-transitions-summary.txt]
"""
import collections
import re
import sys

LINE = re.compile(r"ST site=([0-9A-F]{4}) ghost=(\d) old=\$([0-9A-F]{2}) dots=(\d+) chase=(\d+) gtimer=(\d+) x=(\d+) y=(\d+) fright=(\d+) frame=(\d+)")
NAME = {0x00: "house", 0x01: "start route", 0x02: "chase", 0x04: "leaving house", 0x08: "patrol travel", 0x10: "patrol", 0x20: "to corner",
        0x42: "eaten", 0x44: "eaten at door"}


def nm(s):
    base = NAME.get(s & 0x7F, "?")
    return "$%02X %s%s" % (s, base, " +frightened" if s & 0x80 else "")


def expect_new(site, g, old):
    """The value the store at `site` writes, from the code (the accumulator cannot be read in the debugger; the next write of the ghost checks it)."""
    return {0xA800: old + 1, 0xA888: 0x42, 0xAFA0: 0x00 if old == 0x80 else 0x20, 0xB40A: old | 0x80, 0xB626: 0x02, 0xB6D0: 0x44,
            0xB756: 0x01 if old == 0 else (old & 0x80) | 0x02, 0xB764: old & 0x0F, 0xB853: 0x08, 0xB895: 0x10, 0xB8C7: 0x20, 0xB8ED: 0x02, 0xBAB9: 0x02}[site]


def rule(site, g, old, new, d):
    """Returns None if the store matches what the code implies, else a text."""
    c, gt, dots, y = d["chase"], d["gtimer"], d["dots"], d["y"]
    if site == 0xA800:
        return None if (g, old, new) == (0, 0x00, 0x01) else "ghost 0 must go 0 -> 1"
    if site == 0xA888:      # GhostEaten: reached only for a frightened ghost (BMI at $A881)
        return None if new == 0x42 and old & 0x80 else "eaten: frightened -> $42"
    if site == 0xAFA0:      # frightened time over: $80 (in the house) -> 0, every other frightened state -> $20
        return None if old & 0x80 and ((old == 0x80 and new == 0x00) or (old != 0x80 and new == 0x20)) else "end of frightened: $80 -> 0, other -> $20"
    if site == 0xB40A:      # power pellet: set bit 7 of every ghost that is not eaten
        return None if new == old | 0x80 and not old & 0x40 else "pellet: old | $80, not for eaten ghosts"
    if site == 0xB626:      # Sub_B616 (dots eaten >= $B0.. thresholds): patrol travel, patrol and corner ghosts chase
        need = 0xF0 if g == 3 else 0xE0
        return None if old in (0x08, 0x10, 0x20) and new == 0x02 and dots >= need else "dots threshold: 8/$10/$20 -> 2 with dots >= $%02X" % need
    if site == 0xB6D0:      # eaten ghost reaches the door square ($7C,$64)
        return None if old == 0x42 and new == 0x44 else "eaten at the door: $42 -> $44"
    if site == 0xB756:      # Sub_B738 at the door row (y = $64): leave the house
        want = 0x01 if old == 0 else (old & 0x80) | 0x02
        return None if new == want and y == 0x64 else "leave the house: 0 -> 1, otherwise (old & $80) | 2, at y = $64"
    if site == 0xB764:      # LB760: ghost back inside the house after being eaten
        return None if new == old & 0x0F else "back in the house: state AND $0F"
    if site == 0xB853:      # GhostSelectPatrol
        return None if new == 0x08 and old in (0x01, 0x20) else "select patrol: start route / corner -> $08"
    if site == 0xB895:      # patrol travel: arrived
        return None if (old, new) == (0x08, 0x10) else "arrived at the route start: $08 -> $10"
    if site == 0xB8C7:      # GhostGoToCorner
        ok = new == 0x20 and ((old == 0x02 and c == 0) or (old in (0x08, 0x10) and gt == 0) or old == 0x20)
        return None if ok else "corner: chase timer 0 / patrol timer 0 / already at $20"
    if site == 0xB8ED:      # end of ghost 0's start route -> chase
        return None if (g, old, new) == (0, 0x01, 0x02) else "ghost 0 start route -> chase"
    if site == 0xBAB9:      # GhostSeesPacMan
        return None if old in (0x08, 0x10) and new == 0x02 else "sighted: patrol travel/patrol -> chase"
    return "unknown site"


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    rows = []
    for line in open(path, errors="replace"):
        m = LINE.search(line)
        if m:
            s, g, o, dots, c, gt, x, y, fr, fm = m.groups()
            n = None
            rows.append(dict(site=int(s, 16), g=int(g), old=int(o, 16), new=0, dots=int(dots), chase=int(c), gtimer=int(gt), x=int(x), y=int(y), fright=int(fr), frame=int(fm)))
    inits = [int(m.group(1)) for m in (re.search(r"INIT_BOARD frame=(\d+)", l) for l in open(path, errors="replace")) if m]
    P("state writes logged:", len(rows), "  frames:", rows[0]["frame"] if rows else 0, "-", rows[-1]["frame"] if rows else 0)
    for r in rows:
        r["new"] = expect_new(r["site"], r["g"], r["old"])
    bad = []
    table = collections.Counter()
    for r in rows:
        why = rule(r["site"], r["g"], r["old"], r["new"], r)
        table[(r["site"], r["old"], r["new"])] += 1
        if why:
            bad.append((why, r))
    P("writes that break the rule the code implies:", len(bad))
    for why, r in bad[:15]:
        P("  ", why, r)
    # continuity per ghost: nothing but the logged stores changes the state, except InitBoard ($ADAF), which clears zero page $80-$FF (including $CE-$D1) when a board starts
    last, breaks = {}, []
    for r in rows:
        g = r["g"]
        if g in last and last[g]["new"] != r["old"]:
            breaks.append((last[g], r))
        last[g] = r
    explained = [(a, b) for a, b in breaks if b["old"] == 0 and any(a["frame"] <= f <= b["frame"] for f in inits)]
    P("InitBoard calls logged:", len(inits), "  (A800 writes = board starts:", sum(1 for r in rows if r["site"] == 0xA800), ")")
    P("continuity: consecutive writes of one ghost where old != the value the previous write left:", len(breaks),
      "  of which explained by InitBoard (old = 0 and a call between the two writes):", len(explained))
    for a, b in [x for x in breaks if x not in explained][:10]:
        P("   unexplained: site $%04X new %s -> site $%04X old %s frames %d-%d" % (a["site"], hex(a["new"]), b["site"], hex(b["old"]), a["frame"], b["frame"]))
    bad += [("unexplained state change", b) for a, b in breaks if (a, b) not in explained]
    P()
    P("transitions by store site (count):")
    by_site = collections.defaultdict(list)
    for (s, o, n), cnt in sorted(table.items()):
        by_site[s].append((o, n, cnt))
    DESC = {0xA800: "game start: ghost 0 leaves the house", 0xA888: "ghost eaten (Pac-Man touches a frightened ghost)", 0xAFA0: "frightened time over",
            0xB40A: "power pellet eaten", 0xB626: "dots-eaten threshold (late board): all patrol/corner ghosts chase", 0xB6D0: "eaten ghost reaches the door square",
            0xB756: "ghost leaves the house at the door row", 0xB764: "eaten ghost back inside the house", 0xB853: "GhostSelectPatrol", 0xB895: "arrived at the patrol start junction",
            0xB8C7: "GhostGoToCorner (chase time up / patrol time up)", 0xB8ED: "ghost 0 finishes its start route", 0xBAB9: "GhostSeesPacMan"}
    for s in sorted(by_site):
        P("  $%04X  %s   (%d writes)" % (s, DESC[s], sum(c for _, _, c in by_site[s])))
        for o, n, cnt in by_site[s]:
            P("        %-28s -> %-28s %6d" % (nm(o), nm(n), cnt))
    unseen = [s for s in DESC if s not in by_site]
    P("store sites never reached in this run:", ["$%04X" % s for s in unseen])
    # the three states of the question: who moves a ghost into and out of start route (1), patrol (8, $10) and chase (2)
    P()
    P("per ghost, the states it was in (new values) and how often it entered them:")
    for g in range(4):
        cnt = collections.Counter(r["new"] for r in rows if r["g"] == g)
        P("  ghost %d:" % g, ", ".join("%s x%d" % (nm(k), v) for k, v in sorted(cnt.items())))
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
