"""The ghost-eaten sweep predicted from the register writes (docs/22-sound.md, OPEN-VERIFICATION.md OV-13).  Usage:
  python -I tools/analyze_ghost_sweep.py <recording.wav> <trace.txt> [--summary-file out.txt] [--no-hp]       (exit code 1 if a sweep is not reproduced)
  python -I tools/analyze_ghost_sweep.py --validate-timers <trace-with-POKEYDUMP.txt>                         (timers against the debugger's .pokey dumps)

The sweep (34 frames) programs channels 1, 3 and 4 and sets AUDCTL = $84: channel 1 is high-pass filtered by channel 3.  The model, built from the register writes of the trace only
(tools/pokey_timers.py):
  - every channel fires on one global 28-cycle grid; at a fire its output flip-flop toggles and it reloads with the AUDF value at that moment: the next fire is (AUDF + 1) x 28 cycles later
    (validated: the debugger's `.pokey` "cycles until fire" is reproduced exactly in 16,364 of 16,364 readings, from reset, with no dump as input);
  - AUDCTL bit 2: at every fire of channel 3 a latch takes channel 1's output; the audible output of channel 1 is its output XOR the latch (XOR a constant polarity, hp = 1 in every sweep);
  - level = sum of volume x output over channels 1, 3, 4 (AUDC bits 7-5 = 101 pure tone, volume in bits 3-0); channel 2 is silenced by $A8EE.
The start state of the flip-flops of channels 3 and 4 (c3, c4) is DERIVED (OV-13a, tools/pokey_noise.py): Altirra's renderer sets the noise flip-flop of an idle noise-mode channel to the poly9/17 bit at
every poly5-gated fire and toggles it at every fire of a tone, so a channel entering pure tone starts at the poly bit of its last gated fire (a function of that fire's cycle and of T0, the
SKCTL := 3 write of the OS boot).  The analysis still FITS the four (c3, c4) assignments per sweep from the recording and then reports how the PREDICTED assignment does against the audio
(correlation >= 0.93, at least 90% of the sweeps).  Also checked: EACH sweep is reproduced by one of the four assignments, that this assignment is clearly distinct from all others (margin to the
runner-up), that the high-pass polarity is the same constant everywhere, and that the global time offset is about zero (the anchor is the first fire of the start tune).
Comparison: the simulated level (0/1 outputs, so the amplitude scale is expected near 2k, k = the level of one volume unit) is averaged to the recording's sample rate, both signals are
band-passed (100 Hz - 5 kHz) and compared by the normalised cross-correlation within +-4 ms.
"""
import bisect
import collections
import itertools
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_tail_sound as T  # noqa: E402
import analyze_tune_wav as W  # noqa: E402
import pokey_noise as PN  # noqa: E402
import pokey_timers as PT  # noqa: E402

import video as V  # noqa: E402  (NTSC by default, PAL with PACMAN_VIDEO=pal: OV-42)
CPU = V.CPU                     # NTSC: the CPU clock, 1,789,772.727 Hz (1,789,773 drifts by one audio sample in 150 s: OV-14)
FRAME_CYC = V.FRAME_CYC
TICK = 28
PHASE = 26                      # residue of the fire grid in the cycle stamps of the trace (measured from the debugger dumps: all 16,000+ readings agree)
CORR_MIN = 0.93                # the verified chain (non-linear mixer + AC coupling, exact NTSC clock) gives 0.951-0.964 over the 87 sweeps; wrong start-bit assignments score <= 0.4
PER_SWEEP = []
PER_SWEEP_INFO = []
PRED_SUMMARY = []               # (sweeps whose predicted start bits equal the best fit, sweeps with the predicted bits at corr >= CORR_MIN, sweeps) per recording
FIXED = None                    # (variant, (c3, c4, hpc)) from --fixed: use constants fitted on another recording, no refit


# Altirra's non-linear mixer (src/ATAudio/source/pokey.cpp, mbNonlinearMixingEnabled; OV-13b): the summed level x of all channels' volume bits (uneven weights, normalised so that four channels at
# full volume add to 1) goes through a saturation curve.  Returned in "volume units" (one unit = the level of volume bit weight 1 in the linear region = 0.56 / 4 / 8.24).
BIT_LEVELS = (0.12 / 8.24, 0.26 / 8.24, 0.56 / 8.24)
LINEAR_THRESHOLD, CURVE_FACTOR = 0.14, 2.85
UNIT = 0.56 / 8.24 / 4


