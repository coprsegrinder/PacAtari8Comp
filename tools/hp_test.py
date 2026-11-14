"""Controlled measurement of the high-pass channel pair under the sweep's conditions (docs/22-sound.md, OPEN-VERIFICATION.md OV-13d).  Usage:
  python -I tools/hp_test.py --make-cmd                                  writes tools/altirra_hp_test.cmd
  python -I tools/hp_test.py --analyze analysis/hp-test-recorded.wav analysis/raw-logs/hp-test.txt [--summary-file out.txt] [--mixer linear|altirra]

Why: with Altirra's verified mixer chain the ghost-eaten sweep correlates about 0.01 worse than with a plain linear sum (OV-13d), although the mixer itself is right to 0.8% on controlled tones.  The sweep
differs from that test in one way: AUDCTL = $84 puts a high-pass flip-flop on channel 1, clocked by channel 3, and the three pitches are within a few percent of each other.  This test holds exactly these
states steady (the real frame states of a sweep, and ablations that switch channels off) with the same injected 6502 program as tools/mixer_test.py, but TRACES the register writes (a burst of writes at the
end flushes the log), so the model gets exact cycles, and compares every configuration with the model under different assumptions.
"""
import bisect
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mixer_test as M  # noqa: E402

CPU = 315e6 / 88 / 2
FC = 262 * 114
FRAMES = 72
# (AUDF1, AUDF3, AUDF4), (vol1, vol3, vol4), label : real frame states of a ghost-eaten sweep (even frames: 8/8/8, odd frames: 4/8/4) and ablations of the first one
CONFIGS = [
    ((114, 118, 118), (8, 8, 8), "even-1"), ((111, 118, 114), (4, 8, 4), "odd-1"),
    ((72, 76, 76), (8, 8, 8), "even-2"), ((69, 76, 72), (4, 8, 4), "odd-2"),
    ((44, 48, 48), (8, 8, 8), "even-3"), ((41, 48, 44), (4, 8, 4), "odd-3"),
    ((114, 118, 118), (8, 0, 0), "ch1 only (ch3 silent, still the HP clock)"), ((114, 118, 118), (0, 8, 0), "ch3 only"),
    ((114, 118, 118), (0, 0, 8), "ch4 only"), ((114, 118, 118), (8, 8, 0), "ch1+ch3"),
    ((114, 118, 118), (8, 0, 8), "ch1+ch4"), ((114, 118, 118), (0, 8, 8), "ch3+ch4"),
]
AUDCTL = 0x84
# second set: channel 1 alone under the high-pass filter (channel 3 silent, only the clock) for systematic pitch pairs (AUDF1, AUDF3)
PAIRS = [(114, 114), (114, 116), (114, 118), (114, 122), (114, 110), (114, 106), (72, 72), (72, 76), (72, 80), (72, 68), (44, 48), (200, 204)]
CONFIG_SETS = {"sweep": CONFIGS, "pairs": [((a, b, b), (8, 0, 0), "ch1 only, AUDF1=%d AUDF3=%d (diff %+d)" % (a, b, b - a)) for (a, b) in PAIRS]}
# third set: ONE channel (3) with AUDCTL = 0 whose AUDF steps every 0.3 s - the edge times in the recording are compared with the model's fire times across each step
EDGE_STEPS = [114, 118, 114, 122, 114, 110, 114, 106, 72, 76, 72, 80, 72, 68, 44, 48, 44, 52, 44, 40, 200, 204, 200, 208, 200]      # 25 rows at most: the program indexes its table with an 8-bit register
CONFIG_SETS["edges"] = [((0, a, 0), (0, 8, 0), "ch3 only AUDF3=%d" % a) for a in EDGE_STEPS]


def _replay_rows(ch1_only):
    """the register states of frames 1..24 of the first ghost-eaten sweep of the events trace (AUDF1, AUDC1, AUDF3, AUDC3, AUDF4, AUDC4 per frame), as (AUDF tuple, volume tuple, label)"""
    import analyze_tail_sound as T
    path = os.path.join(os.path.dirname(HERE), "analysis", "raw-logs", "sound-events.txt")
    sndw, _, _ = T.parse_trace(path)
    c_a = next(c for (c, r, v, pc) in sndw if pc == 0xA8EE)
    reg = [0] * 9
    rows, last = [], -1
    for (c, r, v, pc) in sndw:
        if c > c_a + 25 * FC:
            break
        if r <= 8:
            reg[r] = v
        fr = (c - c_a) // FC
        if c >= c_a and fr != last and 1 <= fr <= 24:
            last = fr
            rows.append((fr, list(reg)))
    out = []
    for fr, rg in rows:
        vol = (rg[1] & 15, rg[5] & 15, rg[7] & 15)
        if ch1_only:
            vol = (vol[0], 0, 0)
        out.append(((rg[0], rg[4], rg[6]), vol, "frame %d" % fr))
    return out


CONFIG_SETS["replay1"] = _replay_rows(True)       # the real frame states, only channel 1 audible
CONFIG_SETS["replay"] = _replay_rows(False)       # the real frame states, all three channels
# fourth set: how long a state has been held: channel 1 alone, AUDF1 = 114 constant, AUDF3 alternating 118 / 122, each state held for N frames
HOLD_N = [1, 2, 3, 5, 8, 12, 18, 30, 60]
HOLD_FRAMES = []
CONFIG_SETS["hold"] = []
for n in HOLD_N:
    for a3 in (118, 122):
        CONFIG_SETS["hold"].append(((114, a3, a3), (8, 0, 0), "hold %d frames, AUDF3=%d" % (n, a3)))
        HOLD_FRAMES.append(n)
