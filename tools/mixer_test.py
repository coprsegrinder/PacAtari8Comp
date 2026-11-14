"""Controlled measurement of POKEY's channel mixer in Altirra (docs/22-sound.md, OPEN-VERIFICATION.md OV-13b).  Usage:
  python -I tools/mixer_test.py --make-cmd                       writes tools/altirra_mixer_test.cmd (the debugger script that injects the test program)
  python -I tools/mixer_test.py --analyze analysis/mixer-test-recorded.wav [--summary-file out.txt]

Why: in the ghost-eaten sweep (three channels at volume 8) the real audio is about 12% below the linear sum of the volumes.  Altirra's mixer is not a linear sum (pokey.cpp, "Non-linear
mixing" is on in Altirra.ini): the volume bits have uneven weights and the summed level goes through a saturation curve.  This test holds known tones on channels 1, 3, 4 in 18 configurations
(different volume combinations, pitches 264 / 329 / 395 Hz) and compares the measured amplitude of every channel's fundamental with three mixers: linear, uneven bit weights only, and Altirra's full curve,
each followed by Altirra's AC-coupling high-pass.  Amplitudes are taken relative to the same channel playing alone at volume 8, which cancels the gain of the audio chain.

How the tones get there: a breakpoint at the title-screen routine ($A5FD) writes a 6502 program and a table of configurations into RAM at $0600/$0700 and jumps to it at emulation frame 900.  The
program disables interrupts and NMI, then writes the nine POKEY registers of each table entry and waits the entry's number of frames (counting VCOUNT passes of line 128).  No game code runs after that,
so nothing else writes a sound register.  The ROM is never changed.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CPU = 1789773.0
TICK = 28
FRAME_CYC = 262 * 114
FRAMES = 72                                   # per configuration: 1.2015 s
AUDF = {1: 120, 3: 96, 4: 80}                 # periods 121 / 97 / 81 grid ticks: 264.1 / 329.5 / 394.6 Hz, no common harmonics below 5 kHz
# (volume of channel 1, 3, 4); each entry is held for FRAMES frames
CONFIGS = [(0, 0, 0), (8, 0, 0), (0, 8, 0), (0, 0, 8), (8, 8, 0), (8, 0, 8), (0, 8, 8), (8, 8, 8),
           (15, 0, 0), (15, 15, 0), (15, 15, 15), (4, 0, 0), (4, 4, 4), (1, 0, 0), (15, 1, 0), (15, 0, 1), (7, 0, 0), (0, 0, 15)]
BASE = 900                                    # emulation frame at which the program takes over
BITS = (0.12 / 8.24, 0.26 / 8.24, 0.56 / 8.24)
THR, CURVE = 0.14, 2.85
TAU = 0.0025968510736001341332478644258       # AC coupling of the output stage
CLAMP_LO, CLAMP_HI = -0.65, 0.5
RATE_HC = CPU / TICK


def program():
    """-> (code bytes at $0600, table bytes at $0700)"""
    code = [0x78, 0xA9, 0x00, 0x8D, 0x0E, 0xD4, 0x8D, 0x0E, 0xD2, 0xA2, 0x00,        # SEI; LDA #0; STA NMIEN; STA IRQEN; LDX #0
            0xBD, 0x00, 0x07, 0xF0, 0x26, 0x85, 0xFE, 0xE8, 0xA0, 0x00,               # L0: LDA $0700,X; BEQ done; STA $FE; INX; LDY #0
            0xBD, 0x00, 0x07, 0x99, 0x00, 0xD2, 0xE8, 0xC8, 0xC0, 0x09, 0xD0, 0xF4,   # L1: LDA $0700,X; STA $D200,Y; INX; INY; CPY #9; BNE L1
            0xAD, 0x0B, 0xD4, 0xC9, 0x40, 0xD0, 0xF9,                                 # L2: LDA VCOUNT; CMP #$40; BNE L2
            0xAD, 0x0B, 0xD4, 0xC9, 0x40, 0xF0, 0xF9,                                 # L3: LDA VCOUNT; CMP #$40; BEQ L3
            0xC6, 0xFE, 0xD0, 0xEE, 0x4C, 0x0B, 0x06,                                 # DEC $FE; BNE L2; JMP L0
            0xA9, 0x00, 0xA2, 0x08, 0x9D, 0x00, 0xD2, 0xCA, 0x10, 0xFA, 0x4C, 0x40, 0x06]   # done: LDA #0; LDX #8; clr: STA $D200,X; DEX; BPL clr; JMP *
    table = []
    for (v1, v3, v4) in CONFIGS:
        table += [FRAMES, AUDF[1], 0xA0 | v1, 0, 0, AUDF[3], 0xA0 | v3, AUDF[4], 0xA0 | v4, 0]
    table.append(0)
    return code, table


def make_cmd(path):
    code, table = program()
    lines = ["# Altirra debugger commands for the mixer test (tools/mixer_test.py, OPEN-VERIFICATION.md OV-13b): injects a 6502 program that holds %d tone configurations on POKEY channels 1, 3, 4." % len(CONFIGS),
             "# Use with tools/record_tune.ps1 -Cmd altirra_mixer_test.cmd -Out analysis/mixer-test-recorded.wav -Trace analysis/raw-logs/mixer-test.txt -Seconds 45, then  python -I tools/mixer_test.py --analyze analysis/mixer-test-recorded.wav",
             "# The ROM is never changed; the program is written into emulated RAM and run from emulation frame %d on. No game code runs afterwards." % BASE]

    def chunks(addr, data):
        for i in range(0, len(data), 16):
            yield addr + i, data[i:i + 16]
    for addr, d in list(chunks(0x0600, code)) + list(chunks(0x0700, table)):
        lines.append('bp -n a5fd "eb $%04X %s"' % (addr, " ".join("$%02X" % b for b in d)))
    lines.append('bp -n a5fd "r pc $a5fd+($0600-$a5fd)*(@frame>=%d)"' % BASE)
    open(path, "w", encoding="ascii", newline="\n").write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------------------------------------------- prediction
def level(v1, v3, v4, s1, s3, s4, mixer):
    """mixed level (arbitrary linear unit) for the volumes and the output states (0/1 arrays)"""
    vols = ((v1, s1), (v3, s3), (v4, s4))
    n0 = sum(s * (v & 1) for v, s in vols)
    n1 = sum(s * ((v >> 1) & 1) for v, s in vols)
    n23 = sum(s * (((v >> 2) & 1) + 2 * ((v >> 3) & 1)) for v, s in vols)
    if mixer == "linear":
        return n0 * 1.0 + n1 * 2.0 + n23 * 4.0
    x = n0 * BITS[0] + n1 * BITS[1] + n23 * BITS[2]
    if mixer == "bits":
        return x / (0.56 / 8.24 / 4)
    y = np.where(x < THR, x, THR + (1.0 - np.exp(-CURVE * (x - THR))) / CURVE)
    if mixer == "altirra":
        return -2.1 * y                                    # Altirra's table units (negative-going, slope 2.1): the output clamp below is defined in them
    return y / (0.56 / 8.24 / 4)                           # "altirra_free": the same curve without the clamp, in volume units


def ac_couple(y):
    c = np.exp(-1.0 / (RATE_HC * TAU))
    d = np.diff(y, prepend=y[0])
    kern = c ** np.arange(4000)
    m = 1 << int(np.ceil(np.log2(len(y) + len(kern))))
    return np.fft.irfft(np.fft.rfft(d, m) * np.fft.rfft(kern, m), m)[:len(y)]


def fund_amp(x, rate, f, t0=0.0):
    """amplitude of the sine at frequency f (least squares over the whole array x sampled at `rate`)"""
    t = np.arange(len(x)) / rate
    best = 0.0
    for df in np.linspace(-0.15, 0.15, 7):
        c, s = np.cos(2 * np.pi * (f + df) * t), np.sin(2 * np.pi * (f + df) * t)
        a = np.array([[c @ c, c @ s], [c @ s, s @ s]])
        b = np.array([c @ x, s @ x])
        sol = np.linalg.solve(a, b)
        best = max(best, float(np.hypot(*sol)))
    return best


def predicted_amps(cfg, mixer, ac=True, seed=0, seconds=0.95):
    """-> {channel: amplitude of its fundamental} for configuration cfg = (v1, v3, v4), tones of known periods and a random phase per draw (averaged over 3 draws)"""
    n = int(seconds * RATE_HC)
    k = np.arange(n)
    out = {1: 0.0, 3: 0.0, 4: 0.0}
    rng = np.random.default_rng(seed)
    for draw in range(3):
        st = {}
        for ch in (1, 3, 4):
            per = AUDF[ch] + 1
            st[ch] = (((k + int(rng.integers(0, 2 * per))) // per) & 1).astype(np.float64)
        y = level(cfg[0], cfg[1], cfg[2], st[1], st[3], st[4], mixer)
        if ac:
            y = ac_couple(np.asarray(y, dtype=np.float64))[int(0.2 * RATE_HC):]
            if mixer == "altirra":
                y = np.clip(y, CLAMP_LO, CLAMP_HI)           # pokeyrenderer.cpp PostFilter: the AC-coupled output is clamped to [-0.65, 0.5] of POKEY's maximum
        else:
            y = np.asarray(y, dtype=np.float64)[int(0.2 * RATE_HC):]
        for ch in (1, 3, 4):
            f = RATE_HC / (2 * (AUDF[ch] + 1))
            out[ch] += fund_amp(y - y.mean(), RATE_HC, f) / 3
    return out


def main(argv):
    if argv and argv[0] == "--make-cmd":
        make_cmd(os.path.join(HERE, "altirra_mixer_test.cmd"))
        print("wrote tools/altirra_mixer_test.cmd")
        return 0
    if not argv or argv[0] != "--analyze":
        print(__doc__)
        return 2
    import analyze_tune_wav as W
    x, rate = W.load_wav(argv[1])
    summ = argv[argv.index("--summary-file") + 1] if "--summary-file" in argv else None
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    D = FRAMES * FRAME_CYC / CPU
    env = np.abs(x)
    thr = 0.5 * np.percentile(env, 99.5)
    t1 = float(np.argmax(env > thr)) / rate                    # onset of configuration 1 (configuration 0 is silence)
    # refine: configuration boundaries repeat every D seconds; the first non-silent sample may be a little late (the first zero crossing)
    t1 -= 0.002
    P("Recording %.2f s; configuration 1 starts at %.3f s; one configuration lasts %.4f s." % (len(x) / rate, t1, D))
    meas = {}
    for i, cfg in enumerate(CONFIGS):
        a, b = t1 + (i - 1) * D + 0.25, t1 + (i - 1) * D + 1.15
        seg = x[int(a * rate):int(b * rate)]
        meas[i] = {ch: fund_amp(seg - seg.mean(), rate, RATE_HC / (2 * (AUDF[ch] + 1))) for ch in (1, 3, 4)}
    ref = {1: meas[1][1], 3: meas[2][3], 4: meas[3][4]}          # each channel alone at volume 8
    P("Reference amplitude of one channel alone at volume 8 (recording units): ch1 %.5f  ch3 %.5f  ch4 %.5f (ratio ch3/ch1 %.3f, ch4/ch1 %.3f - the chain's frequency response)" % (ref[1], ref[3], ref[4], ref[3] / ref[1], ref[4] / ref[1]))
    models = ("linear", "bits", "altirra_free", "altirra")
    pred = {m: {i: predicted_amps(cfg, m) for i, cfg in enumerate(CONFIGS)} for m in models}
    pref = {m: {1: pred[m][1][1], 3: pred[m][2][3], 4: pred[m][3][4]} for m in models}
    P("\nAmplitude of each playing channel's fundamental relative to the same channel alone at volume 8 (measured | linear | uneven bits | Altirra curve without the output clamp | with the clamp):")
    err = {m: [] for m in models}
    rows = []
    for i, cfg in enumerate(CONFIGS):
        for ch, v in zip((1, 3, 4), cfg):
            if v == 0:
                continue
            r_meas = meas[i][ch] / ref[ch]
            r_mod = {m: pred[m][i][ch] / pref[m][ch] for m in models}
            for m in models:
                err[m].append(r_mod[m] / r_meas - 1.0)
            rows.append((i, cfg, ch, r_meas, r_mod))
            P("  config %2d vol (ch1, ch3, ch4) = %-12s ch%d: %.3f | %.3f  %.3f  %.3f  %.3f" % (i, cfg, ch, r_meas, r_mod["linear"], r_mod["bits"], r_mod["altirra_free"], r_mod["altirra"]))
    P("\nModel / measurement - 1 over the %d channel readings (mean, RMS, max |.|):" % len(err["linear"]))
    for m in models:
        e = np.array(err[m])
        P("  %-8s mean %+.3f  rms %.3f  max %.3f" % (m, e.mean(), np.sqrt((e ** 2).mean()), np.abs(e).max()))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
