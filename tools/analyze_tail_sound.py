"""Audit of ALL sound in a recording of Altirra's audio, not only the start tune (docs/21).  Usage:
  python -I tools/analyze_tail_sound.py [recording.wav] [trace.txt] [--summary-file out.txt]
defaults: analysis/start-tune-recorded.wav and analysis/raw-logs/tune-record.txt (both made by tools/record_tune.ps1).

1. Reads every write to the POKEY registers $D200-$D208 from the trace (SNDW lines: address, value, PC, frame, beam position).
2. Gives every write its exact emulated time: frame x 29868 cycles + vpos x 114 + hpos (an NTSC frame is 262 lines of 114 cycles at 1,789,773 Hz).  The one unknown, where the
   emulated clock sits in the recording, is found by correlating the on/off pattern the writes predict with the level of the recording (0.5 ms blocks, +-40 ms around the
   start tune found by tools/analyze_tune_wav.py); the shift is reported.
3. Builds SEGMENTS of constant register state (all four AUDF/AUDC pairs + AUDCTL); changes less than 1 ms apart (the 2-4 register writes of one sound) count as one change.
   Only pure-tone (AUDC bits 7-5 = 101) and silent channels are modelled; any other mode, any non-zero AUDCTL and any volume-only channel is reported as "not modelled".
4. For every segment compares the recording with what the registers predict: the pitch of each sounding channel (f = 63921 / (2 (AUDF + 1)) Hz, in cents; for segments of
   at least 40 ms) and the level (RMS = k x volume per channel, k calibrated on the start tune's single-voice steps in the same recording; the real DAC is slightly
   non-linear, so 25 % is allowed).  A segment where the registers say silence must be silent in the recording (that finds sound that has no register write behind it).
5. Lists the program counters that write each kind of sound.
Exit code 1 if a segment is outside the limits or something is not modelled.
"""
import bisect
import collections
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_tune_wav as W  # noqa: E402
import render_start_tune as R  # noqa: E402

import video as V  # noqa: E402
CPU = V.CPU if V.PAL else 1789773.0
FRAME_CYC = V.FRAME_CYC
BASE = R.BASE
LEVEL_TOL = 0.25
CENTS_TOL = 30.0
SILENT_RMS = 0.005                  # silence: the quietest sound the game can make is a volume-1 square wave, RMS 0.0086 (measured: 0.0086 per volume unit); leakage of a slow offset measured up to 0.0033
GROUP_S = 0.001                     # register writes closer together than this are one change
MIN_LEVEL_S, MIN_PITCH_S, LONG_S = 0.012, 0.012, 0.040          # shorter than MIN_LEVEL_S: not judged; from LONG_S on the tight pitch limit applies
MIN_CYCLES = 3                      # a tone is measured only if the window holds at least this many cycles of it
SPECTRUM_CYCLES = 6                 # below this many cycles in a short window the least-squares fit (with the square wave's harmonics) is used instead of a spectrum peak
UNRESOLVED_RATIO = 1.15             # residual at the expected pitch / residual at the best pitch: at or below this the window cannot resolve the pitch
SHORT_CENTS_TOL = 80.0              # pitch limit for segments shorter than LONG_S (about 14 ms = one frame; one AUDF step of the siren is about 36 cents)
END_MARGIN_S = 0.0005
TAU = 0.0025                        # decay time constant of Altirra's AC-coupled output after a drop in level