META = {"sweep": (0x84, 72), "pairs": (0x84, 72), "edges": (0x00, 18), "replay1": (0x84, 1), "replay": (0x84, 1), "hold": (0x84, 1)}


# fifth set 'abs': marker clicks on channel 2 (volume-only mode, AUDC2 = $14 then $10) before each configuration: isolated steps at known write instants, an absolute time reference that depends on no timer phase
MARK = [((114, 118, 118), (0, 0, 0), "silence", 3, 0x10), ((114, 118, 118), (0, 0, 0), "click on", 3, 0x14), ((114, 118, 118), (0, 0, 0), "click off", 3, 0x10)]
ABS_ROWS = []
for (af, vol, lab) in [((114, 118, 118), (8, 0, 0), "ch1 only, AUDF3-AUDF1=+4"), ((114, 118, 118), (0, 8, 0), "ch3 only"), ((114, 122, 122), (8, 0, 0), "ch1 only, AUDF3-AUDF1=+8"),
                       ((114, 110, 110), (8, 0, 0), "ch1 only, AUDF3-AUDF1=-4"), ((114, 114, 114), (8, 0, 0), "ch1 only, AUDF3-AUDF1=0")]:
    ABS_ROWS += MARK + [(af, vol, lab, 36, 0x10)]
ABS_ROWS += MARK
CONFIG_SETS["abs"] = [r[:3] + r[3:] for r in ABS_ROWS]
META["abs"] = (0x84, 1)


# sixth set 'nohp': AUDCTL = 0 (NO high-pass).  Channel 1 and channel 4 (the reference train, AUDF4 = AUDF3 = b) both audible, AUDF1 = 114 never rewritten with a different value; b steps as in 'pairs'.
NOHP_B = [114, 116, 118, 122, 110, 106, 118, 114]
CONFIG_SETS["nohp"] = [((114, 114, 114), (0, 0, 8), "ch4 only (reference)")] + [((114, b, b), (8, 0, 8), "ch1 + ch4, no high-pass, AUDF4=%d (diff %+d)" % (b, b - 114)) for b in NOHP_B]
META["nohp"] = (0x00, 72)

# seventh/eighth set 'disp1'/'disp2': AUDCTL = 0, channel 1 constant and channel 4 stepping, to find what the displacement of a changed channel's edge train is measured from.
#   disp1: AUDF1 = 72 constant, channel 4 starts at AUDF 114;   disp2: AUDF1 = 114 constant, channel 4 starts at AUDF 72
DISP_SEQ = {"disp1": [114, 118, 114, 110, 130, 114, 90, 114, 114, 122, 114], "disp2": [72, 76, 72, 68, 90, 72, 120, 72, 72, 80, 72]}
for _name, _a1 in (("disp1", 72), ("disp2", 114)):
    CONFIG_SETS[_name] = [((_a1, b, b), (8, 0, 8), "ch1 + ch4, AUDF1=%d, AUDF4=%d" % (_a1, b)) for b in DISP_SEQ[_name]]
    META[_name] = (0x00, 40)


# ninth set 'abs0': AUDCTL = 0, ONE channel audible per row, a marker-click triplet (silence, click on, click off) before every row; varied AUDF write histories
def _abs0():
    mk = [((114, 114, 114), (0, 0, 0), "click on", 3, 0x14), ((114, 114, 114), (0, 0, 0), "click off", 3, 0x10)]       # 25 rows at most (8-bit table index): the click-off step is isolated (the tones are off since the click-on row)
    rows = list(mk)
    rows.append(((114, 0, 0), (8, 0, 0), "ch1 only, AUDF1=114 (first write)", 20, 0x10))
    for (a4, lab) in ((114, "ch4 only, AUDF4=114 (first write of ch4)"), (118, "ch4 only, AUDF4=118 (change)"), (114, "ch4 only, AUDF4=114 (change back)"), (110, "ch4 only, AUDF4=110 (change)")):
        rows += mk + [((114, 0, a4), (0, 0, 8), lab, 20, 0x10)]
    rows += mk + [((114, 0, 110), (8, 0, 0), "ch1 only again, AUDF1=114 (rewritten, unchanged)", 20, 0x10)]
    rows += mk + [((120, 0, 110), (8, 0, 0), "ch1 only, AUDF1=120 (change)", 20, 0x10)]
    return rows


# tenth set 'steps': ONE channel (4) alone, AUDCTL = 0, 22 AUDF steps with varied old/new periods and write phases; the time axis is fixed by a single click from silence at the start
STEP_SEQ = [114, 118, 114, 110, 130, 90, 114, 100, 170, 60, 114, 150, 80, 114, 126, 104, 114, 190, 70, 114, 140, 96]
CONFIG_SETS["steps"] = [((114, 114, 114), (0, 0, 0), "click on", 3, 0x14), ((114, 114, 114), (0, 0, 0), "click off", 3, 0x10)] + [((114, 114, a), (0, 0, 8), "ch4 alone, AUDF4=%d" % a, 18, 0x10) for a in STEP_SEQ[:21]]
META["steps"] = (0x00, 1)
CONFIG_SETS["abs0"] = _abs0()
META["abs0"] = (0x00, 1)


