"""Stage 48: checks the Altirra structure traces of tools/run_structure_audit.ps1 against the structures of docs/30-structures.md.

Input: analysis/raw-logs/structures-<harness>.txt, with the lines
  IDX s=$XXXX x=N      X at an `array,x` instruction (before it executes)
  IB f=N <128 bytes>   the zero page $80-$FF at the RTS of InitBoard ($ADF0)
  RS f=N <32 bytes>    the zero page $20-$3F after the clear of the game restart ($A481)
Checks: (1) every IDX is inside its array (offset of the site + X < size of the array); (2) after InitBoard $80-$93 is ZeroPageInit80 except nothing, `MoveDelayCount` ($B5-$B9) is loaded
(the four ghost values equal, none 0), `GhostTimer`[1..3] ($CB-$CD) are the first window of HouseReleaseTimers (InitBoard calls SetReleaseTimers with Y = 0), and every other byte of $94-$FF is 0;
(3) after the restart clear $20-$3F is 0.
Usage: python -I tools/analyze_structures_log.py analysis/raw-logs/structures-*.txt [--write analysis/evidence-structures-summary.txt]
"""
import collections
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_structures as AST  # noqa: E402

ROOT = AST.ROOT
BASE = AST.BASE
LOADED = set(range(0x35, 0x3A)) | {0x4B, 0x4C, 0x4D}          # offsets from $80: MoveDelayCount $B5-$B9, GhostTimer[1..3] $CB-$CD


def site_table():
    rom, F, owner_fn, sites, probes, outside, callers, init, bulk = AST.analyse()
    var = AST.zp_vars()
    T = {}
    for name, lst in sites.items():
        first, size = var[name][0], var[name][1]
        for a, m, off, routine in lst:
            T[a] = (name, off, size, routine)
    return T, init, rom


def parse(path, T):
    rng = {}
    hits = collections.Counter()
    ib, rs = [], []
    unknown = 0
    frames = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            c = line[:2]
            if c == "ID" and line.startswith("IDX s=$"):
                try:
                    s = int(line[7:11], 16)
                    x = int(line[14:])
                except ValueError:
                    continue
                hits[s] += 1
                lo, hi = rng.get(s, (999, -1))
                rng[s] = (x if x < lo else lo, x if x > hi else hi)
            elif c == "IB" and line.startswith("IB f="):
                p = line.split()
                if len(p) == 130:
                    ib.append((int(p[1][2:]), [int(v, 16) for v in p[2:]]))
                    frames = max(frames, ib[-1][0])
            elif c == "RS" and line.startswith("RS f="):
                p = line.split()
                if len(p) == 34:
                    rs.append((int(p[1][2:]), [int(v, 16) for v in p[2:]]))
    return rng, hits, ib, rs, frames


def sentinel(path):
    """True when the log has the SENT line of the sentinel tracepoint on Start ($A386): Altirra 4.40 prints the first tracepoint hit of a session with the state of the NEXT hit (OV-56)"""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if line.startswith("SENT f="):
                return True
            if i > 2000:
                break
    return False


def report(paths):
    T, init, rom = site_table()
    names = [os.path.basename(p)[len("structures-"):-len(".txt")] for p in paths]
    hit_total = collections.Counter()
    maxx = {}
    bad_idx, bad_ib, bad_rs = [], [], []
    per = {}
    ib_n = rs_n = 0
    frames = {}
    release = [rom.data[0xBBF2 - BASE + i] for i in range(6)]
    for n, p in zip(names, paths):
        rng, hits, ib, rs, fr = parse(p, T)
        per[n] = (sum(hits.values()), len(ib), len(rs))
        frames[n] = fr
        for s, (lo, hi) in rng.items():
            hit_total[s] += hits[s]
            if s not in T:
                bad_idx.append((n, s, "site not in the probe list"))
                continue
            name, off, size, routine = T[s]
            a, b = maxx.get(name, (999, -1))
            maxx[name] = (min(a, lo), max(b, hi))
            if lo < 0 or hi + off > size - 1:
                bad_idx.append((n, s, "%s%+d,x with X %d..%d (size %d)" % (name, off, lo, hi, size)))
        for f, v in ib:
            ib_n += 1
            why = []
            if v[:20] != init:
                why.append("$80-$93 differs from ZeroPageInit80")
            ghosts = v[0x35:0x39]
            if len(set(ghosts)) != 1 or ghosts[0] == 0 or v[0x39] == 0:
                why.append("MoveDelayCount not loaded: %s %02X" % (ghosts, v[0x39]))
            if v[0x4B:0x4E] != [release[2], release[1], release[0]]:
                why.append("GhostTimer[1..3] = %s, not the first window of HouseReleaseTimers" % v[0x4B:0x4E])
            for i in range(20, 128):
                if i not in LOADED and v[i] != 0:
                    why.append("$%02X = $%02X, not 0" % (0x80 + i, v[i]))
            if why:
                bad_ib.append((n, f, "; ".join(why[:3])))
        for f, v in rs:
            rs_n += 1
            nz = [(0x20 + i, x) for i, x in enumerate(v) if x]
            if nz:
                bad_rs.append((n, f, ", ".join("$%02X=$%02X" % t for t in nz)))
    L = []
    P = L.append
    P("Structure audit (tools/run_structure_audit.ps1, tools/analyze_structures_log.py): %d harness logs, %d index hits at %d sites, %d InitBoard snapshots, %d restart snapshots" % (len(names), sum(hit_total.values()), len(hit_total), ib_n, rs_n))
    for n in names:
        P("  %-18s %9d index hits, %3d InitBoard, %3d restart, last frame seen %d" % (n, per[n][0], per[n][1], per[n][2], frames[n]))
    P("")
    P("%-16s %5s %7s %s" % ("array", "size", "sites", "X seen (min..max) over all sites"))
    var = AST.zp_vars()
    cnt = collections.Counter(v[0] for v in T.values())
    for name in sorted(maxx, key=lambda nme: var[nme][0]):
        P("%-16s %5d %7d %d..%d" % (name, var[name][1], cnt[name], maxx[name][0], maxx[name][1]))
    P("")
    P("Sentinel on Start (first tracepoint hit absorbed, OV-56): present in %d of %d logs" % (sum(1 for p in paths if sentinel(p)), len(paths)))
    never = sorted(s for s in T if hit_total[s] == 0)
    P("Index sites never reached: %d of %d%s" % (len(never), len(T), (" (" + ", ".join("$%04X" % s for s in never) + ")") if never else ""))
    P("Index accesses outside their array: %d" % len(bad_idx))
    for t in bad_idx[:8]:
        P("  %s $%04X: %s" % t)
    P("InitBoard snapshots that differ from the model (start positions, loaded MoveDelayCount and GhostTimer[1..3], zero elsewhere): %d of %d" % (len(bad_ib), ib_n))
    for t in bad_ib[:8]:
        P("  %s f=%d: %s" % t)
    P("Restart snapshots with a non-zero byte in $20-$3F: %d of %d" % (len(bad_rs), rs_n))
    for t in bad_rs[:8]:
        P("  %s f=%d: %s" % t)
    return L, bad_idx, bad_ib, bad_rs, never


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        args = [a for a in args if a != out]
    paths = sorted(p for a in args for p in glob.glob(a))
    L = report(paths)[0]
    txt = "\n".join(L) + "\n"
    if out:
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
