"""Controlled test of the START STATE of a tone on POKEY channel 2 (docs/22-sound.md, OPEN-VERIFICATION.md OV-14d).  Usage:
  python -I tools/start_state_test.py --make-cmd                       writes tools/altirra_start_state_test.cmd
  python -I tools/start_state_test.py --analyze <recording.wav> <trace.txt> [--summary-file out.txt]

Why: the rule of OV-13a (the output flip-flop of a channel that enters a pure tone starts at the poly bit of its last gated fire) predicts all 110 start bits of the ghost-eaten sweep but is at
chance for the tone runs outside it (channel 2: 31 of 58).  The runs in the game differ in many ways at once.  This test changes one thing at a time: an injected 6502 program (as tools/mixer_test.py:
breakpoint at $A5FD, runs from emulation frame 900, interrupts off, the ROM is never changed) repeats TRIALS.  One trial = AUDC2 := $00 (idle noise, volume 0), AUDF2 := Ai, 3 frames of idle,
(first a one-frame time marker: AUDC1 := $1F, a volume-only DC step that anchors the recording to the trace for this trial), then at a cycle that moves by 5 cycles from trial to trial: AUDF2 := Bi, 9 cycles later AUDC2 := $A4 (pure tone, volume 4), held for 4 frames.  Every write to $D200-$D208 is traced (exact cycle), the audio is
recorded; the analysis fits the polarity of every trial's tone against the recording and compares it with the rule.  Configurations (Ai, Bi): (0, 13) the eyes; (13, 13) idle at the tone's own AUDF;
(20, 13) idle at another period; (2, 13) idle at a short period.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CPU = 315e6 / 88 / 2
FC = 262 * 114
BASE = 900
TAB = 0x0800
CONFIGS = [(0, 13), (13, 13), (20, 13), (2, 13)]
TRIALS = 56                                    # per configuration: delay D = 1..56 loops of 5 cycles
IDLE_FRAMES, HOLD_FRAMES = 3, 4


def regs(k):
    f = 0xD200 + 2 * (k - 1)
    return f, f + 1, (0xD201 if k != 1 else 0xD205)        # AUDF, AUDC of the tested channel; AUDC of the marker channel


def assemble(k=2):
    AF, AC, MK = regs(k)
    """-> bytes of the program at $0600 (a tiny assembler: ops are (mnemonic, operand) or ('label', name))"""
    ops = [
        ("SEI",), ("LDAi", 0), ("STAa", 0xD40E), ("STAa", 0xD20E), ("STAa", 0xD208), ("LDXi", 0),
        ("label", "L0"), ("LDAax", TAB), ("BEQ", "done"), ("STAz", 0xFE),
        ("LDAax", TAB + 0x100), ("STAz", 0xFD), ("LDAax", TAB + 0x200), ("STAz", 0xFC),
        ("LDAi", 0), ("STAa", AC), ("LDAz", 0xFD), ("STAa", AF),
        ("LDAi", 0x1F), ("STAa", MK), ("LDAi", 1), ("JSR", "WAIT"), ("LDAi", 0), ("STAa", MK),
        ("LDAi", IDLE_FRAMES - 1), ("JSR", "WAIT"), ("JSR", "SYNC"),
        ("LDYz", 0xFE), ("label", "D"), ("DEY",), ("BNE", "D"),
        ("LDAz", 0xFC), ("STAa", AF), ("LDAi", 0xA4), ("BITz", 0xFE), ("STAa", AC),
        ("LDAi", HOLD_FRAMES), ("JSR", "WAIT"),
        ("INX",), ("JMP", "L0"),
        ("label", "done"), ("LDAi", 0), ("LDXi", 8), ("label", "clr"), ("STAax", 0xD200), ("DEX",), ("BPL", "clr"),
        ("LDXi", 40), ("label", "fl"), ("STAa", 0x07FF), ("DEX",), ("BNE", "fl"), ("label", "end"), ("JMP", "end"),
        ("label", "WAIT"), ("STAz", 0xFB), ("label", "WL"), ("JSR", "SYNC"), ("DECz", 0xFB), ("BNE", "WL"), ("RTS",),
        ("label", "SYNC"), ("LDAa", 0xD40B), ("CMPi", 0x40), ("BNE", "SYNC"), ("label", "S2"), ("LDAa", 0xD40B), ("CMPi", 0x40), ("BEQ", "S2"), ("RTS",),
    ]
    size = {"SEI": 1, "LDAi": 2, "STAa": 3, "LDXi": 2, "LDAax": 3, "BEQ": 2, "STAz": 2, "LDAz": 2, "JSR": 3, "LDYz": 2, "DEY": 1, "BNE": 2, "BITz": 2, "INX": 1, "JMP": 3, "DEX": 1,
            "BPL": 2, "STAax": 3, "DECz": 2, "RTS": 1, "LDAa": 3, "CMPi": 2}
    opc = {"SEI": 0x78, "LDAi": 0xA9, "STAa": 0x8D, "LDXi": 0xA2, "LDAax": 0xBD, "BEQ": 0xF0, "STAz": 0x85, "LDAz": 0xA5, "JSR": 0x20, "LDYz": 0xA4, "DEY": 0x88, "BNE": 0xD0, "BITz": 0x24,
           "INX": 0xE8, "JMP": 0x4C, "DEX": 0xCA, "BPL": 0x10, "STAax": 0x9D, "DECz": 0xC6, "RTS": 0x60, "LDAa": 0xAD, "CMPi": 0xC9}
    labels, pc = {}, 0x0600
    for o in ops:
        if o[0] == "label":
            labels[o[1]] = pc
        else:
            pc += size[o[0]]
    out, pc = [], 0x0600
    for o in ops:
        if o[0] == "label":
            continue
        m = o[0]
        out.append(opc[m])
        if size[m] == 1:
            pass
        elif m in ("BEQ", "BNE", "BPL"):
            out.append((labels[o[1]] - (pc + 2)) & 0xFF)
        elif size[m] == 2:
            out.append(o[1] & 0xFF)
        else:
            a = labels[o[1]] if isinstance(o[1], str) else o[1]
            out += [a & 0xFF, a >> 8]
        pc += size[m]
    return out


def table():
    """-> three pages: delays D at TAB, idle AUDF at TAB+$100, tone AUDF at TAB+$200 (indexed by the trial number; 8-bit index, so at most 255 trials), D = 0 ends"""
    d, ai_, bi_ = [], [], []
    for (ai, bi) in CONFIGS:
        for dd in range(1, TRIALS + 1):
            d.append(dd); ai_.append(ai); bi_.append(bi)
    d.append(0); ai_.append(0); bi_.append(0)
    return d, ai_, bi_


def trial_list():
    return [(ai, bi, d) for (ai, bi) in CONFIGS for d in range(1, TRIALS + 1)]


def make_cmd(path, k=2):
    code, tab = assemble(k), table()
    lines = ["# Altirra debugger commands for the start-state test (tools/start_state_test.py, OPEN-VERIFICATION.md OV-14d): injects a 6502 program that starts %d tones on POKEY channel 2 at moving cycles." % len(trial_list()),
             "# Use with tools/record_tune.ps1 -Cmd altirra_start_state_test.cmd -Out analysis/start-state-test-recorded.wav -Trace analysis/raw-logs/start-state-test.txt -Seconds 60, then  python -I tools/start_state_test.py --analyze analysis/start-state-test-recorded.wav analysis/raw-logs/start-state-test.txt",
             "# The ROM is never changed; the program is written into emulated RAM and run from emulation frame %d on. Every write to $D200-$D208 and $D20F is traced; the final burst of writes to $07FF flushes the log." % BASE,
             'bta w d200 L9 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos',
             'bta w d20f L1 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos',
             'bta w 07ff L1 "FLUSH f=%d  ................................................................................................................................" @frame']

    def chunks(addr, data):
        for i in range(0, len(data), 16):
            yield addr + i, data[i:i + 16]
    pages = [(0x0600, code)] + [(TAB + 0x100 * k, tab[k]) for k in range(3)]
    for addr0, data0 in pages:
      for addr, d in chunks(addr0, data0):
        lines.append('bp -n a5fd "eb $%04X %s"' % (addr, " ".join("$%02X" % b for b in d)))
    lines.append('bp -n a5fd "r pc $a5fd+($0600-$a5fd)*(@frame>=%d)"' % BASE)
    open(path, "w", encoding="ascii", newline="\n").write("\n".join(lines) + "\n")


def analyze(wav, trace, summ, k=2):
    AF, AC, MK = regs(k)
    import analyze_full_waveform as A
    import analyze_ghost_sweep as G
    import analyze_tail_sound as T
    import analyze_tune_wav as W
    import pokey_noise as PN
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    mod = G.Model(sndw)
    mod.mixer = "invtable"
    # the tone starts of channel 2: AUDC2 ($D203) := $A4
    starts = [c for (c, r, v, pc) in sndw if r == 2 * (k - 1) + 1 and v == 0xA4 and pc >= 0x0600 and pc < 0x0700]
    trials = trial_list()
    P("Recording %.2f s; trace: %d tone starts of channel 2 (expected %d)." % (len(x) / rate, len(starts), len(trials)))
    n = min(len(starts), len(trials))
    step = CPU / rate
    xr = A.band(np.asarray(x, dtype=np.float64), rate)
    ends = {s: next(c for (c, r, v, pc) in sndw if r == 2 * (k - 1) + 1 and v == 0 and c > s) for s in starts}
    # time anchor of every trial: the marker (AUDC1 := $1F, a volume-only DC step) before it; the recording drifts against the trace when the emulator is slower than real time
    markers = [c for (c, r, v, pc) in sndw if r == (MK - 0xD200) and v == 0x1F and 0x0600 <= pc < 0x0700]
    dx = np.abs(np.asarray(x, dtype=np.float64)[2:] - np.asarray(x, dtype=np.float64)[:-2])
    ev_none = {kk: (np.array([0], dtype=np.int64), np.array([0], dtype=np.int8)) for kk in (1, 2, 3, 4)}
    # global first guess: the first marker is the first big step in the recording
    i_first = int(np.argmax(dx > 0.5 * dx.max()))
    c0_guess = markers[0] - (i_first + 1) * step
    lags = []

    def anchor(j):
        """cycle of sample 0 for trial j: from the marker's DC step, searched in +-60 ms around the guess (the drift is slow)"""
        i_pred = int(round((markers[j] - c0_guess) / step))
        w = 2800
        lo = max(0, i_pred - w)
        seg = dx[lo:i_pred + w]
        k = int(np.argmax(seg > 0.5 * seg.max()))
        return markers[j] - (lo + k + 1) * step

    def render(w0, w1, flip, c0):
        t_, s_ = A.run_events(mod, k, w0, w1, flip)
        ev = dict(ev_none)
        ev[k] = (np.array([0] + t_, dtype=np.int64), np.array([0] + s_, dtype=np.int8))
        a_c, b_c = w0, min(w1, w0 + int(0.05 * CPU))
        bb, tt = A.general_levels(mod, a_c, b_c, ev)
        nn = int((b_c - a_c) / step) - 1
        sig = A.band(G.render(bb, tt, a_c, nn, step), rate, ac=True)
        i_a = int(round((a_c - c0) / step))
        return sig, xr[i_a:i_a + nn]

    def score(w0, w1, flip, c0):
        sig, rr = render(w0, w1, flip, c0)
        if len(rr) != len(sig) or len(rr) < 100:
            return -2.0
        return float(np.dot(rr, sig) / (np.linalg.norm(rr) * np.linalg.norm(sig) + 1e-30))
    rows = []
    starts_m = []
    for j in range(min(n, len(markers))):
        w0, w1 = starts[j], ends[starts[j]]
        c0 = anchor(j)
        lags.append((c0 - c0_guess) / CPU * 1e3)
        s0, s1 = score(w0, w1, 0, c0), score(w0, w1, 1, c0)
        v, kind = PN.noise_state_before(mod, k, w0)
        rows.append((trials[j], w0, s0, s1, v))
    P("Marker anchors: %d; drift of the recording against the trace %.1f ms at the end (first trial 0)." % (len(lags), lags[-1] - lags[0]))
    # per configuration: agreement of the rule (flip 0 better = rule right)
    P("\nconfiguration (idle AUDF, tone AUDF): trials, rule right (flip 0 has the higher correlation), mean best correlation, undecided (|difference| < 0.3)")
    res = {}
    for cfg in CONFIGS:
        rr_ = [r for r in rows if (r[0][0], r[0][1]) == cfg]
        right = sum(1 for r in rr_ if r[2] > r[3] and abs(r[2] - r[3]) >= 0.3)
        und = sum(1 for r in rr_ if abs(r[2] - r[3]) < 0.3)
        P("  %-9s %3d trials   rule right %3d   wrong %3d   undecided %3d   mean best corr %.3f" % (cfg, len(rr_), right, len(rr_) - right - und, und, np.mean([max(r[2], r[3]) for r in rr_])))
        res[cfg] = rr_
    P("\nPer trial (delay loops D, tone start cycle mod 28, mod 131071, truth = state predicted XOR (1 if the complement fits better), rule state):")
    for r in rows:
        (ai, bi, d), w0, s0, s1, v = r
        P("  cfg(%2d,%2d) D=%2d  w0=%d  mod28=%2d  c0=%+.3f c1=%+.3f  %s  rule_state=%s" % (ai, bi, d, w0, w0 % 28, s0, s1, "RIGHT" if s0 > s1 else "WRONG", v))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")
    return rows


def main(argv):
    global CONFIGS
    if "--configs" in argv:                       # e.g. --configs 0:114,0:60,0:28,0:13  (idle AUDF : tone AUDF)
        CONFIGS = [tuple(int(v) for v in c.split(":")) for c in argv[argv.index("--configs") + 1].split(",")]
    k = int(argv[argv.index("--chan") + 1]) if "--chan" in argv else 2
    if argv and argv[0] == "--make-cmd":
        make_cmd(os.path.join(HERE, "altirra_start_state_test.cmd" if (k == 2 and "--configs" not in argv) else "altirra_start_state_test_%s.cmd" % ("tone" if "--configs" in argv else "ch%d" % k)), k)
        print("wrote tools/altirra_start_state_test.cmd (%d trials, %d program bytes)" % (len(trial_list()), len(assemble())))
        return 0
    if argv and argv[0] == "--analyze":
        summ = argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None
        analyze(argv[1], argv[2], summ, k)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