def parse_trace(path):
    sndw, events, last_frame = [], [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = re.match(r"SNDW a=\$([0-9A-F]{4}) v=\$([0-9A-F]{2}) pc=\$([0-9A-F]{4}) f=(\d+) vp=(\d+) hp=(\d+)$", line)
            if m:
                f = int(m.group(4))
                if int(m.group(1), 16) - 0xD200 > 8:
                    continue                                          # POKEY registers that are not sound ($D20B POTGO is written by the OS every frame)
                sndw.append((f * FRAME_CYC + int(m.group(5)) * 114 + int(m.group(6)), int(m.group(1), 16) - 0xD200, int(m.group(2), 16), int(m.group(3), 16)))
                continue
            m = re.match(r"FR f=(\d+) .* t1=\d+$", line)           # complete frame lines only (the last line may be cut off)
            if m:
                last_frame = int(m.group(1))
                continue
            m = re.match(r"(TUNE|NEWGAME|READY_DRAW|START_PLAY|DEATH_START|DEATH_DONE|INITBOARD_CALL|PELLET|GHOST_EATEN|BONUS_EATEN|BONUS_APPEAR|EXTRA_LIFE|LEVEL_ADV|INIT_BOARD) f=(\d+)( x=(\d+))?$", line)
            if m:
                events.append((int(m.group(2)), m.group(1), int(m.group(4)) if m.group(4) else None))
    sndw.sort(key=lambda w: w[0])
    return sndw, events, last_frame


def build_segments(sndw):
    """Groups of writes -> [dict(c0, c1, st, writers)]: c0 = cycle of the last write of the group (new state complete), c1 = cycle of the first write of the next group."""
    groups, cur = [], None
    for (c, r, v, pc) in sndw:
        if cur and c - cur["c1"] <= GROUP_S * CPU:
            cur["c1"] = c
            cur["w"].append((r, v, pc))
        else:
            cur = dict(c0=c, c1=c, w=[(r, v, pc)])
            groups.append(cur)
    regs = [0] * 9
    segs = [dict(first=-1e18, c0=-1e18, c1=None, st=tuple(regs), wr=collections.defaultdict(set))]
    for g in groups:
        segs[-1]["c1"] = g["c0"]                      # the previous state ends when the first write of the group happens
        for (r, v, pc) in g["w"]:
            regs[r] = v
        wr = collections.defaultdict(set)
        for (r, v, pc) in g["w"]:
            wr[r].add(pc)
        segs.append(dict(first=g["c0"], c0=g["c1"], c1=None, st=tuple(regs), wr=wr))
    # c0 above is the last write of the group; the first write is `first`
    segs[-1]["c1"] = segs[-1]["c0"] + 10 ** 12
    # merge neighbours with the same state (a routine that rewrites the same value every frame)
    out = [segs[0]]
    for s in segs[1:]:
        if s["st"] == out[-1]["st"]:
            out[-1]["c1"] = s["c1"]
            for r, p in s["wr"].items():
                out[-1]["wr"][r] |= p
        else:
            out.append(s)
    return out


def expected_tones(st, with_hp=False):
    """-> (list of (channel, freq, volume), problems)  [, list of high-pass filtered channel-1 tones when with_hp].
    AUDCTL: bit 7 (9-bit polynomial) only matters for the polynomial distortion modes, so it is harmless for pure tones; bit 2 (channel 1 high-pass filtered by channel 3) is handled
    by returning channel 1 separately as a tone of known pitch but UNKNOWN level (the level depends on the phase between channels 1 and 3, which the register writes do not give);
    any other AUDCTL bit is reported as not modelled."""
    tones, prob, hp = [], [], []
    if st[8] & ~0x84 & 0xFF:
        prob.append("AUDCTL=$%02X has bits that are not modelled (only bit 2 and bit 7 are handled)" % st[8])
    for c in range(4):
        f, v = st[c * 2], st[c * 2 + 1]
        vol, dist, vo = v & 15, v >> 5, v & 0x10
        if vol == 0:
            continue
        if vo:
            prob.append("channel %d volume-only ($%02X) is not modelled" % (c + 1, v))
        elif dist != 5:
            prob.append("channel %d AUDC $%02X (distortion %d) is not modelled" % (c + 1, v, dist))
        elif f == 0:
            continue                                   # about 32 kHz: inaudible, a rest
        elif c == 0 and st[8] & 0x04:
            hp.append((1, BASE / (2.0 * (f + 1)), vol))
        else:
            tones.append((c + 1, BASE / (2.0 * (f + 1)), vol))
    return (tones, prob, hp) if with_hp else (tones, prob)


def model_edges(sndw, reg, c_first, c_last):
    """Toggle times (CPU cycles) of a pure-tone channel from its AUDF history: after an underflow the channel reloads from the AUDF value at that moment and the next
    underflow comes (AUDF + 1) 64 kHz ticks (28 cycles each) later.  The first toggle is taken at c_first + (AUDF + 1) ticks (the absolute phase is fitted afterwards as one shift)."""
    ws = [(c, v) for (c, r, v, pc) in sndw if r == reg]
    tt = [c for c, _ in ws]
    vv = [v for _, v in ws]

    def audf(c):
        i = bisect.bisect_right(tt, c) - 1
        return vv[i] if i >= 0 else 0
    out, c = [], c_first
    f = audf(c)
    c += (f + 1) * 28
    while c <= c_last and f != 0:
        out.append(c)
        f = audf(c)
        c += (f + 1) * 28
    return out


def crossings(x, rate, t_a, t_b, lo, hi):
    """Zero crossings (seconds) of the band-passed recording between t_a and t_b (interpolated)."""
    pad = 0.05
    n0, n1 = max(0, int((t_a - pad) * rate)), min(len(x), int((t_b + pad) * rate))
    seg = x[n0:n1].astype(np.float64)
    X = np.fft.rfft(seg)
    fr = np.fft.rfftfreq(len(seg), 1.0 / rate)
    X[(fr < lo) | (fr > hi)] = 0
    y = np.fft.irfft(X, len(seg))
    s = np.sign(y)
    idx = np.where(s[:-1] * s[1:] < 0)[0]
    t = (n0 + idx + y[idx] / (y[idx] - y[idx + 1])) / rate
    return t[(t >= t_a) & (t <= t_b)]


def ls_pitch(seg_x, rate, known, target_f, span_cents=150.0, step_cents=2.0, harmonics=(1, 3, 5, 7)):
    """Pitch of a weak tone beneath other tones whose frequencies are known exactly.
    For each candidate frequency of the target (+-span_cents around target_f) fit, by least squares, sine and cosine terms at the odd harmonics of the target AND of every
    known tone (a square wave has odd harmonics only; amplitude and phase are free) and keep the candidate with the smallest residual.  -> (frequency, residual share of the
    energy at the best candidate, at the expected frequency)."""
    t = np.arange(len(seg_x)) / rate
    t = t - t.mean()
    w = np.hanning(len(seg_x))
    y = seg_x * w

    def cols(f):
        c = []
        for n in harmonics:
            if n * f < rate / 2.2:
                c.append(np.sin(2 * np.pi * n * f * t) * w)
                c.append(np.cos(2 * np.pi * n * f * t) * w)
        return c
    base = []
    for f in known:
        base += cols(f)
    energy = float(np.dot(y, y)) + 1e-30
    best = None
    grid = np.arange(-span_cents, span_cents + 1e-9, step_cents)
    res_ = []
    for cents in grid:
        f = target_f * 2 ** (cents / 1200.0)
        A = np.array(base + cols(f)).T
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        r = y - A @ coef
        res_.append(float(np.dot(r, r)) / energy)
    res_ = np.array(res_)
    j = int(np.argmin(res_))
    cents = grid[j]
    if 0 < j < len(grid) - 1:
        d = res_[j - 1] - 2 * res_[j] + res_[j + 1]
        if d > 0:
            cents += 0.5 * (res_[j - 1] - res_[j + 1]) / d * step_cents
    return target_f * 2 ** (cents / 1200.0), float(res_[j]), float(res_[int(np.argmin(np.abs(grid)))])


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    force_shift = None
    if "--shift-ms" in args:
        i = args.index("--shift-ms")
        force_shift = float(args[i + 1]) / 1000.0
        del args[i:i + 2]
    debug_at = None
    if "--debug-at" in args:
        i = args.index("--debug-at")
        debug_at = float(args[i + 1])
        del args[i:i + 2]
    root = os.path.dirname(HERE)
    wav = args[0] if len(args) > 0 else os.path.join(root, "analysis", "start-tune-recorded.wav")
    trace = args[1] if len(args) > 1 else os.path.join(root, "analysis", "raw-logs", "tune-record.txt")
    out = []
    P = lambda *a: out.append(" ".join(str(x) for x in a))
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = parse_trace(trace)
    tune_writes = [f for (f, n, v) in events if n == "TUNE" and v == 0]
    if not tune_writes:
        print("no TUNE x=0 event in the trace")
        return 2
    f_tune = tune_writes[0]
    res = W.analyze(x, rate)
    problems = []
    if "error" in res or res["problems"]:
        problems.append("the start tune in the recording is not clean: %s" % (res.get("error") or res["problems"][:3]))
    # reference cycle: the first write of tune step 0 (frame f_tune); the recording time of the step start is res["t0"]
    c_tune = next(c for (c, r, v, pc) in sndw if c // FRAME_CYC == f_tune)
    segs = build_segments(sndw)
    c_end_trace = (last_frame - 12) * FRAME_CYC                          # the end of a trace may be missing
    # --- level calibration (single-voice tune steps)
    ss = W.Spec(x, rate)
    k_est = []
    for row in res["rows"]:
        if row["kind"] == "tone" and (row["f1"] > 0) != (row["f2"] > 0):
            _, rms = ss.mag(res["t0"], res["P"], row["i"])
            k_est.append((8 if row["f1"] > 0 else 4, rms / (8 if row["f1"] > 0 else 4)))
    k = float(np.median([e[1] for e in k_est]))
    def tone_rms(st):
        t, _ = expected_tones(st)
        return k * float(np.sqrt(sum(v ** 2 for (_, _, v) in t)))

    def first_toggle_delay(st):
        """Seconds from the register write to the first sample of sound: a pure tone first changes its output after AUDF + 1 ticks of the 64 kHz clock."""
        t, _ = expected_tones(st)
        return min((1.0 / (2.0 * fq) for (_, fq, _) in t), default=0.0)

    def onset_near(t_pred, st, half_window):
        """Time of the first sample that reaches half the expected amplitude of the loudest-first channel, searched in [t_pred - w, t_pred + w], or None."""
        t, _ = expected_tones(st)
        if not t:
            return None
        a_exp = 0.5 * k * max(v for (_, _, v) in t)
        i0, i1 = max(0, int((t_pred - half_window) * rate)), min(len(x), int((t_pred + half_window) * rate))
        hit = np.where(np.abs(x[i0:i1]) > a_exp)[0]
        return (i0 + int(hit[0])) / rate if len(hit) else None

    # --- anchor: the first sound of the start tune.  Its register writes happen at a known emulated time; the first sample of sound follows after the half period of the
    # highest-pitched channel, so  t_write = t_onset - delay.  The tune fit (t0) only tells where to look.
    t0 = res["t0"]
    seg0 = next(s for s in segs if s["c0"] >= c_tune - 1 and expected_tones(s["st"])[0])
    t_on = onset_near(t0, seg0["st"], 0.030)
    if t_on is None:
        print("no first sound found near the start tune")
        return 2
    shift_on = t_on - first_toggle_delay(seg0["st"]) - (t0 + 0.0)
    shift = force_shift if force_shift is not None else shift_on
    t_anchor = t0 + shift
    T = lambda c: t_anchor + (c - c_tune) / CPU
    P("Recording %.2f s, %d Hz.  Trace: %d register writes, frames up to %d." % (len(x) / rate, rate, len(sndw), last_frame))
    P("Alignment: the first sound of the start tune appears at %.4f s; its writes (frame %d, %.2f ms into the frame) happened %.2f ms earlier, at %.4f s (the tune fit's step start is %.4f s: %+.2f ms)." % (
      t_on, f_tune, (c_tune - f_tune * FRAME_CYC) / CPU * 1000, first_toggle_delay(seg0["st"]) * 1000, T(c_tune), t0, shift * 1000))
    # --- clock check: every later silence -> sound transition must appear where the writes put it (otherwise the emulated clock drifts against the recording)
    c_last = min(c_end_trace, sndw[-1][0])
    marks = []
    for i_, s in enumerate(segs[1:], 1):
        prev = segs[i_ - 1]
        if s["c0"] <= c_tune + 2 * CPU or s["c0"] > c_last or not expected_tones(s["st"])[0] or expected_tones(prev["st"])[0]:
            continue
        if (s["first"] - prev["first"]) / CPU < 0.2 and prev["first"] > -1e17:
            continue
        pred = T(s["c0"]) + first_toggle_delay(s["st"])
        got = onset_near(pred, s["st"], 0.030)
        if got is not None and pred + 0.030 < len(x) / rate:
            marks.append((pred, got - pred))
    if marks:
        dd = np.array([m[1] for m in marks]) * 1000
        P("Clock check: %d later silence-to-sound transitions (first at %.1f s, last at %.1f s): the sound appears %+.2f ms (mean) from where the writes put it, spread %.2f ms (min %+.2f, max %+.2f)." % (
          len(marks), marks[0][0], marks[-1][0], dd.mean(), dd.max() - dd.min(), dd.min(), dd.max()))
        if dd.max() - dd.min() > 3.0 or abs(dd.mean()) > 2.0:
            problems.append("clock check: onsets deviate from the register writes by up to %.2f ms" % max(abs(dd.min()), abs(dd.max())))
    else:
        P("Clock check: no later silence-to-sound transition in the trace.")
    ev = collections.OrderedDict()
    for (f, n, v) in events:
        if n != "TUNE" and n not in ev:
            ev[n] = f
    cyc_of_frame = lambda f: f * FRAME_CYC
    P("Game events (first occurrence): " + ", ".join("%s f=%d (%.2f s)" % (n, f, T(cyc_of_frame(f))) for n, f in ev.items()) + ";  DEATH_START frames: %s" % [f for (f, n, v) in events if n == "DEATH_START"])
    P("Level calibration from %d single-voice tune steps: RMS = %.5f x volume (volume 8: %.5f per unit, volume 4: %.5f per unit)." % (len(k_est), k,
      float(np.median([e[1] for e in k_est if e[0] == 8])), float(np.median([e[1] for e in k_est if e[0] == 4]))))
    rows, short, short_t = [], 0, 0.0
    kinds = collections.defaultdict(lambda: dict(n=0, dur=0.0, worst_cents=0.0, lv=[], writers=set(), pj=0))
    covered = [0.0, 0.0]
    for si, s in enumerate(segs):
        if s["c0"] < -1e17 and s["c1"] is not None and T(s["c1"]) < 0:
            continue
        prev_tones = (expected_tones(segs[si - 1]["st"], True)[0] + expected_tones(segs[si - 1]["st"], True)[2]) if si else []
        tones, prob, hp = expected_tones(s["st"], True)
        ta = T(s["c0"])
        tb = T(min(s["c1"], c_end_trace)) - END_MARGIN_S
        if s["c0"] > c_end_trace:
            continue
        lowest = min([fq for (_, fq, _) in tones + hp], default=0)
        # a channel finishes the half-cycle it is in before the new period applies: up to one half period of the old sound, then up to one of the new one
        ta += max([0.5 / fq for (_, fq, _) in prev_tones] + [0.0]) + (0.5 / lowest if lowest else 0.0) + 0.0005
        # Altirra's output is AC-coupled: after a drop in level the signal decays exponentially (measured: 0.037, 0.013, 0.009, 0.006, 0.004, 0.003 in successive ms after a
        # 0.07 tone stops, tau about 2.5 ms).  Skip the time the tail needs to fall below 10 % of this segment's own level (or below the silence limit).
        own_e, prev_e = tone_rms(s["st"]), (tone_rms(segs[si - 1]["st"]) if si else 0.0)
        drop, target = prev_e - own_e, (0.1 * own_e if own_e > 0 else SILENT_RMS)
        if drop > target:
            ta += TAU * float(np.log(drop / target))
        if ta < 0 or tb > len(x) / rate:
            ta, tb = max(ta, 0.0), min(tb, len(x) / rate)
        key = tuple((c, s["st"][(c - 1) * 2 + 1]) for (c, fq, vol) in tones) + tuple((1, 256 + s["st"][1]) for _ in hp) or ("silence",)
        if prob:
            problems.append("segment at %.2f s: %s" % (ta, "; ".join(prob)))
        d = tb - ta
        if debug_at is not None and abs(ta - debug_at) < 0.003:
            for sj in range(max(0, si - 2), min(len(segs), si + 3)):
                q = segs[sj]
                print("DEBUG seg %d%s: %.4f..%.4f s (%.2f ms) regs AUDF/AUDC %s AUDCTL %d  writers %s" % (sj, " <==" if sj == si else "", T(q["c0"]), T(min(q["c1"], c_end_trace)), (q["c1"] - q["c0"]) / CPU * 1000 if q["c1"] < 1e17 else 0,
                      [(q["st"][2 * c], q["st"][2 * c + 1]) for c in range(4)], q["st"][8], {r_: sorted("%04X" % p_ for p_ in v_) for r_, v_ in q["wr"].items()}))
            t_a = T(segs[max(0, si - 1)]["c0"])
            sl = x[int(t_a * rate):int((tb + 0.004) * rate)]
            print("DEBUG recorded rms in 1 ms slices from %.4f s (window used: %.4f..%.4f): %s" % (t_a, ta, tb, [round(float(np.sqrt(np.mean(c ** 2))), 4) for c in np.array_split(sl, max(1, int(len(sl) / rate * 1000)))]))
        if d < MIN_LEVEL_S:
            short += 1
            short_t += max(0.0, T(min(s["c1"], c_end_trace)) - T(s["c0"]))
            continue
        seg_x = x[int(ta * rate):int(tb * rate)]
        rms = float(np.sqrt(np.mean(seg_x ** 2)))
        exp_rms = tone_rms(s["st"])
        row = dict(ta=ta, d=d, st=s["st"], tones=tones + hp, rms=rms, exp=exp_rms, wr=s["wr"], pitch=[], key=key, hp=bool(hp))
        bad = []
        if not tones and not hp:
            # "Sound" is the oscillating part of the output: the emulator's AC coupling leaves a slow offset / overshoot after a loud sound with a large DC part (measured here: 0.13
            # falling to 0.003 and rising again to 0.01 over 15 ms with no tone in it), so the mean and the linear trend of the window are removed before the level is judged.
            # The band-limited resampler of the emulator lets a following sound start up to about a millisecond before its register time (seen: one sample of -0.084 in the last
            # millisecond of a silent window), so 1 ms is trimmed at both ends of a silent window.
            trim = int(0.001 * rate)
            sx = seg_x[trim:len(seg_x) - trim] if len(seg_x) > 2 * trim + 8 else seg_x
            tt = np.arange(len(sx))
            ac = sx - np.polyval(np.polyfit(tt, sx, 1), tt) if len(sx) > 4 else sx
            # the lowest tone of this game is 131 Hz, so only the energy at 150 Hz and above counts as sound; the slow, non-linear overshoot of the AC coupling lies below that
            spc = np.abs(np.fft.rfft(ac * np.hanning(len(ac)), 4096)) ** 2
            frq = np.fft.rfftfreq(4096, 1.0 / rate)
            share = float(spc[frq >= 150.0].sum() / max(spc.sum(), 1e-30))
            rms_ac = float(np.sqrt(np.mean(ac ** 2))) * float(np.sqrt(share))
            row["rms_ac"] = rms_ac
            if rms_ac > SILENT_RMS:
                bad.append("silent by the registers but the recording has sound (150 Hz and above) of level %.4f (raw %.4f)" % (rms_ac, rms))
        else:
            allt = tones + hp
            # Tones whose pitch is within 5 % of each other form a GROUP.  Equal-pitch square waves add coherently, so the level of a group depends on their phase: between
            # max(0, 2 x largest - sum) and the sum of the (certain) amplitudes; a high-pass filtered channel 1 adds an unknown part between 0 and its volume.  Groups of different
            # pitch add as powers.  A segment with such a group (or a high-pass channel) is checked against these bounds, any other segment against the exact expected level.
            groups = []
            for t in sorted(allt, key=lambda q: q[1]):
                if groups and abs(np.log2(t[1] / groups[-1][-1][1])) < 0.07:
                    groups[-1].append(t)
                else:
                    groups.append([t])
            lo2 = hi2 = 0.0
            for g in groups:
                cert = [t_[2] for t_ in g if t_ not in hp]
                lo2 += (max(0.0, 2 * max(cert) - sum(cert)) if cert else 0.0) ** 2
                hi2 += sum(t_[2] for t_ in g) ** 2
            lo_rms, hi_rms = k * float(np.sqrt(lo2)), k * float(np.sqrt(hi2))
            bounded = bool(hp) or any(len(g) > 1 for g in groups)
            row["lo"], row["hi"], row["bounded"] = lo_rms, hi_rms, bounded
            if bounded:
                if rms < lo_rms * (1 - LEVEL_TOL) or rms > hi_rms * (1 + LEVEL_TOL):
                    bad.append("level %.4f outside the bounds %.4f .. %.4f (equal-pitch tones / high-pass channel: phase-dependent)" % (rms, lo_rms, hi_rms))
            elif exp_rms > 0 and abs(rms / exp_rms - 1) > LEVEL_TOL:
                bad.append("level %.4f against %.4f expected (%+.0f %%)" % (rms, exp_rms, (rms / exp_rms - 1) * 100))
            if d >= MIN_PITCH_S:
                row['short'] = d < LONG_S
                nf = 1 << int(np.ceil(np.log2(max(8192, len(seg_x) * 4))))
                m = np.abs(np.fft.rfft(seg_x * np.hanning(len(seg_x)), nf))
                sp = W.Spec.__new__(W.Spec)
                sp.rate, sp.freqs = rate, np.fft.rfftfreq(nf, 1.0 / rate)
                sp.band = (sp.freqs >= 80) & (sp.freqs <= 3000)
                old, W.NFFT = W.NFFT, nf
                tol = CENTS_TOL if d >= LONG_S else SHORT_CENTS_TOL
                gfreq = [sum(t_[1] * t_[2] for t_ in g) / sum(t_[2] for t_ in g) for g in groups]
                # a channel that starts from silence inside a short window brings an onset transient that is not modelled: the OTHER tones' pitch is then not resolved in that window
                prev_chs = {t_[0] for t_ in prev_tones}
                onset_chs = {t_[0] for t_ in allt} - prev_chs
                for gi_, g in enumerate(groups):
                    c, fq = g[0][0], gfreq[gi_]
                    coherent = len(g) > 1 or any(t_ in hp for t_ in g)
                    if fq * d < MIN_CYCLES:
                        continue
                    others = [gfreq[j_] for j_ in range(len(groups)) if j_ != gi_]
                    if d < LONG_S and len(groups) > 1 and onset_chs and not ({t_[0] for t_ in g} & onset_chs) and prev_tones:
                        row.setdefault("unresolved", []).append((c, fq, None, -1.0))      # onset of another channel in the window
                        continue
                    if d < LONG_S and (len(groups) > 1 or fq * d < SPECTRUM_CYCLES):
                        # several voices inside one short window: fit the other voices out (their pitch is known exactly) and measure this one
                        fp, resid, resid0 = ls_pitch(seg_x, rate, others, fq)
                        h = 1.0 / max(resid, 1e-9)                        # signal-to-residual ratio of the fit
                        ratio = resid0 / max(resid, 1e-12)
                        if abs(1200 * np.log2(fp / fq)) > tol and ratio <= UNRESOLVED_RATIO:
                            # the fit at the expected pitch is as good as the best fit: the window cannot tell (the weak voice is not above the model error of the loud one)
                            row.setdefault("unresolved", []).append((c, fq, fp, ratio))
                            continue
                    else:
                        fp, h = W.peak_near(sp, m, fq)
                    cents = 1200 * np.log2(fp / fq) if fp else None
                    need = 1.2 if coherent else 4.0                      # equal-pitch tones may largely cancel, so their peak can be weak; the pitch must still be right
                    if coherent and fp is not None and (h < need or (h < 4.0 and abs(cents) > tol)):
                        row.setdefault("unresolved", []).append((c, fq, fp, 0.0))      # weak peak of a coherent group: a pitch estimate from it is not reliable
                        continue
                    row["pitch"].append((c, fq, fp, cents, h))
                    if fp is None or h < need or abs(cents) > tol:
                        bad.append("channel %d expected %.1f Hz, measured %s" % (c, fq, "%.1f Hz (%+.0f cents, peak %.1fx)" % (fp, cents, h) if fp else "nothing"))
                W.NFFT = old
        row["ok"] = not bad
        for bmsg in bad:
            problems.append("segment at %.3f s (%.0f ms): %s" % (ta, d * 1000, bmsg))
        rows.append(row)
        kd = kinds[key]
        kd["n"] += 1
        kd["dur"] += d
        kd["pj"] += 1 if row["pitch"] else 0
        kd["worst_cents"] = max([kd["worst_cents"]] + [abs(p[3]) for p in row["pitch"] if p[3] is not None])
        if exp_rms > 0:
            kd["lv"].append(rms / exp_rms)
        for r_, s_ in s["wr"].items():
            kd["writers"] |= set(s_)
    P("\nSegments of constant register state: %d judged (%d with a pitch measurement), %d shorter than %.0f ms (not judged); ok: %d" % (len(rows), sum(1 for r in rows if r["pitch"]), short, MIN_LEVEL_S * 1000, sum(1 for r in rows if r["ok"])))
    t_first, t_end = max(0.0, T(sndw[0][0])), min(T(c_end_trace), len(x) / rate)
    judged_t = sum(r["d"] for r in rows)
    P("Accounting of the %.2f s recording: before the first register write %.2f s (nothing writes sound there, the recording is silent: level %.4f); after the end of the usable trace %.2f s (not compared); "
      "inside the trace %.2f s = judged %.2f s + segments shorter than %.0f ms %.2f s + settle/half-period margins %.2f s." % (
      len(x) / rate, t_first, float(np.sqrt(np.mean(x[:int(t_first * rate)] ** 2))) if t_first > 0 else 0.0, len(x) / rate - t_end, t_end - t_first, judged_t, MIN_LEVEL_S * 1000, short_t, (t_end - t_first) - judged_t - short_t))
    P("\nBy kind of sound:  segments (with pitch), time, worst pitch error, level recording/expected (min..max), PCs that write the AUDF/AUDC registers of it")
    for key, kd in sorted(kinds.items(), key=lambda t: -t[1]["dur"]):
        name = "silence" if key == ("silence",) else " + ".join("ch%d $%02X%s" % (c, v & 255, " HP" if v > 255 else "") for (c, v) in key)
        P("  %-22s %4d segs (%3d) %7.2f s  worst %5.1f cents  level %s  PCs %s" % (name, kd["n"], kd["pj"], kd["dur"], kd["worst_cents"],
          ("%.2f..%.2f" % (min(kd["lv"]), max(kd["lv"]))) if kd["lv"] else "-", " ".join("$%04X" % p for p in sorted(kd["writers"])) or "-"))
    unres = [(r["ta"], u) for r in rows for u in r.get("unresolved", [])]
    long_p = [abs(p_[3]) for r in rows if r["pitch"] and not r.get("short") for p_ in r["pitch"] if p_[3] is not None]
    short_p = [abs(p_[3]) for r in rows if r["pitch"] and r.get("short") for p_ in r["pitch"] if p_[3] is not None]
    if long_p:
        P("Pitch error, segments of 40 ms or more: %d tones, mean %.2f cents, 95%% within %.1f, worst %.1f (limit %.0f)." % (len(long_p), np.mean(long_p), np.percentile(long_p, 95), max(long_p), CENTS_TOL))
    if short_p:
        P("Pitch error, segments of 12-40 ms (siren, death glide, sweeps): %d tones, mean %.2f cents, 95%% within %.1f, worst %.1f (limit %.0f)." % (len(short_p), np.mean(short_p), np.percentile(short_p, 95), max(short_p), SHORT_CENTS_TOL))
    P("Pitch not resolved (weak voice under a louder one in a 12-13 ms window: the fit at the expected pitch is within %.0f %% of the best fit, level still checked): %d tones%s" % (
        (UNRESOLVED_RATIO - 1) * 100, len(unres), "".join("\n    %.3f s  channel %d expected %.1f Hz, %s" % (t_, u[0], u[1], ("best fit %.1f Hz, residual ratio %.2f" % (u[2], u[3])) if u[2] is not None else "another channel starts in the window (onset transient)") for (t_, u) in unres)))
    P("\nSegment list (start, length, what the registers say, pitch error in cents, level recording/expected):")
    last_sil = None
    for r in rows:
        tones = "  ".join("ch%d %.0f Hz v%d (%s)" % (c, fq, vol, ("%+.0f" % p[3]) if (p := next((q for q in r["pitch"] if q[0] == c), None)) and p[3] is not None else "-") for (c, fq, vol) in r["tones"]) or "silence"
        P("  %8.3f s %6.0f ms  %-52s level %s  %s" % (r["ta"], r["d"] * 1000, tones, ("%.2f" % (r["rms"] / r["exp"])) if r["exp"] else "%.4f" % r["rms"], "ok" if r["ok"] else "FAIL"))
    # ---- edge timing of the bonus-item sweep (single channel 1, 177-264 Hz): predicted toggle times against the zero crossings of the band-passed recording
    ab = sorted({c // FRAME_CYC for (c, r, v, pc) in sndw if pc == 0xABFE})
    eps_, st_ = [], None
    for fr_ in ab:
        if st_ is None:
            st_ = [fr_, fr_]
        elif fr_ == st_[1] + 1:
            st_[1] = fr_
        else:
            eps_.append(st_)
            st_ = [fr_, fr_]
    if st_:
        eps_.append(st_)
    edge_rows, edge_skipped = [], []
    for (fa_, fb_) in eps_:
        cw = next(c for (c, r, v, pc) in sndw if pc == 0xABFE and c // FRAME_CYC == fa_)
        c_last = max(c for (c, r, v, pc) in sndw if pc == 0xAC01 and c // FRAME_CYC == fb_)
        me = model_edges(sndw, 0, cw, c_last)
        if len(me) < 6 or T(c_last) + 0.1 > len(x) / rate:
            continue
        mt = np.array([T(c) for c in me])
        # the method needs channel 1 to be the only tone in the 120-400 Hz band: another channel with sound in that band (e.g. the frightened-phase tone on channel 2) is skipped
        def other_in_band(c_lo, c_hi):
            st = [0] * 9
            seen = False
            for (c, r, v, pc) in sndw:
                if c > c_hi:
                    break
                st[r] = v
                if c >= c_lo - 1:
                    for ch in (1, 2, 3):
                        vv_, ff_ = st[ch * 2 + 1], st[ch * 2]
                        if (vv_ & 15) and (vv_ >> 5) == 5 and ff_ and 100.0 <= BASE / (2.0 * (ff_ + 1)) <= 450.0:
                            seen = True
            return seen
        if other_in_band(cw, c_last):
            edge_skipped.append(fa_)
            continue
        rc = crossings(x, rate, mt[0] - 0.004, mt[-1] + 0.004, 120.0, 400.0)
        best_ = None
        for sh in np.arange(-0.008, 0.0081, 0.00005):
            d_ = np.array([np.min(np.abs(rc - (m_ + sh))) for m_ in mt[2:-2]]) if len(rc) else np.array([9.0])
            cost = float(np.median(d_))
            if best_ is None or cost < best_[0]:
                best_ = (cost, sh, d_)
        cost, sh, d_ = best_
        edge_rows.append((fa_, len(mt), len(rc), sh, cost, float(np.mean(d_ < 0.0005)), float(np.max(d_))))
    if edge_skipped:
        P("\nEdge timing not applicable (another channel sounds in the 120-400 Hz band during the sweep): bonus sweeps at frames %s." % edge_skipped)
    if edge_rows:
        P("\nEdge timing of the bonus-item sweep (channel 1, one call per frame; predicted toggle times from the AUDF history against the zero crossings of the recording, 120-400 Hz band):")
        for (fa_, nm_, nr_, sh_, cost_, frac_, mx_) in edge_rows:
            P("  frame %d: %d predicted edges, %d recorded crossings, best constant shift %+.2f ms, median residual %.3f ms, %.0f %% within 0.5 ms, worst %.2f ms" % (fa_, nm_, nr_, sh_ * 1000, cost_ * 1000, frac_ * 100, mx_ * 1000))
            if cost_ > 0.0002 or frac_ < 0.98 or mx_ > 0.002:
                problems.append("bonus sweep at frame %d: edge timing differs (median %.3f ms, %.0f %% within 0.5 ms, worst %.2f ms)" % (fa_, cost_ * 1000, frac_ * 100, mx_ * 1000))
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