def altirra_level(n0, n1, n23):
    x = n0 * BIT_LEVELS[0] + n1 * BIT_LEVELS[1] + n23 * BIT_LEVELS[2]
    y = np.where(x < LINEAR_THRESHOLD, x, LINEAR_THRESHOLD + (1.0 - np.exp(-CURVE_FACTOR * (x - LINEAR_THRESHOLD))) / CURVE_FACTOR)
    return y / UNIT


GAIN_P = 0.5                    # 'cfggain' mixer: probability that another channel is high when the gain of one channel is averaged (OV-13e)
_GAIN_CACHE = {}


def _curve(vols):
    n0 = sum(v & 1 for v in vols)
    n1 = sum((v >> 1) & 1 for v in vols)
    n23 = sum(((v >> 2) & 1) + 2 * ((v >> 3) & 1) for v in vols)
    return float(altirra_level(np.float64(n0), np.float64(n1), np.float64(n23)))


def config_gains(vols, p=None):
    """gain of each channel of a configuration (volumes `vols`, 0 = not playing): the amplitude Altirra's table gives it when each OTHER channel is high with probability p, as a fraction of its linear amplitude"""
    p = GAIN_P if p is None else p
    key = (tuple(vols), p)
    if key in _GAIN_CACHE:
        return _GAIN_CACHE[key]
    out = []
    for i, v in enumerate(vols):
        if v == 0:
            out.append(1.0)
            continue
        oth = [w for j, w in enumerate(vols) if j != i and w]
        tot = 0.0
        for st in __import__("itertools").product((0, 1), repeat=len(oth)):
            pr = 1.0
            on = []
            for w, sbit in zip(oth, st):
                pr *= p if sbit else 1 - p
                if sbit:
                    on.append(w)
            tot += pr * (_curve(on + [v]) - _curve(on))
        out.append(tot / v)
    _GAIN_CACHE[key] = out
    return out


class Hist:
    def __init__(self, init, writes):
        self.t = [-1] + [c for c, _ in writes]
        self.v = [init] + [v for _, v in writes]

    def at(self, c):
        return self.v[bisect.bisect_right(self.t, c) - 1]


