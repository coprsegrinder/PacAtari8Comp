"""Who catches Pac-Man while the frightened phase is running? Checks the log of tools\\altirra_catch.cmd (board 71 = level counter 70, Pac-Man cannot die).
Code facts (docs/18): the collision test ($A851-$A883) skips ghosts with bit 6 set (eaten); a contact with a ghost whose bit 7 (frightened) is set eats it, a contact with any other ghost ends
the life (the death routine, $A923, skipped by the test aid). Bit 7 is set for every ghost at a power pellet ($B40A) and cleared when the eaten ghost is home again (state AND $0F, $B764).
Claim to verify: every catch during a frightened episode is made by a ghost that was eaten after the last power pellet and has since come home (so it is no longer frightened).
Usage: python -I tools/analyze_catch_log.py <log> [--summary-file out]
"""
import collections
import re
import sys

RE_CAUGHT = re.compile(r"CAUGHT ghost=(\d) g0=\$([0-9A-F]{2}) g1=\$([0-9A-F]{2}) g2=\$([0-9A-F]{2}) g3=\$([0-9A-F]{2}) FC=(\d+) FD=(\d+) pacx=(\d+) pacy=(\d+) frame=(\d+)")
RE_ST = re.compile(r"ST site=([0-9A-F]{4}) ghost=(\d) old=\$([0-9A-F]{2}) .*? fright=(\d+) frame=(\d+)")
RE_EAT = re.compile(r"GHOST_EATEN ghost=(\d) frame=(\d+)")
RE_PEL = re.compile(r"PELLET frame=(\d+)")


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    ev = []
    for line in open(path, errors="replace"):
        for kind, rx in (("caught", RE_CAUGHT), ("eat", RE_EAT), ("pellet", RE_PEL), ("st", RE_ST)):
            m = rx.search(line)
            if m:
                ev.append((kind, m))
                break
    # the frame number of every event: caught/eat/st/pellet all log @frame
    last_pellet = None
    eaten_since_pellet = {}        # ghost -> frame
    home_since_eaten = {}          # ghost -> frame of the store at $B764 after the eating
    cnt = collections.Counter()
    rows = []
    bad = []
    for kind, m in ev:
        if kind == "pellet":
            last_pellet = int(m.group(1))
            eaten_since_pellet, home_since_eaten = {}, {}
            cnt["power pellets"] += 1
        elif kind == "eat":
            g, f = int(m.group(1)), int(m.group(2))
            eaten_since_pellet[g] = f
            home_since_eaten.pop(g, None)
            cnt["ghosts eaten"] += 1
        elif kind == "st":
            site, g, f = m.group(1), int(m.group(2)), int(m.group(5))
            if site == "B764" and g in eaten_since_pellet and g not in home_since_eaten:
                home_since_eaten[g] = f
        elif kind == "caught":
            g = int(m.group(1))
            st = [int(m.group(2 + i), 16) for i in range(4)]
            fc, fd, f = int(m.group(6)), int(m.group(7)), int(m.group(10))
            during = last_pellet is not None and fc > 0
            cnt["catch events (one per frame of contact)"] += 1
            if not during:
                cnt["catch events before the first power pellet / phase not running"] += 1
                continue
            cnt["catch events while the frightened phase was running (FC > 0)"] += 1
            ok = g in eaten_since_pellet and g in home_since_eaten and home_since_eaten[g] <= f
            cnt["  ... by a ghost eaten after the last power pellet and already home again"] += int(ok)
            if not ok:
                bad.append((f, g, st, fc, fd, eaten_since_pellet, home_since_eaten))
            rows.append((f, g, st, fc, last_pellet, eaten_since_pellet.get(g), home_since_eaten.get(g), [x >> 7 for x in st]))
    for k in sorted(cnt):
        P("  %-90s %d" % (k, cnt[k]))
    P("first catch events during the phase (frame, ghost, states g0-g3, FC, last pellet, eaten, home again, bit7 of the four ghosts):")
    seen = set()
    for r in rows:
        key = (r[1], r[4], r[5])
        if key in seen:
            continue
        seen.add(key)
        P("  ", r)
        if len(seen) >= 12:
            break
    P("catches not explained by 'eaten after the last pellet and home again':", len(bad))
    for b in bad[:5]:
        P("  ", b)
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
