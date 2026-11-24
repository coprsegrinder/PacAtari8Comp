r"""OV-68: the collision registers of the real GTIA against the model of tools/gtia_collisions.py, on random scenes (the logs of tools/altirra_collide.cmd, analysis/raw-logs/collide-s<N>.txt).
Each log holds the static data of the screen (the maze cells `$0C00`, the character set `$3000`) once, then for every installed scene a record: the sixteen collision registers read by the CPU (the overlaps of the PREVIOUS scene, shown
for three frames), the scene (eight positions, five first rows, five densities, 5 x 16 picture rows) and the number of the scene.  Checked:
  1. integrity: the scene of every record equals the scene the stub's random generator makes (tools/collide_stub.s run on the concrete 6502 from the run's seed): the records are not corrupted, whatever the machine did;
  2. the model: for every record from the third scene on, collision_registers(previous scene) equals the registers read.
Usage: python -I tools/analyze_collide.py analysis/raw-logs/collide-s*.txt [--write analysis/evidence-collide-summary.txt]"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import cpu6502 as C  # noqa: E402
import gtia_collisions as G  # noqa: E402
import make_collide_cmd as M  # noqa: E402

LINE = re.compile(r"^([0-9A-F]{4}): ((?:[0-9A-F]{2} ){1,16})")


def parse(path):
    """-> (static dumps {address: byte}, records [dict])"""
    mem = {}
    recs = []
    cur = None
    with open(path, encoding="latin-1") as fh:
        for ln in fh:
            m = LINE.match(ln)
            if not m:
                continue
            a = int(m.group(1), 16)
            data = bytes.fromhex(m.group(2).replace(" ", ""))
            if 0x4100 <= a <= 0x41A0:
                if a == 0x4100:
                    if cur:
                        recs.append(cur)
                    cur = {}
                if cur is not None:
                    for k, v in enumerate(data):
                        cur[a + k] = v
            elif not 0x4000 <= a <= 0x43FF:
                for k, v in enumerate(data):
                    mem[a + k] = v
    if cur:
        recs.append(cur)
    out = []
    for r in recs:
        if 0x41A0 not in r or 0x41A1 not in r or 0x41A2 not in r or any(0x4100 + k not in r for k in range(0x90)):
            continue                                            # a record cut by the end of the log
        out.append({"regs": [r[0x4100 + k] for k in range(16)], "scene": bytes(r[0x4110 + k] for k in range(0x80)), "valid": r[0x41A0], "count": r[0x41A1] | r[0x41A2] << 8})
    return mem, out


def stub_scenes(seed, n, mode=0):
    """the scenes the stub makes from `seed`: {count: 128 bytes of the record's scene area} for counts 1..n"""
    code, done = M.assemble()
    with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
        m = C.Machine(fh.read())
    m.mem[M.ORG:M.ORG + len(code)] = code
    m.mem[0x4084], m.mem[0x4085] = seed & 255, seed >> 8
    m.mem[0x4086] = mode
    out = {}
    for _ in range(n + 1):
        m.call(M.ORG, until=done, limit=2000000)
        c = m.mem[0x41A1] | m.mem[0x41A2] << 8
        if c:
            out[c] = bytes(m.mem[0x4110:0x4190])
    return out


def scene_of(blob):
    hpos = list(blob[0:8])
    rows = list(blob[8:13])
    pats = [list(blob[0x20 + 16 * i:0x30 + 16 * i]) for i in range(5)]
    return hpos, rows, pats


def playfield_of(mem):
    cells = [mem[0x0C00 + i] for i in range(G.MAZE_ROWS * G.MAZE_COLS)]
    charset = bytes(mem[0x3000 + i] for i in range(1024))
    return G.Playfield(cells, charset)


def analyse(path, seed, model=None, mode=0):
    """-> dict of results for one log"""
    model = model or G.collision_registers
    mem, recs = parse(path)
    pf = playfield_of(mem)
    scenes = stub_scenes(seed, max([r["count"] for r in recs] + [0]), mode)
    res = {"records": len(recs), "integrity_bad": [], "compared": 0, "bad": [], "bits": Counter(), "bits_total": Counter(), "nonzero_regs": Counter(), "counts": [r["count"] for r in recs], "distinct": set()}
    # the records must be consecutive: the registers of record c belong to the scene of record c - 1
    by_count = {r["count"]: r for r in recs if r["valid"] or r["count"] > 1}
    for r in recs:
        if scenes.get(r["count"]) != r["scene"]:
            res["integrity_bad"].append(r["count"])
    for r in recs:
        c = r["count"]
        if c < 3 or (c - 1) not in by_count or c - 1 in res["integrity_bad"] or c in res["integrity_bad"]:
            continue
        hpos, rows, pats = scene_of(by_count[c - 1]["scene"])
        mp, pp = G.scene_pages(rows, pats)
        want = model(hpos, mp, pp, pf)
        got = r["regs"]
        idx = list(range(16))
        if mode & 4:                                            # rows anywhere in the pages: the model is exact where it models the screen: the objects in the maze band for the playfield registers, the rows from 32 on for the
            idx = (list(range(8, 16)) if min(rows) >= 32 else []) + (list(range(8)) if all(40 <= r_ and r_ + 15 <= 223 for r_ in rows) else [])     # player and missile registers (above that the stub's own install is still running as the beam passes)
            if not idx:
                continue
        res["compared"] += 1
        res["distinct"].add(by_count[c - 1]["scene"])
        for i in range(16):
            for b in range(4):
                res["bits_total"][(i, b)] += 1
                if got[i] >> b & 1:
                    res["bits"][(i, b)] += 1
            if got[i]:
                res["nonzero_regs"][i] += 1
        if any(want[i] != got[i] for i in idx):
            res["bad"].append((c - 1, hpos, rows, want, got))
    return res


NAMES = ["M0PF", "M1PF", "M2PF", "M3PF", "P0PF", "P1PF", "P2PF", "P3PF", "M0PL", "M1PL", "M2PL", "M3PL", "P0PL", "P1PL", "P2PL", "P3PL"]


def run_of(path):
    return int(re.search(r"collide-s(\d+)", os.path.basename(path)).group(1))


def seed_of(path):
    return M.SEEDS[run_of(path)]


def summary(paths):
    L = ["Collision registers of the real GTIA against the model of tools/gtia_collisions.py (tools/altirra_collide.cmd, tools/analyze_collide.py, OV-68)", ""]
    total = Counter()
    distinct = set()
    allbits = Counter()
    nz = Counter()
    bad_all = []
    for p in paths:
        r = analyse(p, seed_of(p), mode=M.MODES.get(run_of(p), 0))
        L.append("%s: %d records (scenes %d-%d), %d differ from the stub's generator (integrity), %d scenes compared with the model (%d distinct): %d differences" % (
            os.path.basename(p), r["records"], min(r["counts"]), max(r["counts"]), len(r["integrity_bad"]), r["compared"], len(r["distinct"]), len(r["bad"])))
        distinct |= r["distinct"]
        total["records"] += r["records"]
        total["compared"] += r["compared"]
        total["bad"] += len(r["bad"])
        total["integrity"] += len(r["integrity_bad"])
        allbits.update(r["bits"])
        nz.update(r["nonzero_regs"])
        bad_all += r["bad"]
        for b in r["bad"][:3]:
            L.append("  scene %d: hpos %s rows %s: model %s, hardware %s" % (b[0], b[1], b[2], b[3], b[4]))
    L.append("")
    L.append("total: %d scenes compared, %d differences (%d records differ from the generator); %d distinct scenes" % (total["compared"], total["bad"], total["integrity"], len(distinct)))
    L.append("")
    L.append("coverage (scenes in which each register bit was set / not set in the hardware, of %d):" % total["compared"])
    L.append("register " + " ".join("bit%d".rjust(8) % b for b in range(4)))
    for i in range(16):
        L.append("%-8s " % NAMES[i] + " ".join(("%d/%d" % (allbits[(i, b)], total["compared"] - allbits[(i, b)])).rjust(8) for b in range(4)))
    return L, total, bad_all


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# the real game in play (tools/run_collide_play_audit.ps1)
GRACTL = re.compile(r"^GRACTL: ([0-9A-F]{2})")
POS = re.compile(r"^(Player|Missile)\s+(\d): color = ([0-9A-F]{2}), pos = ([0-9A-F]{2})")


def parse_play(path):
    """-> list of frames {hpos, regs, pages, screen}; a frame starts at the debugger's `.gtia` line `Player  0`"""
    frames = []
    cur = None
    entries = 0                                                 # the handler entries seen (the `FR` lines); a `HC` line (an executed `sta HITCLR`) and the `HE` line (the end of the handler) belong to the latest one
    hc = {}
    info = {}
    with open(path, encoding="latin-1") as fh:
        for ln in fh:
            if ln.startswith("FR f="):
                m = re.match(r"FR f=(\d+) vp=(\d+)", ln)
                if not m:
                    continue                                    # a line cut by the end of the log
                entries += 1
                info[entries - 1] = {"f": int(m.group(1)), "vp": int(m.group(2)), "end": None, "hc": []}
                continue
            if ln.startswith("HE f=") and entries:
                m = re.match(r"HE f=(\d+) vp=(\d+)", ln)
                if not m:
                    continue
                info[entries - 1]["end"] = (int(m.group(1)), int(m.group(2)))
                continue
            if ln.startswith("HC site=") and entries:
                m = re.search(r"f=(\d+) vp=(\d+)", ln)
                if not m:
                    continue
                hc[entries - 1] = True
                info[entries - 1]["hc"].append((int(m.group(1)), int(m.group(2))))
                continue
            m = POS.match(ln)
            if m:
                if m.group(1) == "Player" and m.group(2) == "0":
                    if cur:
                        frames.append(cur)
                    cur = {"hpos": [0] * 8, "regs": None, "mem": {}, "gractl": 0}
                if cur is not None:
                    cur["hpos"][int(m.group(2)) + (0 if m.group(1) == "Player" else 4)] = int(m.group(4), 16)
                continue
            m = GRACTL.match(ln)
            if m and cur is not None:
                cur["gractl"] = int(m.group(1), 16)
                continue
            m = LINE.match(ln)
            if m and cur is not None:
                a = int(m.group(1), 16)
                data = bytes.fromhex(m.group(2).replace(" ", ""))
                if a == 0xD000:
                    cur["regs"] = list(data)
                else:
                    for k, v in enumerate(data):
                        cur["mem"][a + k] = v
    if cur:
        frames.append(cur)
    out = []
    for i, f in enumerate(frames):
        mem = f["mem"]
        f["hc"] = hc.get(i, False)
        f["info"] = info.get(i)
        if f["regs"] is None or len(f["regs"]) < 16 or any(a not in mem for a in range(0x2300, 0x2800)) or any(a not in mem for a in range(0x0C00, 0x0C00 + 920)):
            continue                                            # a frame cut by the end of the log
        out.append({"info": f["info"], "hc": f["hc"], "gractl": f["gractl"], "hpos": f["hpos"], "regs": f["regs"][:16], "pages": [[mem[0x2300 + 256 * i + k] for k in range(256)] for i in range(5)], "cells": [mem[0x0C00 + k] for k in range(920)], "state": mem.get(0xED, 0)})
    return out


def rom_charset():
    import decode_streams as S
    g, _ = S.decode_b(0xA003)
    return bytes(g) + bytes(1024 - len(g))


BEAM_LIMIT = 40                                                  # the first scan line at which an object can be (the maze starts at line 40)


def overran(f):
    """did the handler of this entry still run when the beam reached the objects?  Its end, or a HITCLR, falls in a LATER frame than its entry at a scan line from BEAM_LIMIT on: the pictures and positions were changed in the middle of the display (collisions of the lines before that are of the old scene, HITCLR drops the collisions of the lines before it)"""
    i = f.get("info")
    if not i or i["end"] is None:
        return True                                                 # no end seen: unknown
    if i["end"][0] > i["f"] and i["end"][1] >= BEAM_LIMIT:
        return True
    return any(ff > i["f"] and vp >= BEAM_LIMIT for ff, vp in i["hc"])


def analyse_play(path, model=None):
    """the registers latch every overlap shown since the last HITCLR: A[i] = (0 if a HITCLR ran in handler i - 1, else A[i - 1]) | model(scene i), where scene i is what the entry of handler i finds on the screen (shown in the frame
    before) and A[i] is what the game reads there; the chain starts at the first HITCLR of the log and is carried by the MODEL, not by the hardware's earlier values"""
    model = model or G.collision_registers
    frames = parse_play(path)
    cs = rom_charset()
    res = {"frames": len(frames), "bad": [], "compared": 0, "bits": Counter(), "nonzero": Counter(), "skipped": 0, "carried": 0, "hitclr": sum(1 for f in frames if f["hc"]), "late": 0, "late_bad": []}
    prev = None
    for i, f in enumerate(frames):
        if f["gractl"] & 3 != 3:
            prev = None
            res["skipped"] += 1                                 # the players and missiles are not enabled yet (the title, the start-up): nothing is shown, nothing collides
            continue
        pf = G.Playfield(f["cells"], cs)
        shown = model(f["hpos"], f["pages"][0], f["pages"][1:], pf)
        if i > 0 and frames[i - 1]["hc"]:
            want = shown
        elif prev is not None:
            want = [a | b for a, b in zip(prev, shown)]
            res["carried"] += 1
        else:
            prev = None
            continue                                            # before the first HITCLR of the log the history is unknown
        prev = want
        got = f["regs"]
        late = i > 0 and overran(frames[i - 1])
        if late:
            res["late"] += 1
            if want != got:
                res["late_bad"].append((f["hpos"], want, got, f["state"]))
            prev = got
            continue
        res["compared"] += 1
        for k in range(16):
            if got[k]:
                res["nonzero"][k] += 1
            for b in range(4):
                if got[k] >> b & 1:
                    res["bits"][(k, b)] += 1
        if want != got:
            res["bad"].append((f["hpos"], want, got, f["state"]))
            prev = got                                          # do not let one difference spoil the frames after it
    return res


def play_summary(paths):
    L = ["The collision registers of the real game in play against the model (tools/run_collide_play_audit.ps1, tools/analyze_collide.py --play, OV-68): at the entry of the frame handler of every frame, the scene of the frame before (the GTIA positions, the player-missile pages, the maze screen) and the registers the game reads", ""]
    tot = Counter()
    bits = Counter()
    nz = Counter()
    for p in paths:
        r = analyse_play(p)
        L.append("%s: %d frames, %d HITCLRs; %d frames compared with the model (%d of them with registers carried over from the frame before, no HITCLR in between): %d differences; %d frames after a handler that overran into the objects' lines (set aside): %d of them differ" % (
            os.path.basename(p), r["frames"], r["hitclr"], r["compared"], r["carried"], len(r["bad"]), r["late"], len(r["late_bad"])))
        for b in r["bad"][:3]:
            L.append("  hpos %s: model %s, hardware %s (DeathState %d)" % b)
        tot["frames"] += r["compared"]
        tot["carried"] += r["carried"]
        tot["late"] += r["late"]
        tot["late_bad"] += len(r["late_bad"])
        tot["bad"] += len(r["bad"])
        bits.update(r["bits"])
        nz.update(r["nonzero"])
    L.append("")
    L.append("total: %d frames compared, %d differences (%d frames with registers carried over); %d further frames follow a handler that was still running when the beam reached the objects, %d of them differ (%.1f%%)" % (
        tot["frames"], tot["bad"], tot["carried"], tot["late"], tot["late_bad"], 100.0 * tot["late_bad"] / max(1, tot["late"])))
    L.append("frames in which the register was not zero in the hardware: " + ", ".join("%s %d" % (NAMES[i], nz[i]) for i in range(16)))
    L.append("the three registers of the game: M1PL %d (bits: %s), M2PL %d (%s), M2PF %d (%s)" % (
        nz[9], " ".join("%d" % bits[(9, b)] for b in range(4)), nz[10], " ".join("%d" % bits[(10, b)] for b in range(4)), nz[2], " ".join("%d" % bits[(2, b)] for b in range(4))))
    return L, tot


def main():
    if "--play" in sys.argv:
        pp = sorted(p for p in sys.argv[1:] if not p.startswith("--") and os.path.exists(p) and "collideplay" in p)
        L, tot = play_summary(pp)
        txt = "\n".join(L) + "\n"
        if "--write" in sys.argv:
            with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(txt)
        print(txt)
        return 1 if tot["bad"] else 0
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and (sys.argv.index(a) < 2 or sys.argv[sys.argv.index(a) - 1] != "--write")]
    paths = sorted(p for p in paths if os.path.exists(p))
    L, total, bad = summary(paths)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if total["bad"] or total["integrity"] else 0


if __name__ == "__main__":
    sys.exit(main())
