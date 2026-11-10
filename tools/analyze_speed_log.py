"""Step C11: how often a ghost acts (GhostBehaviour, $B7F5), by level and by kind (normal / frightened / tunnel). Log from tools\altirra_speed.cmd.
From the code ($AA04-$AA26): a ghost acts when its move-delay counter runs out; a FRIGHTENED ghost, and any ghost in the tunnel row (y = $74, x < $52 or x >= $A7),
acts only on every SECOND time the counter runs out, i.e. at half speed. Eaten ghosts are moved by Sub_B69E once per frame instead (docs/18).
Usage: python -I tools\analyze_speed_log.py F:\Ports\speed.txt [--summary-file analysis\evidence-ghost-speed-summary.txt]
"""
import collections
import re
import statistics
import sys

GB = re.compile(r"GB ghost=(\d) state=\$([0-9A-F]{2}) x=(\d+) y=(\d+) lvl=(\d+) frame=(\d+)")


def kind(state, x, y):
    if y == 0x74 and (x < 0x52 or x >= 0xA7):
        return "tunnel (frightened)" if state & 0x80 else "tunnel"
    return "frightened" if state & 0x80 else "normal"


def main():
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    last = {}
    sp = collections.defaultdict(list)
    n = 0
    for line in open(sys.argv[1], errors="replace"):
        m = GB.search(line)
        if not m:
            continue
        g, s, x, y, lv, f = int(m.group(1)), int(m.group(2), 16), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6))
        n += 1
        if g in last:
            p = last[g]
            if p["lv"] == lv and p["state"] & 0x7F in (1, 2, 8, 0x10, 0x20) and s & 0x7F in (1, 2, 8, 0x10, 0x20) and (p["state"] & 0x80) == (s & 0x80) \
               and kind(p["state"], p["x"], p["y"]) == kind(s, x, y) and 0 < f - p["f"] <= 20:
                sp[(lv, kind(s, x, y))].append(f - p["f"])
        last[g] = dict(state=s, x=x, y=y, lv=lv, f=f)
    P("GhostBehaviour calls logged:", n)
    P("frames between two consecutive actions of the same ghost (same level, same kind, gaps over 20 frames = the 34-frame score pop-up pause are left out), per level:")
    P("  %-5s %-22s %7s %8s %8s   %s" % ("level", "kind", "count", "mean", "median", "most common spacings"))
    for (lv, k), v in sorted(sp.items()):
        c = collections.Counter(v).most_common(3)
        P("  %-5d %-22s %7d %8.2f %8.1f   %s" % (lv, k, len(v), statistics.mean(v), statistics.median(v), c))
    P("ratio (mean spacing of the kind / mean spacing of normal, same level):")
    for (lv, k), v in sorted(sp.items()):
        if k != "normal" and (lv, "normal") in sp:
            P("  level %d %-22s %.2f" % (lv, k, statistics.mean(v) / statistics.mean(sp[(lv, "normal")])))
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
