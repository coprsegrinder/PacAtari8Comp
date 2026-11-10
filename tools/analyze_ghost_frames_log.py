"""Check every logged ghost draw against the frame rule read from the code (step C11, ghost frames).
Usage: python -I tools/analyze_ghost_frames_log.py <log> [--summary-file out]
Rule (StepAndDrawEntity $B93F-$B96A): shape = $BAC0 + offset; offset = {up 0, down $0A, left $14, right $1E}[EntityDir];
frightened (state bit 7) -> $28; eaten (state bit 6) -> $32 and feet row 0; otherwise feet row = $AA if zp_AF else $54."""
import collections
import re
import sys

BASE = 0xBAC0
OFF = {1: 0x00, 2: 0x0A, 4: 0x14, 8: 0x1E}
NAME = {0xBAC0: "Up", 0xBACA: "Down", 0xBAD4: "Left", 0xBADE: "Right", 0xBAE8: "Frightened", 0xBAF2: "Eyes"}


def expect(state, d, af):
    off = OFF.get(d)
    if state & 0x80:
        off = 0x28
    feet = 0xAA if af else 0x54
    if state & 0x40:
        off, feet = 0x32, 0x00
    return (None if off is None else BASE + off), feet


def main(path):
    L = [l.rstrip("\n") for l in open(path, encoding="latin1", errors="replace")]
    n = bad = 0
    combos = collections.Counter()
    colours = collections.defaultdict(collections.Counter)
    badl = []
    toggles = []
    for l in L:
        m = re.match(r"GHOST_DRAW ghost=(\d) src=\$(\w+) state=\$(\w+) dir=(\d+) af=(\d+) feet=\$(\w+) color=\$(\w+)", l)
        if m:
            n += 1
            g, src, st, d, af, feet, col = int(m[1]), int(m[2], 16), int(m[3], 16), int(m[4]), int(m[5]), int(m[6], 16), int(m[7], 16)
            want_src, want_feet = expect(st, d, af)
            if (src, feet) != (want_src, want_feet):
                bad += 1
                if len(badl) < 5:
                    badl.append(l)
            kind = "eyes" if st & 0x40 else ("frightened" if st & 0x80 else "normal")
            combos[(kind, NAME.get(src, "?%04X" % src))] += 1
            colours[kind][col] += 1
            continue
        m = re.match(r"AF_TOGGLE to=(\d) rtclok=(\d+) frame=(\d+)", l)
        if m:
            toggles.append((int(m[1]), int(m[2]), int(m[3])))
    out = ["%d lines, %d ghost draws; frame/feet differ from the rule on %d draws" % (len(L), n, bad)]
    if badl:
        out.append("   first mismatches: %s" % badl)
    out.append("draws by (kind, shape drawn): " + ", ".join("%s/%s: %d" % (k[0], k[1], v) for k, v in sorted(combos.items())))
    for kind in ("normal", "frightened", "eyes"):
        out.append("player colour register while drawing %s ghosts: %s" % (kind, ", ".join("$%02X x%d" % kv for kv in sorted(colours[kind].items()))))
    ok = sum(1 for _, r, _ in toggles if r % 16 == 0)
    gaps = collections.Counter(b[2] - a[2] for a, b in zip(toggles, toggles[1:]))
    out.append("zp_AF toggles: %d, all at RTCLOK2 mod 16 == 0: %s; frame gaps between toggles: %s" % (len(toggles), ok == len(toggles), dict(gaps.most_common(4))))
    return out


if __name__ == "__main__":
    out = main(sys.argv[1])
    print("\n".join(out))
    if "--summary-file" in sys.argv:
        open(sys.argv[sys.argv.index("--summary-file") + 1], "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
