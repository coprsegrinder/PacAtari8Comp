"""OV-31: check the tunnel-edge clipping (Sub_AB48 / Sub_AB57, $AB48-$ABC8) against the log of tools\altirra_tunnel_clip.cmd.

The code (src/asm/pacman.s): for an entity on the tunnel row (EntityY = $74) the mask zp_FE starts as $FF;
  X >= $C0:  mask = $FF << (X - $C0)   (0 from X - $C0 = 8 on);  if X >= $CA and the direction is right ($08): X := $2A  (Pac-Man, x = 4: zp_80 := $8F)
  X <  $39:  mask = $FF >> ($38 - X)   ($FF at X = $38, 0 from X = $30 on);  if X = $2A and the direction is left ($04): X := $CA  (Pac-Man: zp_80 := $B7)
  else       no clipping.
and the 16 picture rows at page $24+x (Pac-Man: $23), offset $74, are ANDed with the mask.
The log has an ENTER line (entity, X, Y, direction before the call) and a LEAVE line (X, direction, the mask, the pointer, zp_80, three picture bytes) for every call.  In the sweep (k >= 200) the 16 rows were filled with $FF
before the call, so every picture byte after it must equal the mask.
Usage: python -I tools\analyze_tunnel_clip.py analysis\raw-logs\tunnel-clip.txt [--summary-file out.txt]
"""
import collections
import re
import sys

ENTER = re.compile(r"ENTER x=(\d) X=(\d+) Y=(\d+) dir=(\d+) k=(-?\d+) f=(\d+)")
LEAVE = re.compile(r"LEAVE x=(\d) X=(\d+) dir=(\d+) mask=\$([0-9A-F]{2}) ptr=\$([0-9A-F]{2})([0-9A-F]{2}) z80=\$([0-9A-F]{2}) b0=\$([0-9A-F]{2}) b7=\$([0-9A-F]{2}) b15=\$([0-9A-F]{2}) f=(\d+)")


def model(X, d):
    """(mask, new X, wrap kind) for an entity on the tunnel row at X moving in direction d."""
    if X >= 0xC0:
        n = X - 0xC0
        mask = (0xFF << n) & 0xFF if n <= 8 else 0
        if n >= 9 and X >= 0xCA and d == 8:
            return mask, 0x2A, "right"
        return mask, X, None
    if X < 0x39:
        m = 0x38 - X
        mask = 0xFF >> m if m <= 8 else 0
        if m >= 9 and X == 0x2A and d == 4:
            return mask, 0xCA, "left"
        return mask, X, None
    return 0xFF, X, None


def parse(path):
    calls, cur = [], None
    for l in open(path, errors="replace"):
        if l.startswith("ENTER"):
            m = ENTER.match(l)
            cur = m and tuple(int(v) for v in m.groups())
        elif l.startswith("LEAVE") and cur:
            m = LEAVE.match(l)
            if m:
                g = m.groups()
                x, X, d = int(g[0]), int(g[1]), int(g[2])
                calls.append(dict(x=x, X0=cur[1], Y=cur[2], d0=cur[3], k=cur[4], f=cur[5], X1=X, d1=d, mask=int(g[3], 16), page=int(g[4], 16), off=int(g[5], 16),
                                  z80=int(g[6], 16), b=(int(g[7], 16), int(g[8], 16), int(g[9], 16))))
            cur = None
    return calls


def check(calls):
    L, bad = [], collections.Counter()
    cover = collections.defaultdict(set)
    wraps = collections.Counter()
    masks = collections.Counter()
    examples = []
    for c in calls:
        mask, X1, wrap = model(c["X0"], c["d0"])
        sweep = c["k"] >= 200
        why = []
        if c["mask"] != mask:
            why.append("mask $%02X, model $%02X" % (c["mask"], mask))
        if c["X1"] != X1:
            why.append("X after %d, model %d" % (c["X1"], X1))
        want_page = 0x23 if c["x"] == 4 else 0x24 + c["x"]
        if c["page"] != want_page or c["off"] != 0x74:
            why.append("pointer $%02X%02X, expected $%02X74" % (c["page"], c["off"], want_page))
        if sweep and any(b != mask for b in c["b"]):
            why.append("picture bytes %s, mask $%02X" % (["$%02X" % b for b in c["b"]], mask))
        if not sweep and any(b & ~mask & 0xFF for b in c["b"]):
            why.append("natural picture byte has bits outside the mask")
        if c["x"] == 4 and wrap:
            want = 0x8F if wrap == "right" else 0xB7
            if c["z80"] != want:
                why.append("Pac-Man wrap: zp_80 $%02X, expected $%02X" % (c["z80"], want))
        if why:
            bad["calls with a deviation"] += 1
            if len(examples) < 10:
                examples.append((c, why))
        key = ("sweep" if sweep else "natural", c["x"], c["d0"])
        cover[key].add(c["X0"])
        if wrap:
            wraps[(wrap, "Pac-Man" if c["x"] == 4 else "ghost", "sweep" if sweep else "natural")] += 1
        if sweep:
            masks[mask] += 1
    return bad, cover, wraps, masks, examples


def report(calls):
    bad, cover, wraps, masks, examples = check(calls)
    L = []
    P = L.append
    sw = [c for c in calls if c["k"] >= 200]
    P("Calls of Sub_AB57 in the log: %d (%d in the sweep, %d natural: the game's own entities on the tunnel row)." % (len(calls), len(sw), len(calls) - len(sw)))
    P("Deviations from the model (mask, X after the call, pointer, picture bytes, Pac-Man's zp_80): %d" % bad["calls with a deviation"])
    for c, why in examples:
        P("  x=%d X=%d dir=%d k=%d f=%d: %s" % (c["x"], c["X0"], c["d0"], c["k"], c["f"], "; ".join(why)))
    P("")
    P("Coverage of the sweep (X values seen at the call, per entity and direction):")
    for key in sorted(k for k in cover if k[0] == "sweep"):
        xs = sorted(cover[key])
        P("  entity %d dir %s: %d values, X %d..%d%s" % (key[1], "left" if key[2] == 4 else "right", len(xs), xs[0], xs[-1], "" if len(xs) == xs[-1] - xs[0] + 1 else " (gaps)"))
    P("Masks seen in the sweep (count of calls): " + ", ".join("$%02X: %d" % (m, n) for m, n in sorted(masks.items(), reverse=True)))
    P("Wraps (X moved to the other side): " + ", ".join("%s %s %s: %d" % (k[0], k[1], k[2], n) for k, n in sorted(wraps.items())))
    nat = sorted(set((k[1], c) for k, c in [(k, 0) for k in cover if k[0] == "natural"]))
    natX = collections.Counter()
    for c in calls:
        if c["k"] < 200:
            natX[(c["x"], "left of $39" if c["X0"] < 0x39 else "right of $BF" if c["X0"] >= 0xC0 else "inside the maze")] += 1
    P("Natural calls (the game's own entities on the tunnel row, before the sweep): " + ", ".join("entity %d %s: %d" % (k[0], k[1], n) for k, n in sorted(natX.items())))
    P("")
    P("PROBLEMS: " + ("none" if not bad else "%d calls deviate" % bad["calls with a deviation"]))
    return L, bad


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    calls = parse(args[0])
    L, bad = report(calls)
    txt = "\n".join(L)
    print(txt)
    if summ:
        open(summ, "w", encoding="utf-8").write(txt + "\n")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