class Model:
    def __init__(self, sndw):
        self.sndw = sndw
        ctl_w, prev, ctl_changes = sorted((c, v) for (c, r, v, pc) in sndw if r == 8), 0, []
        for (c, v) in ctl_w:
            if v != prev:
                ctl_changes.append(c)
            prev = v
        self.timers = {i: PT.Timer(sorted((c, v) for (c, r, v, pc) in sndw if r == 2 * (i - 1)), PHASE, ctl_changes) for i in (1, 2, 3, 4)}
        self.audc = {i: Hist(0, sorted((c, v) for (c, r, v, pc) in sndw if r == 2 * (i - 1) + 1)) for i in (1, 2, 3, 4)}
        self.ctl = Hist(0, sorted((c, v) for (c, r, v, pc) in sndw if r == 8))

    def parity(self, i, t):
        n = PN.ecount(self.timers[i], t)
        return 0 if n is None else (n & 1)

    def mixed(self, c_a, c_b, consts, variant, hp_on, hpc=0):
        """-> (breakpoints, mixed level in volume units) for the window [c_a, c_b]; consts = flip-flop constants of channels 1, 3, 4."""
        fires = {i: PN.edges(self.timers[i], c_a, c_b + 1) for i in (1, 3, 4)}
        out0 = {i: consts[i] ^ self.parity(i, c_a - 1) for i in (1, 3, 4)}
        # high-pass latch: channel 1's output at the last fire of channel 3 before the window
        prev3 = PN.edges(self.timers[3], c_a - 8000, c_a)
        if prev3:
            t3 = prev3[-1]
            latch = consts[1] ^ self.parity(1, t3 if variant == 0 else t3 - 1)
        else:
            latch = out0[1]
        seq = []
        for k, c in enumerate(fires[1]):
            seq.append((c + CH1_DT, 0 if variant == 0 else 1, 1, out0[1] ^ ((k + 1) & 1)))
        f3 = fires[3]
        for k3, c in enumerate(f3):
            tl = c + HP_DT
            seq.append((tl, 1 if variant == 0 else 0, 3, None))
        seq.sort()
        o1 = out0[1]
        f_t, f_v = [c_a], [(o1 ^ latch ^ hpc) if (hp_on and self.ctl.at(c_a) & 4) else o1]
        for (c, _, kind, val) in seq:
            if kind == 1:
                o1 = val
            else:
                latch = o1
            cur = (o1 ^ latch ^ hpc) if (hp_on and self.ctl.at(c) & 4) else o1
            if cur != f_v[-1]:
                f_t.append(c)
                f_v.append(cur)
        chans = {1: (np.array(f_t, dtype=np.float64), np.array(f_v, dtype=np.int8))}
        for i in (3, 4):
            chans[i] = (np.array([c_a] + fires[i], dtype=np.int64), np.array([out0[i]] + [out0[i] ^ ((k + 1) & 1) for k in range(len(fires[i]))], dtype=np.int8))
        bps = {c_a, c_b}
        for i in chans:
            bps.update(chans[i][0].tolist())
        for i in (1, 3, 4):
            bps.update(c for c in self.audc[i].t[1:] if c_a <= c <= c_b)
        bps = np.array(sorted(bps), dtype=np.float64)
        total = np.zeros(len(bps))
        nbits = np.zeros((3, len(bps)))                  # per breakpoint: number of channels with volume bit 0, bit 1, and (bit 2 + 2 x bit 3) set and output high (Altirra's mix-table index)
        for i in (1, 3, 4):
            tt, vv = chans[i]
            idx = np.searchsorted(tt, bps, side="right") - 1
            st = vv[np.clip(idx, 0, len(vv) - 1)].astype(np.float64)
            ac = np.array([self.audc[i].at(int(c)) for c in bps])
            vol = np.where((ac >> 5) == 5, ac & 15, 0).astype(np.float64)
            if getattr(self, 'only', None) is not None and i not in self.only:
                continue                                       # diagnostics (OV-13e): render a subset of the channels
            if i == 1 and getattr(self, 'ch1_mode', 'hp') == 'none':
                continue
            if i != 1 and getattr(self, 'ch1_mode', 'hp') == 'only':
                continue
            total += st * vol
            iv = vol.astype(np.int64)
            nbits[0] += st * (iv & 1)
            nbits[1] += st * ((iv >> 1) & 1)
            nbits[2] += st * (((iv >> 2) & 1) + 2 * ((iv >> 3) & 1))
        if getattr(self, 'mixer', 'linear') == 'altirra':
            total = altirra_level(nbits[0], nbits[1], nbits[2])
        elif getattr(self, 'mixer', 'linear') == 'invtable':
            # OV-13e: Altirra's table applied to the channels that are LOW (the output stage is inverting): level = - f(channels that are low) (negative-going table value)
            allb = np.zeros((3, len(bps)))
            for i in (1, 3, 4):
                ac = np.array([self.audc[i].at(int(c)) for c in bps])
                iv = np.where((ac >> 5) == 5, ac & 15, 0).astype(np.int64)
                allb[0] += iv & 1
                allb[1] += (iv >> 1) & 1
                allb[2] += ((iv >> 2) & 1) + 2 * ((iv >> 3) & 1)
            total = -altirra_level(allb[0] - nbits[0], allb[1] - nbits[1], allb[2] - nbits[2])          # no f(all) term: a volume change of a channel that is high changes nothing
        elif getattr(self, 'mixer', 'linear') == 'cfggain':
            # OV-13e: each channel keeps its linear shape and is scaled by the gain Altirra's table gives it on average in the configuration (the other channels high with probability GAIN_P)
            vv = {}
            for i in (1, 3, 4):
                ac = np.array([self.audc[i].at(int(c)) for c in bps])
                vv[i] = np.where((ac >> 5) == 5, ac & 15, 0).astype(np.int64)
            total = np.zeros(len(bps))
            keys = np.stack([vv[1], vv[3], vv[4]], axis=1)
            uk, inv = np.unique(keys, axis=0, return_inverse=True)
            inv = inv.reshape(-1)
            gtab = np.array([config_gains([int(a) for a in row]) for row in uk])
            for col, i in enumerate((1, 3, 4)):
                tt, vvv = chans[i]
                idx = np.searchsorted(tt, bps, side="right") - 1
                st = vvv[np.clip(idx, 0, len(vvv) - 1)].astype(np.float64)
                total += st * vv[i] * gtab[inv, col]
        elif getattr(self, 'mixer', 'linear') == 'peakgain':
            # OV-13d: the waveform is the plain LINEAR sum, scaled by the gain that Altirra's curve gives to the configuration's PEAK level (all playing channels high): g = f(peak) / peak
            allb = np.zeros((3, len(bps)))
            vsum = np.zeros(len(bps))
            for i in (1, 3, 4):
                ac = np.array([self.audc[i].at(int(c)) for c in bps])
                iv = np.where((ac >> 5) == 5, ac & 15, 0).astype(np.int64)
                vsum += iv
                allb[0] += iv & 1
                allb[1] += (iv >> 1) & 1
                allb[2] += ((iv >> 2) & 1) + 2 * ((iv >> 3) & 1)
            g = np.where(vsum > 0, altirra_level(allb[0], allb[1], allb[2]) / np.maximum(vsum, 1), 1.0)
            total = total * g
        return bps, total