# ninth set 'bis': bisecting what makes the 'pairs' rows differ from the 'hold' rows: AUDF1 = 114 constant, AUDF3 stepping through values (equal period first, then the pairs' and the hold's transitions in other orders)
BIS_SEQ = [114, 116, 118, 122, 118, 122, 116, 118, 114, 118, 122, 118, 122, 118, 122]
CONFIG_SETS["bis"] = [((114, b, b), (8, 0, 0), "AUDF3=%d (diff %+d)" % (b, b - 114)) for b in BIS_SEQ]
META["bis"] = (0x84, 72)

# tenth set 'dur': the same two states (AUDF3 = 118, 122; AUDF1 = 114) held for different numbers of frames, to see whether the length of the previous state matters
DUR_N = [20, 40, 60, 66, 72, 80]
DUR_FRAMES = []
CONFIG_SETS["dur"] = []
for n in DUR_N:
    for a3 in (118, 122):
        CONFIG_SETS["dur"].append(((114, a3, a3), (8, 0, 0), "dur %d frames, AUDF3=%d" % (n, a3)))
        DUR_FRAMES.append(n)
META["dur"] = (0x84, 72)

# eleventh set 'volsw' (OV-13e): AUDCTL = 0, channel 1 steady at volume 8, channel 4 switched between volume 0 and 8 every N frames (N = 1..12): does the gain of the mix follow the instantaneous configuration?
VOLSW_N = [1, 2, 3, 5, 8, 12]
VOLSW_FRAMES = []
CONFIG_SETS["volsw"] = []
for n in VOLSW_N:
    for v4 in (0, 8):
        CONFIG_SETS["volsw"].append(((114, 0, 118), (8, 0, v4), "ch1 8 + ch4 %d, %d frames" % (v4, n)))
        VOLSW_FRAMES.append(n)
META["volsw"] = (0x00, 1)

# twelfth set 'phase' (OV-13e): AUDCTL = 0, channels 1 and 4 at volume 8 and the SAME period (114).  Between the equal-period rows channel 4 runs a few frames at another AUDF, which rotates the relative phase of the two
# squares by a known amount.  An instantaneous curve gives the pair a smaller amplitude the more the two highs overlap (in phase); a gain that follows the configuration gives the same amplitude at every phase.
PHASE_SEQ = [(114, 14), (115, 3), (114, 14), (116, 2), (114, 14), (117, 5), (114, 14), (118, 2), (114, 14), (120, 3), (114, 14), (121, 1), (114, 14), (122, 4), (114, 14), (125, 2), (114, 14), (128, 3), (114, 14)]
PHASE_FRAMES = [n for (a, n) in PHASE_SEQ]
CONFIG_SETS["phase"] = [((114, 0, a), (8, 0, 8), "ch1 8 + ch4 8, AUDF4=%d, %d frames" % (a, n)) for (a, n) in PHASE_SEQ]
META["phase"] = (0x00, 1)

# thirteenth set 'uneq' (OV-13e): AUDCTL = 0, channels 1 and 4 with equal or UNEQUAL volumes, pitches 114 / 118 (so every combination of the two states occurs): the four levels of the pair are regressed out of the recording
UNEQ = [(8, 0), (0, 8), (15, 0), (0, 15), (8, 8), (15, 15), (15, 8), (8, 15), (15, 4), (4, 15), (15, 1), (1, 15), (8, 4), (4, 8), (12, 12), (4, 4), (15, 2), (2, 15)]
CONFIG_SETS["uneq"] = [((114, 0, 118), (a, 0, b), "ch1 %d + ch4 %d" % (a, b)) for (a, b) in UNEQ]
META["uneq"] = (0x00, 72)


def cfg_frames(i):
    if ACTIVE["set"] in ("abs", "abs0", "steps"):
        return CONFIG_SETS[ACTIVE["set"]][i][3]
    return HOLD_FRAMES[i] if ACTIVE["set"] == "hold" else DUR_FRAMES[i] if ACTIVE["set"] == "dur" else VOLSW_FRAMES[i] if ACTIVE["set"] == "volsw" else PHASE_FRAMES[i] if ACTIVE["set"] == "phase" else META[ACTIVE["set"]][1]
ACTIVE = {"set": "sweep"}
RENDER = "bl"                       # --render ac: the box-average renderer with Altirra's output clamp; bl: the alias-free band-limited synthesis (no clamp)


def configs():
    return CONFIG_SETS[ACTIVE["set"]]


def program():
    code, _ = M.program()
    code = list(code[:-3]) + [0xA2, 0x00, 0x8D, 0xFF, 0x07, 0xCA, 0xD0, 0xFA, 0x4C, 0x48, 0x06]       # done: ...; LDX #0; L: STA $07FF; DEX; BNE L; JMP *   (256 writes that make the log flush)
    table = []
    for i, cfg in enumerate(configs()):
        af, vol = cfg[0], cfg[1]
        audc2 = cfg[4] if len(cfg) > 4 else 0
        table += [(cfg_frames(i)), af[0], 0xA0 | vol[0], 0, audc2, af[1], 0xA0 | vol[1], af[2], 0xA0 | vol[2], META[ACTIVE["set"]][0]]
    table.append(0)
    return code, table


