"""Stage 46: checks the Altirra pointer traces of tools/run_pointer_audit.ps1 against the rules of docs/29-pointers.md.

Input: analysis/raw-logs/pointers-<harness>.txt, with the lines
  PTR s=$XXXX src=$.... dst=$.... mz=$.... clip=$.... pm=$.... pp=$.... x=N y=N f=N py=N px=N
logged at the probe addresses (analyze_pointers.PROBES): the pointers $3C (SrcPtr), $3E (DstPtr), $80 (MazePtr), $47 (ClipPtr), $38 (PopupMissilePtr), $3A (PopupPlayerPtr), X, Y, the frame, PacY, PacX.
Every probe has a rule (RULES: the value classes the code can produce); a line that breaks its rule is reported.  The first 100 frames (the boot) are not left out: the boot is part of the check (probes A3B8, A668).
Usage: python -I tools/analyze_pointer_log.py analysis/raw-logs/pointers-*.txt [--write analysis/evidence-pointers-summary.txt]
"""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_pointers as AP  # noqa: E402

ROOT = AP.ROOT
LINE = re.compile(r"^PTR s=\$([0-9A-F]{4}) src=\$([0-9A-F]{4}) dst=\$([0-9A-F]{4}) mz=\$([0-9A-F]{4}) clip=\$([0-9A-F]{4}) pm=\$([0-9A-F]{4}) pp=\$([0-9A-F]{4}) x=(\d+) y=(\d+) f=(\d+) py=(\d+) px=(\d+)")
FIELDS = ("s", "src", "dst", "mz", "clip", "pm", "pp", "x", "y", "f", "py", "px")


def label_addr(name):
    for first, last, kind, n, comment in AP.LB.DATA:
        if n == name:
            return first, last
    raise KeyError(name)


def rules():
    """rule name per probe: a function (record) -> None when the values are possible, else a text"""
    tab = {t[1]: t[4] for t in AP.analyse()[5]}
    pac_lo, _ = label_addr("PacShapeFull")
    _, pac_hi = label_addr("PacShapeDown2")
    gs_lo, _ = label_addr("GhostShapeUp")
    _, gs_hi = label_addr("GhostEyesShape")
    bi_lo, _ = label_addr("BonusItemCodes")
    score = set(tab["GhostScorePtrs"])
    junction = set(tab["JunctionRowPtrs"])
    route = set(tab["StartRoutePtrs"])
    R = {}
    R[0xA3B8] = lambda r: None if (r["src"], r["dst"]) == (0xA1E1, 0x0800) else "Start: the maze stream is SrcPtr $A1E1 -> DstPtr $0800"
    R[0xA668] = lambda r: None if 0xA000 <= r["src"] < 0xC000 and r["dst"] < 0x4000 else "ExpandData: pointers outside ROM -> RAM"
    R[0xA8DE] = lambda r: None if (r["src"] in score and r["pm"] >> 8 == 0x23 and 0x24 <= r["pp"] >> 8 <= 0x27 and (r["pm"] & 255) == (r["pp"] & 255) and abs((r["pm"] & 255) - r["py"]) <= 2) else "GhostEaten set-up"
    R[0xABBD] = lambda r: None if r["clip"] == ((0x2300 if r["x"] == 4 else (0x2400 + r["x"] * 256)) | 0x74) else "ClipEntityAtTunnel: ClipPtr is not page($23 | $24+entity) + $74"
    R[0xACC6] = lambda r: None if r["dst"] == 0x0F92 else "DrawLevelIndicator: DstPtr is not $0F92"
    R[0xACF9] = lambda r: None if bi_lo + 12 <= r["src"] <= bi_lo + 24 else "DrawLevelIndicator: SrcPtr outside BonusItemCodes+12..+24"
    for a in (0xAF29, 0xAF33, 0xAF41, 0xAF4C):
        R[a] = lambda r: None if r["dst"] >> 8 == 0x23 else "DeathAnimation: DstPtr not in the missile page"
    R[0xB301] = lambda r: None if pac_lo <= r["src"] <= pac_hi + 16 else "DrawAllInPlace: SrcPtr outside the Pac-Man shapes"
    R[0xB330] = lambda r: None if r["src"] == 0x0400 and r["dst"] >> 8 == 0x23 and r["dst"] & 255 == r["py"] else "DrawAllInPlace: SrcPtr / DstPtr"
    R[0xB358] = lambda r: None if 0x0C00 <= r["mz"] <= 0x0F97 and r["y"] == 0 else "EatDotAtPacMan: MazePtr outside $0C00-$0F97"
    R[0xB363] = R[0xB358]
    R[0xB384] = R[0xB358]
    R[0xB4D0] = lambda r: None if r["src"] in junction and r["y"] <= 9 else "JunctionLookup: SrcPtr not a JunctionRowPtrs entry, or Y > 9"
    R[0xB840] = lambda r: None if r["src"] in route and r["y"] <= 15 else "GhostStartRoute: SrcPtr not a StartRoutePtrs entry"
    R[0xB96A] = lambda r: None if gs_lo <= r["src"] <= gs_hi + 0x10 else "StepAndDrawEntity: SrcPtr outside the ghost shapes"
    # B98F is the loop of the shared tail of StepAndDrawEntity; InitDisplay2 also jumps into it ($A62F) with X = $81 left over from SetDisplayList: DstPtr high = $24 + $81 = $A5, a copy into ROM (ignored by the hardware)
    R[0xB98F] = lambda r: None if r["x"] == 0x81 and r["dst"] >> 8 == 0xA5 or (r["x"] <= 4 and r["src"] == 0x0410 and r["dst"] >> 8 == 0x24 + r["x"]) else "StepAndDrawEntity: SrcPtr / DstPtr"
    return R