def render(bps, total, c_start, n, step):
    """Average of the piecewise-constant level over n output intervals starting at cycle c_start (interval length `step` cycles)."""
    cum = np.concatenate([[0.0], np.cumsum(total[:-1] * np.diff(bps))])
    edges = c_start + np.arange(n + 1) * step
    val = np.interp(edges, bps, cum, left=0.0, right=cum[-1])
    return np.diff(val) / step


CH1_DT = 0.0                    # cycles added to channel 1's own edges (experiments of OV-13d; the other channels stay on their fires)
HP_DT = 0.0                     # cycles added to the high-pass latch updates (channel 3 fires) against channel 1's own edges; Altirra: -1.5 (the update is merged at fire + 0.5, the output edges at fire + 2)
MIXER_CLAMP = False             # set by --mixer altirra --ac
INVERTED = False                # the mixer 'invtable': the level is +f(all) - f(low channels), i.e. the table's (negative-going) value is +2.1 x level, not -2.1 x level
AC_COUPLING = True              # --no-ac switches it off: Altirra's AC-coupled output stage (pokey.cpp: time constant 2.597 ms, applied per 28-cycle half-cycle sample)
AC_TAU = 0.0025968510736001341332478644258
HALF_CYCLE_RATE = V.HALF_CYCLE_RATE