def make_cmd(path, dump=False):
    code, table = program()
    lines = ["# Altirra debugger commands for the high-pass test (tools/hp_test.py, OPEN-VERIFICATION.md OV-13d): injects the program of tools/mixer_test.py with %d configurations of the sweep's channels 1, 3, 4 and AUDCTL = $84." % len(configs()),
             "# Use with tools/record_tune.ps1 -Cmd altirra_hp_test.cmd -Out analysis/hp-test-recorded.wav -Trace analysis/raw-logs/hp-test.txt -Seconds 40, then  python -I tools/hp_test.py --analyze analysis/hp-test-recorded.wav analysis/raw-logs/hp-test.txt",
             "# The ROM is never changed.  Every write to $D200-$D208 is traced (SNDW); the final burst of writes to $07FF (FLUSH lines) forces the log to be written out before Altirra is closed.",
             'bta w d200 L9 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos',
             'bta w 07ff L1 "FLUSH f=%d  ................................................................................................................................" @frame']
    for i in range(0, len(code), 16):
        lines.append('bp -n a5fd "eb $%04X %s"' % (0x600 + i, " ".join("$%02X" % b for b in code[i:i + 16])))
    for i in range(0, len(table), 16):
        lines.append('bp -n a5fd "eb $%04X %s"' % (0x700 + i, " ".join("$%02X" % b for b in table[i:i + 16])))
    if dump:        # --dump: the debugger's .pokey (cycles until each timer fires) once per frame, at the end of each frame's wait (the instruction DEC $FE at $062F)
        lines.append('bt 062f "POKEYDUMP f=%d vp=%d hp=%d" @frame vpos hpos')
        lines.append('bp -n 062f ".pokey"')
    lines.append('bp -n a5fd "r pc $a5fd+($0600-$a5fd)*(@frame>=%d)"' % M.BASE)
    open(path, "w", encoding="ascii", newline="\n").write("\n".join(lines) + "\n")


def anchor(x, rate, mod, ends, search=120000):
    """-> the cycle of sample 0 of the recording.  The recording's start has no fixed relation to the emulation: the first guess (first sound against the first audible fire) can be off by hundreds of
    ticks.  Fine alignment: the whole-tick shift (within +-`search` ticks) that makes the most observed steps coincide with the fires of ALL audible channels in all rows (and channel 3's, the filter clock,
    in the high-pass rows).  Trains of different periods cannot all line up at a wrong shift, so the optimum is unique; aligning with one periodic train alone is ambiguous modulo its period, and a narrow
    search around a wrong first guess (the previous version, +-half a period) lands on a wrong alias - that fabricated the 'latch advance' of the first analysis of OV-13d."""
    import pokey_noise as PN
    step = CPU / rate
    xx = np.asarray(x, dtype=np.float64)
    d1 = np.diff(xx)
    thr = 0.25 * np.percentile(np.abs(d1), 99.9)
    pk = np.array([i for i in range(3, len(d1) - 3) if abs(d1[i]) > thr and abs(d1[i]) >= abs(d1[i - 1]) and abs(d1[i]) > abs(d1[i + 1])])
    nn = np.array([i + float(np.sum(np.abs(d1[i - 3:i + 4]) * np.arange(-3, 4)) / np.sum(np.abs(d1[i - 3:i + 4]))) + 0.5 for i in pk])
    ctl = META[ACTIVE["set"]][0]
    cand = []
    for i, cfg in enumerate(configs()):
        vol = cfg[1]
        c_s = ends[i]
        n = cfg_frames(i)
        c_e = c_s + n * FC
        chs = [k for k, v in zip((1, 3, 4), vol) if v]
        if ctl == 0x84 and vol[0]:
            chs = sorted(set(chs + [3]))
        for k in chs:
            cand += [f + 2 for f in PN.edges(mod.timers[k], c_s + int(0.3 * n * FC), c_e)]
    cand = np.array(sorted(cand), dtype=float)
    c0 = cand[0] - nn[0] * step

    def score(edges, shifts):
        out = []
        for sh in shifts:
            t = edges * step + c0 + sh * 28.0
            idx = np.clip(np.searchsorted(cand, t), 1, len(cand) - 1)
            d = np.minimum(np.abs(t - cand[idx]), np.abs(t - cand[idx - 1]))
            out.append((int((d < 40).sum()), sh))
        return out
    # coarse: a sample of the edges over the whole range; the first-sound estimate can be wrong by a quarter of a second (17,135 ticks in the 'bis' recording), so the range is +-`search` ticks
    coarse = max(score(nn[::16], range(-search, search + 1)))
    # fine: all edges around the coarse optimum
    fine = max(score(nn, range(coarse[1] - 4, coarse[1] + 5)))
    return c0 + fine[1] * 28.0


