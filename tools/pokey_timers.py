"""POKEY channel timers from the register writes alone (docs/22-sound.md, OPEN-VERIFICATION.md OV-13).

Rules, read from the debugger's `.pokey` output (cycles until fire, period) and validated against thousands of dumps (tools/analyze_ghost_sweep.py --validate-timers):
  - all underflows ("fires") of all channels lie on one global grid of 28 CPU cycles (the 64 kHz divider);
  - a channel fires, toggles its output and reloads with the AUDF value it has AT THAT MOMENT: the next fire is (AUDF + 1) x 28 cycles later;
  - an AUDF write does not touch the pending fire: it only changes the reload at that fire;
  - before the first write all AUDF are 0 (period 28).
`Timer(writes, phase)` answers `pending(t)` = the first fire strictly after cycle t, and `fires(a, b)` = the fires in [a, b), without iterating over the long stretches of AUDF = 0.
"""
import bisect

TICK = 28
COINC_WINDOW = (0, 0)       # offsets (fire - write) in cycles of the fires that give no edge; (0, 0) = exactly on the write cycle


class Timer:
    def __init__(self, writes, phase, ctl_changes=()):
        """writes: sorted list of (cycle, AUDF value); phase: residue of the fire grid (fire cycles = phase mod 28)."""
        self.phase = phase % TICK
        self.ctl_changes = sorted(ctl_changes)      # cycles of the writes that CHANGE AUDCTL: the same mechanism as an AUDF change (pokey.cpp: UpdateTimerCounter + FlushDeferredTimerEvents of all four timers), OV-42c
        self.w_t = [c for c, _ in writes]
        self.w_v = [v for _, v in writes]
        self.f_at = []          # pending fire at the instant of each write (after the fires <= write cycle)
        self.n_at = []          # number of fires since the first grid point before the first write (reset) up to each write
        F = self._first_tick(-(10 ** 12))
        self.f0 = F
        cur = 0
        n = 0
        t0 = F
        coinc = []
        for (c, v) in writes:
            if v != cur and F <= c and (c - F) % ((cur + 1) * TICK) == 0 and (not coinc or coinc[-1] != c):
                coinc.append(c)                    # a fire on the very cycle of a write that CHANGES AUDF (pokey.cpp: `if (mAUDF[n] != value)`: a rewrite of the same value does nothing)
            F2 = self._advance(F, cur, c)          # pending fire after processing all fires <= c with the old reload value `cur`
            n += (F2 - F) // ((cur + 1) * TICK)
            F = F2
            self.f_at.append(F)
            self.n_at.append(n)
            cur = v
        self.coinc = coinc                  # cycles at which a fire and a write of this channel's AUDF coincide
        self._coinc_set = set(coinc)

    def _first_tick(self, t):
        """first grid point strictly after t"""
        return ((t - self.phase) // TICK + 1) * TICK + self.phase

    def _advance(self, F, cur, t):
        if F > t:
            return F
        P = (cur + 1) * TICK
        m = (t - F) // P + 1                       # fires F, F+P, ..., F+(m-1)P are <= t
        return F + m * P

    def _state_at(self, t):
        """(pending fire, reload value in force) at cycle t, just after all fires and writes <= t"""
        j = bisect.bisect_right(self.w_t, t) - 1
        if j < 0:
            return self._first_tick(t), 0
        cur = self.w_v[j]
        F = self.f_at[j]
        return self._advance(F, cur, t), cur

    def count(self, t):
        """number of fires <= t, counted from a fixed origin before the first write (before the first write the channel fires on every grid point, AUDF = 0)"""
        j = bisect.bisect_right(self.w_t, t) - 1
        if j < 0:
            return (t - self.f0) // TICK + 1 if t >= self.f0 else 0
        cur = self.w_v[j]
        F = self.f_at[j]
        n = self.n_at[j]
        if F <= t:
            P = (cur + 1) * TICK
            n += (t - F) // P + 1
        return n

    def pending(self, t):
        F, cur = self._state_at(t)
        return F

    def fires(self, a, b):
        """list of fire cycles in [a, b) (explicit; use only for stretches with AUDF > 0 or short ranges)"""
        out = []
        F, cur = self._state_at(a - 1)
        while F < b:
            j = bisect.bisect_left(self.w_t, F) - 1            # a write on the very cycle of a fire comes after the fire (as in count()/pending(), validated against the dumps): the fire reloads with the OLD value
            cur_at = self.w_v[j] if j >= 0 else 0
            out.append(F)
            F += (cur_at + 1) * TICK
        return out

    # ---- edges: the fires that reach the audio output.  Altirra's renderer gets NO edge from a fire that falls on the very cycle of an AUDF write of its channel (found with the whole-game waveform
    # comparison, OPEN-VERIFICATION.md OV-13c / OV-14: every such coincidence flips the polarity of the rest of a tone).  The timer itself keeps its schedule (the debugger dumps agree), only the output
    # flip-flop is not driven.
    def _dropped_fires(self):
        """sorted fires that give no edge: those within COINC_WINDOW = (lo, hi) cycles of a write that changes AUDF (default (0, 0): exactly on the write cycle)"""
        key = COINC_WINDOW
        if getattr(self, "_dkey", None) != key:
            lo, hi = key
            d = set()
            for c in self.ctl_changes:
                d.update(self.fires(c, c + 1))
            prev = 0
            for c, v in zip(self.w_t, self.w_v):
                if v != prev:
                    d.update(self.fires(c + lo, c + hi + 1))
                prev = v
            self._dropped, self._dset, self._dkey = sorted(d), d, key
        return self._dropped

    def edges(self, a, b):
        fs = self.fires(a, b)
        self._dropped_fires()
        return [f for f in fs if f not in self._dset] if self._dset else fs

    def edge_count(self, t):
        """number of edges <= t (count() minus the dropped fires <= t)"""
        n = self.count(t)
        return n - bisect.bisect_right(self._dropped_fires(), t) if n is not None else n
