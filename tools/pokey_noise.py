"""The start state of a channel's output flip-flop when it enters a pure-tone sound, derived from Altirra's POKEY renderer (docs/22-sound.md, OPEN-VERIFICATION.md OV-13a).

What Altirra does (src/ATAudio/source/pokeyrenderer.cpp, FireTimer<>): each channel keeps a "noise flip-flop".  At every timer fire (the 28-cycle grid of pokey_timers.py):
  * a pure-tone mode (AUDC bits 7-5 = 101, or 001/011/111 gated by poly5) toggles it;
  * a noise mode (AUDC = $00 is what the OS leaves in idle channels) first applies the 5-bit gate (a fire is skipped when the poly5 bit is 0) and then sets it to the
    current poly17 bit (poly9 when AUDCTL bit 7 is set).
The audible output of a channel that has a volume is that flip-flop.  When a sound switches a channel from idle noise to pure tone, the flip-flop therefore starts at the poly bit of
the LAST gated fire before the switch - a function of the cycle time of that fire only, through the free-running polynomial counters:

    index into the 17-bit sequence = (131070 - ch + fire - T0) mod 131071      (9-bit: 510 ...  mod 511;  5-bit gate: (29 - ch + fire - T0) mod 31)

with ch = 0..3 for channels 1..4 and T0 = the cycle at which the OS writes SKCTL ($D20F) := 3 (leaves initialisation mode, where the counters run from): frame 22, vpos 191, hpos 103
of the trace = 22*29868 + 191*114 + 103 = 678973 (seen in every trace that logs $D20F).
"""
import numpy as np

import pokey_timers as PT  # noqa: F401  (kept for the type of `timers`)

import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video as V  # noqa: E402
FRAME_CYC = V.FRAME_CYC
T0 = 22 * FRAME_CYC + 191 * 114 + 103         # NTSC; a PAL run sets PN.T0 from its trace (video.skctl_t0)
M17, M9, M5 = 131071, 511, 31


def _gen17():
    p, out = 0, np.zeros(M17, np.int8)
    for i in range(M17):
        p = (p >> 1) + (~((p << 16) ^ (p << 11)) & 0x10000)
        out[i] = (p >> 8) & 1
    return out


def _gen9():
    p, out = 0, np.zeros(M9, np.int8)
    for i in range(M9):
        p = (p >> 1) + (~((p << 8) ^ (p << 3)) & 0x100)
        out[i] = p & 1
    return out


def _gen5():
    p, out = 0, np.zeros(M5, np.int8)
    for i in range(M5):
        p = (p >> 1) + (~((p << 2) ^ (p << 4)) & 16)
        out[i] = p & 1
    return out


S17, S9, S5 = _gen17(), _gen9(), _gen5()


def audcn(a):
    """the mode of AUDC as Altirra's table selects it (pokeyrenderer.cpp kFireRoutines): 0x20 = tone gated by poly5, 0xA0 = pure tone, 0x00/0x80 = poly9/17 noise (poly5-gated / not), 0x40/0xC0 = poly4"""
    return {0: 0x00, 1: 0x20, 2: 0x40, 3: 0x20, 4: 0x80, 5: 0xA0, 6: 0xC0, 7: 0xA0}[a >> 5]


def poly5_pass(f, ch0, t0=None):
    t0 = T0 if t0 is None else t0
    return bool(S5[(29 - ch0 + f - t0) % M5])


def source_bit(kind, f, ch0, t0=None):
    t0 = T0 if t0 is None else t0
    if kind == "p17":
        return int(S17[(M17 - 1 - ch0 + f - t0) % M17])
    return int(S9[(M9 - 1 - ch0 + f - t0) % M9])


AUDIO_DELAY = 2            # kAudioDelay of pokeyrenderer.cpp: a fire is processed in the mode of the register state 2 cycles AFTER it
# OV-13c / OV-14: a fire on the very cycle of an AUDF write of its channel gives the output flip-flop NO edge (it neither toggles nor samples noise).  Evidence: it removes the last start-bit miss of the
# 110 ghost-eaten-sweep bits (109 -> 110 of 110) and it explains the polarity flips in the middle of long channel-2 runs, which sit exactly at the two coincident writes of the run (frames 2562 and 3398).
COINCIDENT_FIRE_IS_EDGE = False