def analyze(wav, trace, mixer, summ=None):
    import analyze_ghost_sweep as G
    import analyze_tail_sound as T
    import analyze_tune_wav as W
    import pokey_noise as PN
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    step = CPU / rate
    G.CPU = CPU
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    # configuration starts: the writes of AUDCTL ($D208) with value $84 each begin/end a configuration (the program writes AUDF1 ... AUDCTL in order)
    ends = [c for (c, r, v, pc) in sndw if r == 8 and v == META[ACTIVE["set"]][0] and 0x600 <= pc < 0x700]
    P("Configurations found in the trace: %d (expected %d)." % (len(ends), len(configs())))
    mod = G.Model(sndw)
    mod.mixer = mixer
    G.MIXER_CLAMP = (mixer in ("altirra", "invtable"))
    G.INVERTED = (mixer == "invtable")
    G.AC_COUPLING = True
    c0 = anchor(x, rate, mod, ends)
    P("Recording %.2f s; model clock %.3f Hz; cycle of sample 0 = %.1f." % (len(x) / rate, CPU, c0))
    rows = []
    for i, cfg in enumerate(configs()):
        af, vol, label = cfg[0], cfg[1], cfg[2]
        c_s = ends[i]
        c_a, c_b = c_s + int(0.05 * CPU), c_s + int(1.15 * CPU)
        n0, n1 = int((c_s + 0.25 * CPU - c0) / step), int((c_s + 1.15 * CPU - c0) / step)
        br = G.bandpass(np.asarray(x[n0:n1], dtype=np.float64), rate)
        best = None
        for var in (0, 1):
            for c3 in (0, 1):
                for c4 in (0, 1):
                    for c1 in (0, 1):
                        for hpc in (0, 1):
                            bps, tot = mod.mixed(c_a, c_b, {1: c1, 3: c3, 4: c4}, var, True, hpc)
                            sig = G.render_bl(bps, tot, c0 + n0 * step, n1 - n0, step) if RENDER == "bl" else G.render_ac(bps, tot, c_a, int(c0 + n0 * step), n1 - n0, step)
                            bm = G.bandpass(sig, rate)
                            cc, lag = G.best_corr(bm, br, 4)
                            if best is None or cc > best[0]:
                                best = (cc, lag, var, (c1, c3, c4, hpc), float(np.sqrt(np.mean(bm ** 2)) * 2 * 0.0086 / max(np.sqrt(np.mean(br ** 2)), 1e-12)))
        rows.append((label, af, vol, best))
        P("  %-44s AUDF %-15s vol %-9s best corr %.4f (lag %+d, order %d, bits c1,c3,c4,hpc = %s)" % (label, af, vol, best[0], best[1], best[2], best[3]))
    cs = [r[3][0] for r in rows]
    P("\nMixer %s: correlation over the %d configurations: min %.4f, median %.4f." % (mixer, len(rows), min(cs), float(np.median(cs))))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")
    return rows


def analyze_hold(wav, trace, summ=None):
    """For the 'hold' set (channel 1 alone, AUDF1 constant, AUDF3 alternating, each state held for N frames): the correlation of the recording with the model whose high-pass latch sits at channel 3's fire
    (dt = 0) and with the model whose latch is (AUDF3 - AUDF1) ticks EARLIER.  Both with Altirra's mixer chain and the alias-free renderer."""
    import analyze_ghost_sweep as G
    import analyze_tail_sound as T
    import analyze_tune_wav as W
    ACTIVE["set"] = "hold"
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    step = CPU / rate
    G.CPU = CPU
    cfgs = configs()
    ends = [c for (c, r, v, pc) in sndw if r == 8 and v == AUDCTL and 0x600 <= pc < 0x700][:len(cfgs)]
    mod = G.Model(sndw)
    mod.mixer = "linear"
    G.AC_COUPLING = True
    c0 = anchor(x, rate, mod, ends)
    bitsets = [(c1, 0, 0, h) for c1 in (0, 1) for h in (0, 1)]
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    P("Hold test (channel 1 alone, AUDF1 = 114, AUDF3 alternating 118 / 122): correlation with the model whose high-pass latch is at channel 3's fire (dt = 0) and with the latch (AUDF3 - AUDF1) ticks earlier.")
    for i, (af, vol, lab) in enumerate(cfgs):
        n = HOLD_FRAMES[i]
        c_s = ends[i]
        c_a, c_b = c_s - 200, c_s + n * FC - 100
        c_cmp = c_s + int(min(0.2 * n, 6) * FC)
        n0, n1 = int((c_cmp - c0) / step), int((c_b - c0) / step)
        if n1 - n0 < 300:
            continue
        br = G.bandpass(np.asarray(x[n0:n1], dtype=np.float64), rate)
        diff = af[1] - af[0]

        def score(dt):
            G.HP_DT = dt
            best = -2
            for var in (0, 1):
                for bits in bitsets:
                    bps, tot = mod.mixed(c_a, c_b, {1: bits[0], 3: 0, 4: 0}, var, True, bits[3])
                    bm = G.bandpass(G.render_bl(bps, tot, c0 + n0 * step, n1 - n0, step), rate)
                    best = max(best, G.best_corr(bm, br, 2)[0])
            return best
        s0, sd = score(0.0), score(-28.0 * diff)
        G.HP_DT = 0.0
        P("  held %2d frames, AUDF3 = %d (diff %+d): dt = 0: %.3f   latch %d ticks earlier: %.3f" % (n, af[1], diff, s0, diff, sd))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")


def _edges_of(x, rate, c0, lo, hi, step):
    """times (cycles) of the steps of the recording between the cycles lo and hi (centroid of the derivative peaks)"""
    d1 = np.diff(np.asarray(x, dtype=np.float64))
    thr = 0.25 * np.percentile(np.abs(d1), 99.9)
    a, b = int((lo - c0) / step), int((hi - c0) / step)
    pk = [j for j in range(max(a, 3), min(b, len(d1) - 4)) if abs(d1[j]) > thr and abs(d1[j]) >= abs(d1[j - 1]) and abs(d1[j]) > abs(d1[j + 1])]
    return np.array([(j + float(np.sum(np.abs(d1[j - 3:j + 4]) * np.arange(-3, 4)) / np.sum(np.abs(d1[j - 3:j + 4]))) + 0.5) * step + c0 for j in pk])