def render_ac(bps, total, c_a, c_start, n, step):
    """as render(), but the level first goes through Altirra's AC-coupling high-pass at its own rate (one sample per 28 cycles: y[n] = c y[n-1] + level[n] - level[n-1], c = exp(-1/(63920 tau)))"""
    nf = int((bps[-1] - c_a) // TICK) + 1
    fine = render(bps, total, c_a, nf, TICK)
    if MIXER_CLAMP:
        sg = 2.1 if INVERTED else -2.1
        fine = sg * UNIT * fine                        # volume units -> Altirra's negative-going table units, in which the output clamp is defined
    d = np.diff(fine, prepend=fine[0])
    c = np.exp(-1.0 / (HALF_CYCLE_RATE * AC_TAU))
    kern = c ** np.arange(4000)
    m = 1 << int(np.ceil(np.log2(nf + len(kern))))
    y = np.fft.irfft(np.fft.rfft(d, m) * np.fft.rfft(kern, m), m)[:nf]
    if MIXER_CLAMP:
        y = np.clip(y, -0.65, 0.5) / (sg * UNIT)       # the AC-coupled output is clamped to [-0.65, 0.5] (pokeyrenderer.cpp PostFilter); back to volume units, sign restored
    cum = np.concatenate([[0.0], np.cumsum(y)])
    edges = (c_start - c_a + np.arange(n + 1) * step) / TICK
    val = np.interp(edges, np.arange(nf + 1), cum, left=0.0, right=cum[-1])
    return np.diff(val) / (step / TICK)


BANDLIMITED = False             # --bandlimited: synthesise the 100 Hz - 5 kHz signal directly from the edge list (no resampling alias), see render_bl


def render_bl(bps, total, c_start, n, step, ac=True, lo=100.0, hi=5000.0):
    """The piecewise-constant level (breakpoints bps in cycles, levels total) as the signal band-limited to [lo, hi] Hz, sampled at the recording's rate: the Fourier series of the step train is exact, so
    there is no aliasing of the narrow pulses of the high-pass channel (the box average of render() folds their high-frequency content into the band).  AC coupling is applied as its transfer function."""
    rate = CPU / step
    T = n / rate
    t = (np.asarray(bps, dtype=np.float64) - c_start) / CPU
    lev = np.asarray(total, dtype=np.float64)
    d = np.diff(lev)
    te = t[1:]
    m = (te > 0) & (te < T) & (d != 0)
    te, d = te[m], d[m]
    # level at the window start and the wrap-around step that closes the period (it is windowed away by bandpass() later)
    lev0 = lev[max(int(np.searchsorted(t, 0.0, side="right")) - 1, 0)]
    k = np.arange(len(np.fft.rfftfreq(n, 1.0 / rate)))
    f = k / T
    sel = np.where((f >= lo * 0.8) & (f <= hi * 1.2))[0]
    # spectrum of x'(t) = sum d_i delta(t - t_i) - (sum d_i) delta(t): S_k = D_k / (j 2 pi f_k)
    S = np.zeros(len(k), dtype=np.complex128)
    chunk = 512
    for a in range(0, len(sel), chunk):
        ks = sel[a:a + chunk]
        ph = np.exp(-2j * np.pi * np.outer(f[ks], te))
        D = ph @ d - d.sum()
        S[ks] = rate * D / (2j * np.pi * f[ks])        # rfft bin = N x Fourier coefficient = N D_k / (T j 2 pi f_k) = rate D_k / (j 2 pi f_k)
    if ac:
        w = 2 * np.pi * f * AC_TAU
        S = S * (1j * w / (1 + 1j * w))
    S[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(S, n) * 1.0


def bandpass(x, rate, lo=100.0, hi=5000.0):
    n = len(x)
    X = np.fft.rfft(x * np.hanning(n))
    f = np.fft.rfftfreq(n, 1.0 / rate)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, n)


def best_corr(a, b, max_lag):
    best = (-2.0, 0)
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            aa, bb = a[lag:], b[:len(b) - lag]
        else:
            aa, bb = a[:lag], b[-lag:]
        n = min(len(aa), len(bb))
        aa, bb = aa[:n], bb[:n]
        da, db = np.linalg.norm(aa), np.linalg.norm(bb)
        if da > 0 and db > 0:
            c = float(np.dot(aa, bb) / (da * db))
            if c > best[0]:
                best = (c, lag)
    return best


def xcorr(a, b, max_lag):
    """normalised cross-correlation for lags -max_lag..max_lag: value at lag l = sum a[n] b[n+l] / (|a| |b|) over the overlap (b is the recording, a the model)."""
    n = len(a)
    m = 1 << int(np.ceil(np.log2(2 * n)))
    A = np.fft.rfft(a, m)
    B = np.fft.rfft(b, m)
    full = np.fft.irfft(np.conj(A) * B, m)
    out = np.empty(2 * max_lag + 1)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    for l in range(-max_lag, max_lag + 1):
        out[l + max_lag] = full[l % m] / (na * nb) if na > 0 and nb > 0 else 0.0
    return out


def parse_dumps(path):
    """-> list of dict(c0, ch={i: (audf, audc, out, cycles until fire, period)}, ctl, f) from the POKEYDUMP blocks of a trace."""
    dumps, cur = [], None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = re.match(r"POKEYDUMP f=(\d+) vp=(\d+) hp=(\d+)$", line)
            if m:
                cur = dict(c0=int(m.group(1)) * FRAME_CYC + int(m.group(2)) * 114 + int(m.group(3)), ch={}, ctl=None, f=int(m.group(1)))
                continue
            if cur is not None:
                m = re.match(r"AUDF(\d): ([0-9A-F]{2})\s+AUDC\d: ([0-9A-F]{2})\s+Output: (\d)\s+\((\d+) cycles until fire\) \(passive: (\d+) cycles\)", line)
                if m:
                    cur["ch"][int(m.group(1))] = (int(m.group(2), 16), int(m.group(3), 16), int(m.group(4)), int(m.group(5)), int(m.group(6)))
                    continue
                m = re.match(r"AUDCTL: ([0-9A-F]{2})", line)
                if m:
                    cur["ctl"] = int(m.group(1), 16)
                    if len(cur["ch"]) == 4:
                        dumps.append(cur)
                    cur = None
    return dumps


def validate_timers(path):
    sndw, events, last = T.parse_trace(path)
    dumps = parse_dumps(path)
    mod = Model(sndw)
    tot = collections.Counter()
    ok = collections.Counter()
    bad = []
    for d in dumps:
        for i in (1, 2, 3, 4):
            pred = mod.timers[i].pending(d["c0"]) - d["c0"]
            tot[i] += 1
            if pred == d["ch"][i][3]:
                ok[i] += 1
            elif len(bad) < 5:
                bad.append("f=%d ch%d predicted %d, dumped %d" % (d["f"], i, pred, d["ch"][i][3]))
    print("Timer validation against %d .pokey dumps (cycles until the next fire, from the register writes alone, grid phase %d):" % (len(dumps), PHASE))
    for i in (1, 2, 3, 4):
        print("  channel %d: %d of %d exact" % (i, ok[i], tot[i]))
    for b in bad:
        print("   miss", b)
    return 0 if all(ok[i] == tot[i] for i in tot) and dumps else 1


def main():
    args = list(sys.argv[1:])
    if args and args[0] == "--validate-timers":
        return validate_timers(args[1])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    global FIXED
    if "--fixed" in args:
        i = args.index("--fixed")
        v_ = [int(t_) for t_ in args[i + 1].split(",")]
        FIXED = (v_[0], tuple(v_[1:4]))
        del args[i:i + 2]
    global BANDLIMITED
    if "--bandlimited" in args:
        BANDLIMITED = True
        args.remove("--bandlimited")
    global HP_DT
    if "--hp-dt" in args:
        i = args.index("--hp-dt")
        HP_DT = float(args[i + 1])
        del args[i:i + 2]
    global GAIN_P
    if "--gain-p" in args:
        i = args.index("--gain-p")
        GAIN_P = float(args[i + 1])
        del args[i:i + 2]
    mixer = "invtable"
    if "--mixer" in args:
        i = args.index("--mixer")
        mixer = args[i + 1]
        del args[i:i + 2]
    global CURVE_FACTOR, LINEAR_THRESHOLD, AC_COUPLING
    if "--no-ac" in args:
        AC_COUPLING = False
        args.remove("--no-ac")
    for flag, name in (("--curve", "CURVE_FACTOR"), ("--thr", "LINEAR_THRESHOLD")):
        if flag in args:
            i = args.index(flag)
            globals()[name] = float(args[i + 1])
            del args[i:i + 2]
    hp_on = "--no-hp" not in args
    if not hp_on:
        args.remove("--no-hp")
    wav, trace = args[0], args[1]
    out = []
    P = lambda *a: out.append(" ".join(str(x) for x in a))
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    # ---- alignment: the first tone of the start tune, as tools/analyze_tail_sound.py
    f_tune = next(f for (f, n, v) in events if n == "TUNE" and v == 0)
    c_w2 = next(c for (c, r, v, pc) in sndw if pc == 0xA7E8 and c // FRAME_CYC == f_tune)
    audf2 = next(v for (c, r, v, pc) in sndw if c == c_w2)
    res = W.analyze(x, rate)
    ss = W.Spec(x, rate)
    k = float(np.median([ss.mag(res["t0"], res["P"], row["i"])[1] / (8 if row["f1"] > 0 else 4) for row in res["rows"] if row["kind"] == "tone" and (row["f1"] > 0) != (row["f2"] > 0)]))
    i0, i1 = int((res["t0"] - 0.03) * rate), int((res["t0"] + 0.03) * rate)
    t_on = (i0 + int(np.where(np.abs(x[i0:i1]) > 0.5 * k * 4)[0][0])) / rate
    t_w2 = t_on                       # the first fire after the write is the first audible edge (measured: the fitted global offset against this anchor is ~0)
    Tt = lambda c: t_w2 + (c - c_w2) / CPU
    step = CPU / rate
    P("Recording %.2f s; level of one volume unit k = %.5f; the first audible edge of the start tune is taken as the first fire after its write, at %.4f s." % (len(x) / rate, k, t_w2))
    mod = Model(sndw)
    mod.mixer = mixer
    global MIXER_CLAMP, INVERTED
    INVERTED = (mixer == "invtable")
    MIXER_CLAMP = (mixer in ("altirra", "invtable") and AC_COUPLING and "--no-clamp" not in sys.argv)
    P("Mixer: %s." % ("Altirra's non-linear mix table (uneven volume bits, saturation)" if mixer == "altirra" else "the linear sum of the volumes scaled by the gain of Altirra's curve at the peak level (OV-13d)" if mixer == "peakgain" else "each channel linear, scaled by the gain Altirra's table gives it on average in the configuration (OV-13e, p = %.2f)" % GAIN_P if mixer == "cfggain" else "Altirra's table indexed by the channels that are LOW (OV-13e)" if mixer == "invtable" else "linear sum of the volumes"))
    # ---- the sweeps: from the A8EE write (AUDC2 := 0) to the AUDCTL := 0 write of the end ($B088)
    sweeps = []
    for (c, r, v, pc) in sndw:
        if pc == 0xA8EE:
            c_end = next((c2 for (c2, r2, v2, pc2) in sndw if pc2 == 0xB088 and c2 > c), None)
            if c_end is None or c_end > (last_frame - 12) * FRAME_CYC:
                continue
            if Tt(c_end) + 0.05 > len(x) / rate:
                continue
            sweeps.append((c, c_end))
    P("Ghost-eaten sweeps in this trace that can be compared: %d (of %d GHOST_EATEN events)." % (len(sweeps), sum(1 for e in events if e[1] == "GHOST_EATEN")))
    prepared = []
    for (c_a, c_b) in sweeps:
        t_a, t_b = Tt(c_a), Tt(c_b)
        n0 = int(np.ceil((t_a + 0.012) * rate))                    # skip the first 12 ms: the tail of the sounds before the collision (AC coupling)
        n1 = int(np.floor(t_b * rate))
        c_start = c_a + int(round((n0 / rate - t_a) * CPU))
        prepared.append((c_a, c_b, t_a, n0, n1, c_start, bandpass(x[n0:n1], rate)))
    # Unknowns: the start polarity of the flip-flops of channels 3 and 4 (the debugger shows no rule for them: they behave like independent bits per sweep), the polarity of the
    # high-pass output (hpc) and the order of simultaneous events (variant).  Everything else (fire times, volumes, AUDCTL) comes from the register writes.
    MAXLAG = int(0.004 * rate)
    combos = [(c3, c4, hpc) for c3 in (0, 1) for c4 in (0, 1) for hpc in (0, 1)]
    variants = (0, 1)
    table = {}
    for var in variants:
        for cb in combos:
            mats, scs = [], []
            for (c_a, c_b, t_a, n0, n1, c_start, br) in prepared:
                bps, total = mod.mixed(c_a, c_b, {1: 0, 3: cb[0], 4: cb[1]}, var, hp_on, cb[2])
                bm = bandpass(render_bl(bps, total, c_start, n1 - n0, step, ac=AC_COUPLING) if BANDLIMITED else (render_ac(bps, total, c_a, c_start, n1 - n0, step) if AC_COUPLING else render(bps, total, c_start, n1 - n0, step)), rate)
                mats.append(xcorr(bm, br, MAXLAG))
                scs.append(bm)
            table[(var, cb)] = (np.array(mats), scs)
    # global time offset: median over sweeps of the lag of each sweep's best fit
    best_lags = []
    for idx in range(len(prepared)):
        top = max(((float(m[idx].max()), int(m[idx].argmax()) - MAXLAG) for m, _ in table.values()), key=lambda t_: t_[0])
        best_lags.append(top[1])
    lag = int(np.median(best_lags))
    P("Global time offset of the recording against the cycle timeline (median of the best lag of every sweep): %+.3f ms (spread %+.3f..%+.3f ms)." % (lag / rate * 1000, min(best_lags) / rate * 1000, max(best_lags) / rate * 1000))
    for var in variants:
        med = [float(np.median([max(table[(var, cb)][0][idx][lag + MAXLAG] for cb in combos) for idx in range(len(prepared))]))]
        P("Event-order variant %d: median over sweeps of the best fit %.4f" % (var, med[0]))
    var = max(variants, key=lambda v_: np.median([max(table[(v_, cb)][0][idx][lag + MAXLAG] for cb in combos) for idx in range(len(prepared))]))
    rows = []
    P("\nPer sweep at the global offset, variant %d: best of the 8 (c3, c4, high-pass polarity) assignments, the runner-up (best different assignment), and the best assignment with the other high-pass polarity:" % var)
    for idx, (c_a, c_b, t_a, n0, n1, c_start, br) in enumerate(prepared):
        cands = sorted(((float(table[(var, cb)][0][idx][lag + MAXLAG]), cb) for cb in combos), reverse=True)
        best_c, best_cb = cands[0]
        runner = cands[1][0]
        other_hp = max(c for c, cb in cands if cb[2] != best_cb[2])
        bm = table[(var, best_cb)][1][idx]
        if lag >= 0:
            aa, bb = bm[:len(bm) - lag], br[lag:]
        else:
            aa, bb = bm[-lag:], br[:len(br) + lag]
        sc = float(np.dot(aa, bb) / max(np.dot(aa, aa), 1e-12))
        rows.append(dict(f=c_a // FRAME_CYC, c_a=c_a, t=t_a, corr=best_c, bits=best_cb, runner=runner, other_hp=other_hp, scale=sc, lag=lag / rate * 1000))
        P("  f=%6d %8.3f s  best %.4f with (c3, c4, hp) = %s   runner-up %.4f   other high-pass polarity %.4f   scale/2k %.3f" % (rows[-1]["f"], t_a, best_c, best_cb, runner, other_hp, sc / (2 * k)))
    PER_SWEEP_INFO.extend((r["c_a"], r["bits"], r["corr"]) for r in rows)
    # ---- OV-13a: the start bits PREDICTED from Altirra's noise flip-flop rule (tools/pokey_noise.py), no fit: only the audio decides how good the prediction is
    n_exact, n_good, pred_rows = 0, 0, []
    for idx, (c_a, c_b, t_a, n0, n1, c_start, br) in enumerate(prepared):
        pb = (PN.start_constant(mod, 3, c_a, c_b), PN.start_constant(mod, 4, c_a, c_b), 1)
        if None in pb:
            pred_rows.append((c_a, pb, None))
            continue
        cp = float(table[(var, pb)][0][idx][lag + MAXLAG])
        pred_rows.append((c_a, pb, cp))
        n_exact += int(pb == rows[idx]["bits"])
        n_good += int(cp >= CORR_MIN)
    if pred_rows:
        P("\nPredicted start bits (tools/pokey_noise.py: the poly bit of the last gated fire before the tone starts; only the audio is compared): equal to the best-fit assignment in %d of %d sweeps; correlation >= %.2f in %d of %d; per sweep (frame, predicted (c3, c4), correlation, best-fit correlation):" % (n_exact, len(rows), CORR_MIN, n_good, len(rows)))
        for r, (c_a, pb, cp) in zip(rows, pred_rows):
            P("  f=%6d predicted %s  corr %s  (best fit %s: %.4f)%s" % (c_a // FRAME_CYC, pb[:2] if cp is not None else None, "%.4f" % cp if cp is not None else "n/a", r["bits"][:2], r["corr"], "" if pb == r["bits"] else "   <- differs"))
        PRED_SUMMARY.append((n_exact, n_good, len(rows)))
    # level: RMS of the model for the four start-polarity candidates (high-pass polarity 1) against the recording, in units of 2k (so that 1.0 = the linear ideal)
    spread, err_best, err_mean = [], [], []
    for idx, (c_a, c_b, t_a, n0, n1, c_start, br) in enumerate(prepared):
        rr = float(np.sqrt(np.mean(br ** 2)))
        rm = {cb: float(np.sqrt(np.mean(table[(var, cb)][1][idx] ** 2))) * 2 * k for cb in combos if cb[2] == 1}
        spread.append(max(rm.values()) / min(rm.values()))
        best = rows[idx]["bits"]
        err_best.append(rm[best] / rr)
        err_mean.append(float(np.mean(list(rm.values()))) / rr)
        rows[idx]["rms_rec"], rows[idx]["rms_model"] = rr, rm[best]
    P("\nLevel (RMS, band 100 Hz-5 kHz): the four start-polarity candidates differ by a factor %.2f (median; min %.2f, max %.2f) between the lowest and the highest; the candidate chosen by the waveform has a model RMS of %.3f x the recording (median; min %.3f, max %.3f)." % (
      np.median(spread), min(spread), max(spread), np.median(err_best), min(err_best), max(err_best)))
    cnt = collections.Counter((r["bits"][0], r["bits"][1]) for r in rows)
    P("\nStart polarities (c3, c4) of the best assignments over the sweeps: %s;  high-pass polarity bit = 1 in %d of %d sweeps." % (dict(sorted(cnt.items())), sum(1 for r in rows if r["bits"][2] == 1), len(rows)))
    P("Correlation over the sweeps: min %.4f, median %.4f; margin to the runner-up: min %.3f; scale/2k: median %.3f (min %.3f, max %.3f)." % (min(r["corr"] for r in rows), np.median([r["corr"] for r in rows]), min(r["corr"] - r["runner"] for r in rows),
      np.median([r["scale"] / (2 * k) for r in rows]), min(r["scale"] / (2 * k) for r in rows), max(r["scale"] / (2 * k) for r in rows)))
    problems = []
    if not rows:
        problems.append("no sweep could be compared")
    if abs(lag) / rate * 1000 > 0.2:
        problems.append("global offset %+.3f ms is not ~0" % (lag / rate * 1000))
    for r in rows:
        if r["corr"] < CORR_MIN:
            problems.append("sweep at frame %d: best correlation %.3f below %.2f" % (r["f"], r["corr"], CORR_MIN))
        if r["corr"] - r["runner"] < 0.15:
            problems.append("sweep at frame %d: the best assignment is not distinct (margin %.3f to the runner-up)" % (r["f"], r["corr"] - r["runner"]))
        if r["bits"][2] != 1:
            problems.append("sweep at frame %d: the high-pass polarity bit is %d, not the constant 1" % (r["f"], r["bits"][2]))
        lo_hi = (0.85, 1.15) if mixer == "altirra" else (0.7, 1.0)
        if not (lo_hi[0] <= r["scale"] / (2 * k) <= lo_hi[1]):
            problems.append("sweep at frame %d: scale %.3f x 2k outside %.2f..%.2f" % (r["f"], r["scale"] / (2 * k), lo_hi[0], lo_hi[1]))
    if pred_rows and n_good < 0.9 * len(rows):
        problems.append("the predicted start bits reproduce only %d of %d sweeps (correlation >= %.2f), below 90%%" % (n_good, len(rows), CORR_MIN))
    P("\nPROBLEMS:", "none" if not problems else "")
    for p in problems:
        P("  " + p)
    text = "\n".join(out)
    print(text)
    if summ:
        with open(summ, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