def edges(tim, a, b):
    """the fires of timer `tim` in [a, b) that reach the output flip-flop"""
    return tim.fires(a, b) if COINCIDENT_FIRE_IS_EDGE else tim.edges(a, b)


def ecount(tim, t):
    """number of edges <= t"""
    return tim.count(t) if COINCIDENT_FIRE_IS_EDGE else tim.edge_count(t)


def noise_state_before(model, k, w, t0=None, delay=AUDIO_DELAY):
    t0 = T0 if t0 is None else t0
    """-> (value, kind) : the noise flip-flop of channel k (1..4) just before cycle w, walking back over the AUDC/AUDCTL history of the register writes in `model` (analyze_ghost_sweep.Model).
    kind is 'p17', 'p9' or 'poly4' (not modelled: value None).  The fires of the last `delay` cycles before w run in the mode written at w (a tone toggles them)."""
    v, kind = _noise_state_before(model, k, w, t0, delay)
    if v is None or delay == 0:
        return v, kind
    cn = audcn(model.audc[k].at(w))
    if cn & 0x20:
        gated = not (cn & 0x80)
        tail = [f for f in edges(model.timers[k], w - delay, w) if (not gated) or poly5_pass(f, k - 1, t0)]
        v ^= len(tail) & 1
    return v, kind


def _noise_state_before(model, k, w, t0, delay):
    ch0 = k - 1
    tim = model.timers[k]
    bs = sorted(set(c for (c, r, v, pc) in model.sndw if r == 2 * (k - 1) + 1 or r == 8))
    bounds = [-10 ** 18] + [b - delay for b in bs if b < w] + [w - delay]
    acc = 0
    for i in range(len(bounds) - 2, -1, -1):
        lo, hi = bounds[i], bounds[i + 1]
        probe = (hi - 1 if hi - 1 > lo else lo) + delay
        a = model.audc[k].at(probe)
        ctl = model.ctl.at(probe)
        cn = audcn(a)
        gated = not (cn & 0x80)
        if cn & 0x20:                                              # tone: toggles at every (gated) fire
            if not gated:
                n = (ecount(tim, hi - 1) or 0) - (ecount(tim, lo - 1) if lo > -10 ** 17 else 0)
                acc ^= (n & 1)
            else:
                acc ^= (sum(1 for f in edges(tim, lo, hi) if poly5_pass(f, ch0, t0)) & 1)
            continue
        if cn & 0x40:
            return None, "poly4"
        kind = "p9" if (ctl & 0x80) else "p17"
        K = 4000
        while True:                                                # the last (gated) fire of the noise stretch
            a0 = max(lo, hi - K)
            for f in reversed(edges(tim, a0, hi)):
                if (not gated) or poly5_pass(f, ch0, t0):
                    return source_bit(kind, f, ch0, t0) ^ acc, kind
            if a0 <= lo:
                break
            K *= 4
    return None, None


def tone_entry(model, k, c_a, c_b):
    """the cycle at which channel k becomes an audible pure tone in the window [c_a, c_b]: c_a if it already is, else its first AUDC write that makes one"""
    a = model.audc[k].at(c_a)
    if (a >> 5) == 5 and (a & 15):
        return c_a
    for (c, r, v, pc) in model.sndw:
        if c_a <= c <= c_b and r == 2 * (k - 1) + 1 and (v >> 5) == 5 and (v & 15):
            return c
    return None


def start_constant(model, k, c_a, c_b, t0=None, polarity=1):
    t0 = T0 if t0 is None else t0
    """-> the constant c_k of analyze_ghost_sweep.Model.mixed (output of channel k = c_k XOR parity of all fires counted since reset) predicted for the sweep window [c_a, c_b]; None if not derivable.
    `polarity` = the one fitted constant (1): the audible level is the flip-flop inverted."""
    w = tone_entry(model, k, c_a, c_b)
    if w is None:
        return None
    v, kind = noise_state_before(model, k, w, t0)
    if v is None:
        return None
    return v ^ ((ecount(model.timers[k], w - 1) or 0) & 1) ^ polarity