def analyze_phase(wav, trace, summ=None, min_frames=12):
    """For the sets with channel 1 alone under the high-pass filter (pairs, bis, dur, hold): where, in time, the recording's high-pass pulse ENDS lie against the fires of channel 3 in the model.  A pulse starts
    at a fire of channel 1 and ends at the next fire of channel 3 (the latch update), so every edge that is not at a channel-1 fire is a channel-3 fire as heard.  For each row the median and the spread of
    (observed edge - nearest model fire of channel 3) in grid ticks; the model is right when this is one constant (the chain's delay, up to one tick depending on which whole-tick alignment the anchor picked) in every row, with a spread of 0.2 ticks."""
    import analyze_tail_sound as T
    import analyze_tune_wav as W
    import analyze_ghost_sweep as G
    import pokey_noise as PN
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    step = CPU / rate
    G.CPU = CPU
    cfgs = configs()
    ends = [c for (c, r, v, pc) in sndw if r == 8 and v == META[ACTIVE["set"]][0] and 0x600 <= pc < 0x700][:len(cfgs)]
    mod = G.Model(sndw)
    c0 = anchor(x, rate, mod, ends)
    w3 = [(c, v) for (c, r, v, pc) in sndw if r == 4 and 0x600 <= pc < 0x700]
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    P("Phase of the high-pass pulse ends against the model's channel-3 fires, set '%s' (%d configurations, rows of at least %d frames); cycle of sample 0 = %.1f." % (ACTIVE["set"], len(cfgs), min_frames, c0))
    meds = []
    for i, cfg in enumerate(cfgs):
        n = cfg_frames(i)
        if n < min_frames or not cfg[1][0]:
            continue
        c_s = ends[i]
        lo, hi = c_s + int(0.4 * n * FC), c_s + int(0.95 * n * FC)
        t = _edges_of(x, rate, c0, lo, hi, step)
        f1 = np.array(PN.edges(mod.timers[1], lo - 5000, hi + 5000), dtype=float) + 2
        f3 = np.array(PN.edges(mod.timers[3], lo - 5000, hi + 5000), dtype=float) + 2
        t = t[np.array([min(abs(q - g) for g in f1) for q in t]) / 28 > 3]
        if len(t) < 20:
            continue                      # equal periods: every edge is at a fire of channel 1
        r = np.array([min((q - g for g in f3), key=abs) for q in t]) / 28
        wc = max(c for c, v in w3 if c <= c_s)
        old = [v for c, v in w3 if c < wc]
        P("  %-34s AUDF3 %3s -> %3d: offset median %+5.2f ticks, spread %.2f (%d edges)" % (cfg[2][:34], old[-1] if old else "-", cfg[0][1], float(np.median(r)), float(np.std(r)), len(r)))
        meds.append(float(np.median(r)))
    if meds:
        md = float(np.median(meds))
        P("\nOver %d rows: offsets from %+.2f to %+.2f ticks (median %+.2f); largest deviation from the median %.2f ticks (a model error of one tick would show as a different offset in some rows)." % (len(meds), min(meds), max(meds), md, max(abs(m - md) for m in meds)))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")
    return meds


def analyze_shape(wav, trace, summ=None):
    """'nohp' set: two channels (1 and 4, volume 8 each) without the high-pass filter.  The level of 'both high' is varied between the linear sum (2.00, eta = 0) and Altirra's table (1.84, eta = 0.08); the
    correlation of the waveform with the recording shows which shape is real, and the scale factor (recording / model) of the two-channel rows against the single-channel row shows the gain."""
    import analyze_tail_sound as T
    import analyze_tune_wav as W
    import analyze_ghost_sweep as G
    ACTIVE["set"] = "nohp"
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    step = CPU / rate
    G.CPU = CPU
    G.AC_COUPLING = True
    G.MIXER_CLAMP = False
    cfgs = configs()
    ends = [c for (c, r, v, pc) in sndw if r == 8 and v == 0x00 and 0x600 <= pc < 0x700][:len(cfgs)]
    mod = G.Model(sndw)
    mod.mixer = "altirra"
    c0 = anchor(x, rate, mod, ends)
    eta = [0.0]
    saved = G.altirra_level

    def level(n0, n1, n23):
        n23 = np.asarray(n23, dtype=float)
        return np.where(n23 >= 4, 16.0 * (1 - eta[0]), n23 * 4.0) + 0 * np.asarray(n0)         # vol 8: one channel high = 8 units, both = 16 (1 - eta)

    def score(i):
        c_s = ends[i]
        c_a, c_b = c_s + int(0.05 * CPU), c_s + int(1.15 * CPU)
        n0, n1 = int((c_s + 0.25 * CPU - c0) / step), int((c_s + 1.15 * CPU - c0) / step)
        br = G.bandpass(np.asarray(x[n0:n1], dtype=np.float64), rate)
        best = (-2, 0)
        for var in (0, 1):
            for c1 in (0, 1):
                for c4 in (0, 1):
                    bps, tot = mod.mixed(c_a, c_b, {1: c1, 3: 0, 4: c4}, var, False, 0)
                    bm = G.bandpass(G.render_bl(bps, tot, c0 + n0 * step, n1 - n0, step), rate)
                    cc, lag = G.best_corr(bm, br, 3)
                    if cc > best[0]:
                        best = (cc, float(np.dot(bm, br) / np.dot(bm, bm)))
        return best
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    P("Two squares (channels 1 and 4, volume 8 each, no high-pass), rows %s: correlation of the recording with the model as a function of the level of 'both high'." % [cfgs[i][2][:24] for i in (2, 3, 4, 5)])
    G.altirra_level = level
    try:
        for e in (0.0, 0.04, 0.08, 0.12, 0.16):
            eta[0] = e
            P("  both-high level %.2f of 2.00 (eta %.2f%s): correlation %s" % (2 * (1 - e), e, ", Altirra's table" if abs(e - 0.08) < 1e-9 else ", linear sum" if e == 0 else "", " ".join("%.4f" % score(i)[0] for i in (2, 3, 4, 5))))
        eta[0] = 0.0
        r = [score(i) for i in (0, 1, 2, 3, 4, 5, 6)]
    finally:
        G.altirra_level = saved
    P("Scale factor recording / linear model, relative to the single channel (row 0, channel 4 alone): %s" % " ".join("%.3f" % (b / r[0][1]) for a, b in r))
    P("Altirra's table predicts 0.92 for the amplitude of each of two channels; the shape of the sum is the plain linear one (the correlation falls as the saturation grows), so the compression is a GAIN, not an instantaneous curve.")
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")


