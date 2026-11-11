"""Pac-Man's own pictures and the death sequence (Pac-Man frames, the ghosts during the death). Checks the log of tools\\altirra_death.cmd (a real game, Pac-Man is killed by the ghosts).
Code (docs/12, docs/20): MovePacMan ($B179) picks a picture (Y = index into PacShapePtrs, X = byte offset 0 or 10), stages its 10 rows at $0403 and copies 16 rows to the missile memory $2300+PacY.
The death: $A923 -> DeathState 1, zp_EE = $60; DeathSequence ($AE3D) + DeathAnimation ($AEF7) run once per frame from $A82F while DeathState <> 0.
This analyzer (1) checks every Pac-Man picture against the ROM shape that Y/X select and against the direction rule, (2) runs a software model of DeathSequence/DeathAnimation, built from the code, against the
per-frame variables of every logged death, (3) checks what the four ghosts do during the death (frozen, redrawn with the feet toggling, then hidden by HPOSP = 0, never redrawn).
Usage: python -I tools/analyze_death_log.py <log> [--summary-file out]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

rd = S.rd
PTRS = [rd(0xBB65 + 2 * i) | rd(0xBB66 + 2 * i) << 8 for i in range(5)]
NAMES = {0: "Full", 2: "Right", 4: "Left", 6: "Up", 8: "Down"}
DIR_Y = {1: 6, 2: 8, 4: 4, 8: 2}         # PacDirection (STICK bits: 1 up, 2 down, 4 left, 8 right) -> index into PacShapePtrs
PLOT_BYTES = [rd(0xBB57 + i) for i in range(14)]
STAR = [rd(0xBC07 + i) for i in range(16)]
UP2 = [rd(0xBB38 + i) for i in range(10)]

RE_DF = re.compile(r"DF f=(\d+) ds=(\d+) ee=(\d+) da=(\d+) daf=(\d+) dad=(\d+) z24=(\d+) f0=(\d+) ef=(\d+) f1=(\d+) lives=(\d+),(\d+) px=(\d+) py=(\d+)")
RE_SEL = re.compile(r"PACSEL y=(\d+) off=(\d+) dir=(\d+) chomp=(\d+) pause=(\d+) f=(\d+)")
RE_DRAW = re.compile(r"PACDRAW px=(\d+) py=(\d+) shape=([0-9A-F]{20}) rows=([0-9A-F]{20}) f=(\d+)")
RE_START = re.compile(r"DEATH_START ghost=(\d) gst=\$(..),\$(..),\$(..),\$(..) gx=(\d+),(\d+),(\d+),(\d+) gy=(\d+),(\d+),(\d+),(\d+) px=(\d+) py=(\d+) pdir=(\d+) chomp=(\d+) f=(\d+)")
RE_FG = re.compile(r"FREEZE_GHOST g=(\d) dir=(\d+) st=\$(..) x=(\d+) y=(\d+) f=(\d+)")
RE_GD = re.compile(r"GDRAW g=(\d) src=\$([0-9A-F]{4}) feet=\$([0-9A-F]{2}) st=\$(..) f=(\d+)")
RE_EV = re.compile(r"^(GHOST_HPOS_ZERO g=(\d)|ANIM_ON|ANIM_FRAME0|ANIM_STAR|ANIM_END|DEATH_DONE|ANIM_PLOT idx=(\d+) row=(\d+) byte=\$(..)|FREEZE_LEG af=(\d+) ee=(\d+)).* f=(\d+)")


def model_audf(v):
    """The AUDF1 write made by DeathSequence in the frame that starts with variables v: (state, value) or None. State 3 and 4 write the old zp_F0, state 5 the old zp_EF; state 2 falls into the state-3 code with zp_F0 = $35."""
    if v["ds"] == 1 and v["ee"] != 0:
        return None
    ds = 2 if v["ds"] == 1 else v["ds"]
    if ds == 2:
        return (3, 0x35)
    if ds == 3:
        return (3, v["f0"])
    if ds == 4:
        return (4, v["f0"])
    if ds == 5:
        return (5, v["ef"])
    return None


def model_step(v):
    """One main-step frame of DeathSequence then DeathAnimation, translated from $AE3D-$AF53. v: dict of ds ee da daf dad z24 f0 ef f1. Returns the new dict and the picture drawn (or None)."""
    v = dict(v)
    draw = None
    ds = v["ds"]
    went = False

    def sound_up():
        v["f0"] = (v["f0"] + 8) & 0xFF
        v["f1"] = (v["f1"] + 1) & 0xFF
        if v["f1"] == 4:
            v["ds"] = 4

    if ds == 1:
        if v["ee"] != 0:
            v["ee"] -= 1
            went = True
        else:
            v["ds"] = ds = 2
    if not went:
        if ds == 2:
            v["f0"] = v["ef"] = 0x35
            v["f1"] = 0
            v["daf"] = 0
            v["da"] += 1
            v["dad"] = 7
            v["ds"] = 3
            sound_up()
        elif ds == 4:
            v["f0"] = (v["f0"] - 8) & 0xFF
            v["f1"] = (v["f1"] - 1) & 0xFF
            if v["f1"] == 0:
                if v["ef"] == 0x6D:
                    v["ds"] = 5
                else:
                    v["ef"] += 4
                    v["f0"] = v["ef"]
                    v["ds"] = 3
        elif ds == 5:
            v["ef"] = (v["ef"] - 8) & 0xFF
            if v["ef"] == 0x25:
                v["f1"] = 0x80
                v["ds"] = 6
        elif ds == 6:
            if v["f1"] == 0:
                v["z24"] += 1
            else:
                v["f1"] -= 1
        else:                                   # ds == 3
            sound_up()
    # DeathAnimation
    if v["da"] != 0:
        if v["dad"] != 0:
            v["dad"] -= 1
        else:
            if v["daf"] == 0x0F:
                v["da"] = 0
                return v, "end"
            v["daf"] += 1
            v["dad"] = 7
        draw = v["daf"]
    return v, draw


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    df, starts, fg, gd, evs, sels, draws_after_sel = [], [], [], [], [], [], []
    last_sel = None
    after_anim = False
    late_draws = 0
    cur_audf = None
    all_audf = []
    for line in open(path, errors="replace"):
        line = line.rstrip("\n")
        if line.startswith("DEATH_START"):
            after_anim = False
            cur_audf = []
        elif line.startswith("ANIM_ON"):
            after_anim = True
        elif line.startswith("DEATH_DONE"):
            after_anim = False
            if cur_audf is not None:
                all_audf.append(cur_audf)
                cur_audf = None
        elif line.startswith("GDRAW") and after_anim:
            late_draws += 1
        elif line.startswith("AUDF1") and cur_audf is not None:
            mm = re.match(r"AUDF1 st=(\d) val=(\d+) f=(\d+)", line)
            cur_audf.append((int(mm.group(1)), int(mm.group(2))))
        m = RE_DF.match(line)
        if m:
            g = list(map(int, m.groups()))
            df.append(dict(f=g[0], ds=g[1], ee=g[2], da=g[3], daf=g[4], dad=g[5], z24=g[6], f0=g[7], ef=g[8], f1=g[9], lives=(g[10], g[11]), px=g[12], py=g[13]))
            last_sel = None
            continue
        m = RE_SEL.match(line)
        if m:
            last_sel = tuple(map(int, m.groups()))
            sels.append(last_sel)
            continue
        m = RE_DRAW.match(line)
        if m:
            if last_sel is not None:
                draws_after_sel.append((last_sel, int(m.group(1)), int(m.group(2)), m.group(3), m.group(4), int(m.group(5))))
            last_sel = None
            continue
        m = RE_START.match(line)
        if m:
            g = m.groups()
            starts.append(dict(ghost=int(g[0]), st=[int(g[i], 16) for i in range(1, 5)], gx=list(map(int, g[5:9])), gy=list(map(int, g[9:13])), px=int(g[13]), py=int(g[14]), pdir=int(g[15]), f=int(g[17])))
            continue
        m = RE_FG.match(line)
        if m:
            fg.append(dict(g=int(m.group(1)), dir=int(m.group(2)), st=int(m.group(3), 16), x=int(m.group(4)), y=int(m.group(5)), f=int(m.group(6))))
            continue
        m = RE_GD.match(line)
        if m:
            gd.append(dict(g=int(m.group(1)), src=int(m.group(2), 16), feet=int(m.group(3), 16), st=int(m.group(4), 16), f=int(m.group(5))))
            continue
        m = RE_EV.match(line)
        if m:
            name = line.split()[0]
            fr = int(m.group(m.lastindex))
            evs.append((name, fr, line))
    cnt = collections.Counter()
    bad = collections.defaultdict(list)

    # ---------- 1. Pac-Man's pictures ----------
    P("PART 1 - Pac-Man's pictures: %d draws (a selection followed by the copy to missile memory)" % len(draws_after_sel))
    table = collections.Counter()
    seq = []
    for (y, off, d, chomp, pause, fsel), px, py, shape, rows, f in draws_after_sel:
        want = bytes(rd(PTRS[y // 2] + off + i) for i in range(10)).hex().upper()
        if y not in NAMES:
            bad["picture index not 0/2/4/6/8"].append((y, off, f))
            continue
        cnt["draws"] += 1
        if shape != want:
            bad["staged bytes differ from the ROM shape selected by Y/X"].append((y, off, shape, want, f))
        else:
            cnt["staged bytes == ROM shape (PacShapePtrs[Y] + X)"] += 1
        if rows != shape:
            bad["missile memory rows differ from the staged shape"].append((rows, shape, f))
        else:
            cnt["missile memory rows ($2300+PacY+3..+12) == staged shape"] += 1
        table[(NAMES[y], off, d)] += 1
        seq.append((y, off, d, chomp, f))
    P("  picture chosen by (shape, byte offset, PacDirection) - counts:")
    for k in sorted(table):
        P("    %-6s offset %2d direction %2d : %d" % (k[0], k[1], k[2], table[k]))
    # rule: offsets only 0 or 10; Full only with offset 0; a direction shape is the one of PacDirection
    for y, off, d, chomp, f in seq:
        if off not in (0, 10):
            bad["offset not 0/10"].append((y, off, f))
        if y == 0 and off != 0:
            bad["Full with an offset"].append((y, off, f))
        if y != 0 and d in DIR_Y and y != DIR_Y[d]:
            bad["direction shape does not match PacDirection"].append((y, d, f))
    cnt["direction shapes whose index matches PacDirection (up 6, down 8, left 4, right 2)"] = sum(1 for y, off, d, c, f in seq if y != 0 and d in DIR_Y and y == DIR_Y[d])
    # mouth cycle on consecutive moving draws: ChompPhase after the call versus offsets
    by_chomp = collections.defaultdict(collections.Counter)
    for y, off, d, chomp, f in seq:
        by_chomp[chomp][("Full" if y == 0 else "dir", off)] += 1
    P("  ChompPhase ($AB) at the selection -> (kind, offset):", {k: dict(v) for k, v in sorted(by_chomp.items())})
    # the cycle: look at runs of consecutive draws of a moving Pac-Man (chomp 1,2,3 phases)
    cyc = collections.Counter()
    prev = None
    for y, off, d, chomp, f in seq:
        kind = "full" if y == 0 else ("f1" if off == 0 else "f2")
        if prev is not None:
            cyc[(prev, kind)] += 1
        prev = kind
    P("  consecutive pictures (previous -> next) - counts:", dict(sorted(cyc.items())))

    # ---------- 2. the death sequence against the model ----------
    P()
    P("PART 2 - the death sequence: %d deaths (DEATH_START), %d frames logged" % (len(starts), len(df)))
    byf = {r["f"]: r for r in df}
    deaths = []
    cur = []
    for r in df:
        if r["ds"] != 0:
            cur.append(r)
        elif cur:
            deaths.append(cur)
            cur = []
    if cur:
        deaths.append(cur)
    P("  %d runs of frames with DeathState <> 0" % len(deaths))
    lens = collections.Counter()
    checked = mism = 0
    phases = collections.Counter()
    full_runs = 0
    drawn_frames = collections.Counter()
    for run in deaths:
        # model starts from the first logged frame of the death (ds = 1, ee = $60)
        v = dict(ds=run[0]["ds"], ee=run[0]["ee"], da=run[0]["da"], daf=run[0]["daf"], dad=run[0]["dad"], z24=run[0]["z24"], f0=run[0]["f0"], ef=run[0]["ef"], f1=run[0]["f1"])
        ok_run = run[0]["ds"] == 1 and run[0]["ee"] == 0x60 and run[0]["da"] == 0 and run[0]["z24"] == 0
        if not ok_run:
            bad["first frame of a death is not DeathState 1, zp_EE $60"].append(run[0])
            continue
        full_runs += 1
        for a, b in zip(run, run[1:]):
            if a["z24"] != 0:
                break
            v, drawn = model_step(v)
            checked += 1
            got = dict(ds=b["ds"], ee=b["ee"], da=b["da"], daf=b["daf"], dad=b["dad"], z24=b["z24"], f0=b["f0"], ef=b["ef"], f1=b["f1"])
            if got != v:
                mism += 1
                bad["model differs from the logged variables"].append((a["f"], v, got))
                break
        # lengths
        first_z24 = next((i for i, r in enumerate(run) if r["z24"] != 0), None)
        lens[(len(run), first_z24)] += 1
        for r in run:
            phases[r["ds"]] += 1
    P("  model checks (one per frame, all variables: DeathState, zp_EE, DeathAnimActive/Frame/Delay, zp_F0/EF/F1, zp_24):", checked, " mismatches:", mism, " full deaths compared:", full_runs)
    P("  frames spent in each DeathState over all deaths (state -> frames):", dict(sorted(phases.items())))
    P("  (frames with DeathState <> 0, index of the frame where zp_24 first became non-zero) -> number of deaths:", dict(sorted(lens.items())))
    # one model run: durations per state
    v = dict(ds=1, ee=0x60, da=0, daf=0, dad=0, z24=0, f0=0, ef=0, f1=0)
    dur = collections.Counter()
    n = 0
    anim = {}
    while v["z24"] == 0 and n < 2000:
        dur[v["ds"]] += 1
        v, drawn = model_step(v)
        n += 1
        if drawn is not None:
            anim.setdefault(drawn, 0)
            anim[drawn] += 1
    P("  model: frames in state 1,2,3,4,5,6 until zp_24 is set:", dict(sorted(dur.items())), " total", n, "frames")
    P("  model: DeathAnimation draws per animation frame (0 = PacShapeUp2, 1-14 = DeathPlotBytes, 15 = StarShape, 'end' = rows cleared):", dict(anim) if 'end' not in anim else dict(anim))

    # ---------- the animation events ----------
    plots = collections.Counter()
    for name, fr, line in evs:
        if name == "ANIM_PLOT":
            m = re.search(r"idx=(\d+) row=(\d+) byte=\$(..)", line)
            idx, row, byte = int(m.group(1)), int(m.group(2)), int(m.group(3), 16)
            plots[idx] += 1
            if byte != PLOT_BYTES[idx]:
                bad["plotted byte differs from DeathPlotBytes"].append(line)
    # AUDF1 writes: the model's sequence against the writes logged in every death
    exp_audf = []
    v = dict(ds=1, ee=0x60, da=0, daf=0, dad=0, z24=0, f0=0, ef=0, f1=0)
    n = 0
    while v["z24"] == 0 and n < 2000:
        w = model_audf(v)
        if w:
            exp_audf.append(w)
        v, _ = model_step(v)
        n += 1
    same = sum(1 for d in all_audf if d == exp_audf)
    P("  AUDF1 writes (sound frequency) per death: model %d writes; deaths logged %d, with exactly the model's sequence: %d" % (len(exp_audf), len(all_audf), same))
    P("  AUDF1 model sequence, first 24 (state, value):", exp_audf[:24])
    if same != len(all_audf):
        bad["AUDF1 write sequence differs from the model"].append(next((d[:14] for d in all_audf if d != exp_audf), None))
    P("  ANIM_PLOT: draws per DeathPlotBytes index (each death: 8 per index):", dict(sorted(plots.items())))
    P("  events:", dict(collections.Counter(n for n, _, _ in evs)))

    # ---------- 3. the ghosts during the death ----------
    P()
    P("PART 3 - the ghosts during the death")
    frames_of_death = []
    for d in starts:
        frames_of_death.append(d["f"])
    # group FREEZE_GHOST by death: the frames of one freeze are consecutive
    freeze_frames = sorted({r["f"] for r in fg})
    hpos = [(n, fr) for n, fr, _ in evs if n == "GHOST_HPOS_ZERO"]
    P("  freeze: %d ghost redraws in %d frames (4 per frame); HPOSP0-3 := 0 events: %d (4 per death)" % (len(fg), len(freeze_frames), len(hpos)))
    per_frame = collections.Counter(r["f"] for r in fg)
    P("  ghost redraws per freeze frame:", dict(collections.Counter(per_frame.values())))
    # ghosts do not move during the freeze: compare x, y, dir with the values at DEATH_START
    st_by_f = {}
    for d in starts:
        st_by_f[d["f"]] = d
    moved = 0
    frozen = 0
    for r in fg:
        start = None
        for d in starts:
            if d["f"] <= r["f"]:
                start = d
        if start is None or r["f"] - start["f"] > 200:
            continue
        frozen += 1
        if r["x"] != start["gx"][r["g"]] or r["y"] != start["gy"][r["g"]]:
            moved += 1
            bad["ghost moved during the freeze"].append((r, start))
        if r["st"] != start["st"][r["g"]]:
            bad["ghost state changed during the freeze"].append((r, start))
    P("  ghost redraws compared with the position/state at DEATH_START:", frozen, " moved or changed:", moved)
    # pictures drawn during the freeze: the right shape for direction/state, feet alternate with LegPhase
    SH = {1: 0xBAC0, 2: 0xBACA, 4: 0xBAD4, 8: 0xBADE}
    pics = collections.Counter()
    gd_by_f = collections.defaultdict(list)
    for r in gd:
        gd_by_f[r["f"]].append(r)
    fgd = {}
    for r in fg:
        fgd[(r["f"], r["g"])] = r
    wrong = 0
    feet_seq = collections.defaultdict(list)
    for r in fg:
        for d in gd_by_f.get(r["f"], []):
            if d["g"] == r["g"]:
                if r["st"] & 0x40:
                    want = 0xBAF2
                elif r["st"] & 0x80:
                    want = 0xBAE8
                else:
                    want = SH.get(r["dir"])
                pics["freeze draw: shape matches direction/state" if d["src"] == want else "freeze draw: shape differs"] += 1
                if d["src"] != want and not (r["st"] & 0xC0):
                    wrong += 1
                    bad["freeze picture differs from the direction shape"].append((r, d))
                feet_seq[r["g"]].append((r["f"], d["feet"]))
                break
    P("  pictures drawn during the freeze:", dict(pics))
    # LegPhase toggles during the freeze: count feet changes per death
    legs = [fr for n, fr, _ in evs if n == "FREEZE_LEG"]
    toggles = collections.Counter()
    for g, seqf in feet_seq.items():
        ch = sum(1 for a, b in zip(seqf, seqf[1:]) if a[1] != b[1] and b[0] - a[0] <= 2)
        toggles[g] = ch
    P("  frames with the leg-phase toggle call in the freeze: %d (96 per death); feet-row changes seen between consecutive freeze frames per ghost:" % len(legs), dict(sorted(toggles.items())))
    # no ghost is drawn from the HPOS zero event to the end of the death
    P("  calls of the ghost draw routine after ANIM_ON until the death routine ends (counted by log order, not by frame number):", late_draws, "(over %d deaths)" % len(starts))
    if late_draws:
        bad["a ghost was drawn after the freeze"].append(late_draws)
    # ghost state classes at the moment of death: the killing ghost is never frightened or eaten
    cls = collections.Counter()
    for d in starts:
        g = d["ghost"]
        st = d["st"][g]
        cls["killing ghost state $%02X" % st] += 1
        if st & 0xC0:
            bad["killed by a frightened or eaten ghost"].append(d)
    P("  state of the ghost that killed Pac-Man:", dict(sorted(cls.items())))
    P("  states of all four ghosts at the moment of death (counts of ghost-deaths):", dict(sorted(collections.Counter("$%02X" % s for d in starts for s in d["st"]).items())))

    P()
    for k in sorted(cnt):
        P("  %-90s %d" % (k, cnt[k]))
    P("violations:", {k: len(v) for k, v in bad.items()} or "none")
    for k, v in bad.items():
        P("  first", k, v[:2])
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