def parse(path):
    recs = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE.match(line)
            if m:
                v = m.groups()
                r = {k: (int(x, 16) if k in ("s", "src", "dst", "mz", "clip", "pm", "pp") else int(x)) for k, x in zip(FIELDS, v)}
                recs.append(r)
    return recs


def sentinel(path):
    """True when the log has the SENT line of the sentinel tracepoint on Start ($A386) among its first lines: Altirra 4.40 prints the first tracepoint hit of a session with the state of the NEXT hit (OV-56)"""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if line.startswith("SENT f="):
                return True
            if i > 2000:
                break
    return False


def classify_delta(prev, cur):
    d = cur - prev
    if d == 0:
        return "same cell"
    if d in (1, -1):
        return "+-1 (sideways)"
    if d in (0x28, -0x28):
        return "+-$28 (a row)"
    if (cur & 255) in (0x8F, 0xB7) and abs(d) <= 0x30:
        return "tunnel wrap"
    if cur in (0x0E93, 0x0E94):
        return "reset to the start cell"
    return "other"


def summarise(paths):
    R = rules()
    out, total, bad = [], collections.Counter(), []
    seen = collections.defaultdict(lambda: collections.Counter())
    rng = {}
    mz_delta = collections.Counter()
    tail = collections.Counter()
    tail_vals = set()
    frames = {}
    for p in paths:
        name = os.path.basename(p)[len("pointers-"):-len(".txt")]
        recs = parse(p)
        frames[name] = max((r["f"] for r in recs), default=0)
        last_mz = None
        for r in recs:
            total[r["s"]] += 1
            seen[r["s"]][name] += 1
            why = R[r["s"]](r) if r["s"] in R else "no rule for the probe"
            if why:
                bad.append((name, r, why))
            if r["s"] == 0xB98F:
                tail["InitDisplay2 jump into the tail (X=$81, DstPtr=$A5xx, a copy into ROM)" if r["x"] == 0x81 else "StepAndDrawEntity (ghost)"] += 1
                if r["x"] == 0x81:
                    tail_vals.add((r["src"], r["dst"]))
            if r["s"] == 0xB358:
                if last_mz is not None:
                    mz_delta[classify_delta(last_mz, r["mz"])] += 1
                last_mz = r["mz"]
            for k in ("src", "dst", "mz", "clip", "pm", "pp"):
                if (r["s"], k) in {(0xA668, "src"), (0xA668, "dst"), (0xB358, "mz"), (0xB4D0, "src"), (0xB840, "src"), (0xB96A, "src"), (0xB98F, "dst"), (0xB301, "src"), (0xABBD, "clip"), (0xA8DE, "src"), (0xA8DE, "pm"), (0xA8DE, "pp"), (0xAF29, "dst"), (0xACF9, "src")}:
                    lo, hi = rng.get((r["s"], k), (0x10000, -1))
                    rng[(r["s"], k)] = (min(lo, r[k]), max(hi, r[k]))
    return total, seen, bad, rng, mz_delta, frames, tail, tail_vals


def report(paths):
    total, seen, bad, rng, mz_delta, frames, tail, tail_vals = summarise(paths)
    L = []
    P = L.append
    P("Pointer audit (tools/run_pointer_audit.ps1, tools/analyze_pointer_log.py): %d harness logs, %d frames in the longest, %d probe hits" % (len(frames), max(frames.values()) if frames else 0, sum(total.values())))
    for n in sorted(frames):
        P("  %-18s %d frames, %d hits" % (n, frames[n], sum(c[n] for c in seen.values())))
    P("")
    P("%-7s %-17s %10s  %s" % ("probe", "routine", "hits", "values seen"))
    ctx = AP.Ctx()
    for a in AP.PROBES:
        owner = ctx.F[ctx.owner[a]].name
        vals = []
        for (s, k), (lo, hi) in sorted(rng.items()):
            if s == a:
                vals.append("%s $%04X-$%04X" % (k, lo, hi) if lo != hi else "%s $%04X" % (k, lo))
        P("$%04X  %-17s %10d  %s" % (a, owner, total[a], "; ".join(vals) if vals else "(the rule: see tools/analyze_pointer_log.py)"))
    P("")
    P("Sentinel on Start (first tracepoint hit absorbed, OV-56): present in %d of %d logs" % (sum(1 for p in paths if sentinel(p)), len(paths)))
    unreached = [a for a in AP.PROBES if total[a] == 0]
    P("Probes never reached: %s" % (", ".join("$%04X" % a for a in unreached) if unreached else "none"))
    P("MazePtr between two cell checks (EatDotAtPacMan, $B358): %s" % ", ".join("%s %d" % (k, v) for k, v in sorted(mz_delta.items())))
    P("Probe $B98F: %s; the pointers at the InitDisplay2 entries: %s" % (", ".join("%s %d" % (k, v) for k, v in sorted(tail.items())), ", ".join("src $%04X dst $%04X" % t for t in sorted(tail_vals)) or "-"))
    P("Hits that break the rule of their probe: %d" % len(bad))
    for name, r, why in bad[:10]:
        P("  %s f=%d $%04X: %s %s" % (name, r["f"], r["s"], why, {k: "$%04X" % v for k, v in r.items() if k in ("src", "dst", "mz", "clip", "pm", "pp")}))
    return L, bad, unreached, mz_delta


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--write" in sys.argv:
        i = sys.argv.index("--write")
        out = sys.argv[i + 1]
        args = [a for a in args if a != out]
    paths = sorted(p for a in args for p in glob.glob(a))
    L, bad, unreached, mz = report(paths)
    txt = "\n".join(L) + "\n"
    if out:
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