def _setup(wav, trace, setname, ctl):
    import analyze_tail_sound as T
    import analyze_tune_wav as W
    import analyze_ghost_sweep as G
    ACTIVE["set"] = setname
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    G.CPU = CPU
    G.AC_COUPLING = True
    G.MIXER_CLAMP = False
    cfgs = configs()
    ends = [c for (c, r, v, pc) in sndw if r == 8 and v == ctl and 0x600 <= pc < 0x700][:len(cfgs)]
    mod = G.Model(sndw)
    return G, x, rate, CPU / rate, cfgs, ends, mod, anchor(x, rate, mod, ends)


def analyze_gainphase(wav, trace, summ=None, single_scale=17.85):
    """'phase' set (OV-13e): channels 1 and 4, volume 8, the SAME period, the relative phase rotated between the rows.  An instantaneous curve would give the pair less amplitude the more the two highs overlap; the
    measured amplitude (scale of the plain linear model that fits the recording, relative to one channel alone: `single_scale`, in the units of the `volsw` set) is the same at every phase."""
    import pokey_noise as PN
    G, x, rate, step, cfgs, ends, mod, c0 = _setup(wav, trace, "phase", 0)
    mod.mixer = "linear"
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    P("Two squares of the same period (channels 1 and 4, volume 8, no high-pass), relative phase rotated between the rows; amplitude relative to one channel alone (Altirra's table: 0.919 on average over independent phases, 1.00 when the highs never overlap, 0.84 when they always do).")
    scales = []
    for i, cfg in enumerate(cfgs):
        if cfg[0][2] != 114:
            continue
        n = cfg_frames(i)
        a_c, b_c = ends[i] + 4 * FC, ends[i] + (n - 1) * FC
        n0, n1 = int((a_c - c0) / step), int((b_c - c0) / step)
        br = G.bandpass(np.asarray(x[n0:n1], dtype=np.float64), rate)
        best = None
        for var in (0, 1):
            for c1 in (0, 1):
                for c4 in (0, 1):
                    bps, tot = mod.mixed(a_c - 3000, b_c + 100, {1: c1, 3: 0, 4: c4}, var, False, 0)
                    bm = G.bandpass(G.render_bl(bps, tot, c0 + n0 * step, n1 - n0, step), rate)
                    cc, lag = G.best_corr(bm, br, 3)
                    if best is None or cc > best[0]:
                        best = (cc, float(np.dot(bm, br) / np.dot(bm, bm)) * 1e3)
        f1 = np.array(PN.edges(mod.timers[1], a_c, a_c + 20000), dtype=float)
        f4 = np.array(PN.edges(mod.timers[4], a_c, a_c + 20000), dtype=float)
        d = ((f4[0] - f1[0]) / 28) % 115
        scales.append(best[1] / single_scale)
        P("  row %2d: channel 4 behind channel 1 by %5.1f of 115 ticks (opposite phase = 57.5): correlation %.4f, amplitude %.3f x one channel" % (i, d, best[0], best[1] / single_scale))
    P("Over %d phases: amplitude %.3f - %.3f (spread %.1f%%)." % (len(scales), min(scales), max(scales), 100 * (max(scales) - min(scales)) / np.mean(scales)))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")


def analyze_volsw(wav, trace, summ=None):
    """'volsw' set (OV-13e): channel 1 steady at volume 8, channel 4 switched between 0 and 8 every N frames.  Per row: correlation of the recording with the model and the fitted scale (recording / model, 1e-3) for
    the linear sum, Altirra's table and the table's configuration gain ('cfggain'); the scale of the rows with channel 4 on must equal that of the rows with channel 4 off only for a model that has the gain."""
    G, x, rate, step, cfgs, ends, mod, c0 = _setup(wav, trace, "volsw", 0)
    c_a, c_b = ends[0] - 300, ends[-1] + 12 * FC - 200
    n0, n1 = int((ends[0] + 2 * FC - c0) / step), int((c_b - c0) / step)
    br = G.bandpass(np.asarray(x[n0:n1], dtype=np.float64), rate)
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    P("Channel 1 steady (volume 8), channel 4 switching 0 / 8 every N frames (N = %s); per row (channel 4 volume: correlation / fitted scale):" % VOLSW_N)
    for mixer in ("linear", "altirra", "cfggain"):
        mod.mixer = mixer
        best = None
        for var in (0, 1):
            for c1 in (0, 1):
                for c4 in (0, 1):
                    bps, tot = mod.mixed(c_a, c_b, {1: c1, 3: 0, 4: c4}, var, False, 0)
                    bm = G.bandpass(G.render_bl(bps, tot, c0 + n0 * step, n1 - n0, step), rate)
                    cc, lag = G.best_corr(bm, br, 3)
                    if best is None or cc > best[0]:
                        best = (cc, bm)
        cc, bm = best
        rows = []
        for i in range(len(cfgs)):
            if cfg_frames(i) < 5:
                continue
            a = int((ends[i] + 0.1 * FC - c0) / step) - n0
            b = int((ends[i] + (cfg_frames(i) - 0.1) * FC - c0) / step) - n0
            r, m = br[a:b], bm[a:b]
            rows.append("%d: %.3f / %.2f" % (cfgs[i][1][2], float(np.dot(r, m) / np.linalg.norm(r) / np.linalg.norm(m)), float(np.dot(r, m) / np.dot(m, m)) * 1e3))
        P("  %-8s whole %.4f | %s" % (mixer, cc, " | ".join(rows)))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")


def analyze_mixers(wav, trace, setname, summ=None, mixers=("linear", "altirra", "cfggain", "invtable")):
    """Per row of a two-channel set without the filter ('uneq', 'nohp', 'phase', ...; channels 1 and 4): correlation and fitted scale (recording / model, 1e-3) for each mixer.  The mixer that is right has the SAME
    scale in every row (the recording's level per volume unit does not depend on the configuration) and the highest correlation."""
    G, x, rate, step, cfgs, ends, mod, c0 = _setup(wav, trace, setname, META[setname][0])
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    P("Set '%s': per row, correlation / fitted scale (1e-3) with %s." % (setname, ", ".join(mixers)))
    scales = {m: [] for m in mixers}
    for i, cfg in enumerate(cfgs):
        n = cfg_frames(i)
        a_c, b_c = ends[i] + 4 * FC, ends[i] + (n - 1) * FC
        n0, n1 = int((a_c - c0) / step), int((b_c - c0) / step)
        br = G.bandpass(np.asarray(x[n0:n1], dtype=np.float64), rate)
        line = []
        for mixer in mixers:
            mod.mixer = mixer
            best = None
            for var in (0, 1):
                for c1 in (0, 1):
                    for c4 in (0, 1):
                        bps, tot = mod.mixed(a_c - 3000, b_c + 100, {1: c1, 3: 0, 4: c4}, var, False, 0)
                        bm = G.bandpass(G.render_bl(bps, tot, c0 + n0 * step, n1 - n0, step), rate)
                        cc, lag = G.best_corr(bm, br, 3)
                        if best is None or cc > best[0]:
                            best = (cc, float(np.dot(bm, br) / np.dot(bm, bm)) * 1e3)
            line.append("%s %.4f / %.2f" % (mixer[:6], best[0], best[1]))
            scales[mixer].append(best[1])
        P("  %-16s %s" % (cfg[2][:16], " | ".join(line)))
    P("Spread of the fitted scale over the %d rows (max / min - 1): %s" % (len(cfgs), ", ".join("%s %.1f%%" % (m, 100 * (max(v) / min(v) - 1)) for m, v in scales.items())))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")


def main(argv):
    if "--set" in argv:
        ACTIVE["set"] = argv[argv.index("--set") + 1]
    if argv and argv[0] == "--make-cmd":
        name = "altirra_hp_test.cmd" if ACTIVE["set"] == "sweep" else "altirra_hp_test_%s.cmd" % ACTIVE["set"]
        make_cmd(os.path.join(HERE, name if "--dump" not in argv else name.replace(".cmd", "_dump.cmd")), dump="--dump" in argv)
        print("wrote tools/" + name)
        return 0
    if argv and argv[0] == "--analyze-phase":
        analyze_phase(argv[1], argv[2], argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None)
        return 0
    if argv and argv[0] == "--analyze-shape":
        analyze_shape(argv[1], argv[2], argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None)
        return 0
    if argv and argv[0] in ("--analyze-gainphase", "--analyze-volsw"):
        f = analyze_gainphase if argv[0] == "--analyze-gainphase" else analyze_volsw
        f(argv[1], argv[2], argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None)
        return 0
    if argv and argv[0] == "--analyze-mixers":
        analyze_mixers(argv[1], argv[2], ACTIVE["set"], argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None)
        return 0
    if argv and argv[0] == "--analyze-hold":
        summ = argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None
        analyze_hold(argv[1], argv[2], summ)
        return 0
    if argv and argv[0] == "--analyze":
        mixer = argv[argv.index("--mixer") + 1] if "--mixer" in argv else "invtable"
        summ = argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None
        global RENDER
        if "--render" in argv:
            RENDER = argv[argv.index("--render") + 1]
        if "--hp-dt" in argv:
            import analyze_ghost_sweep as G0
            G0.HP_DT = float(argv[argv.index("--hp-dt") + 1])
        analyze(argv[1], argv[2], mixer, summ)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
