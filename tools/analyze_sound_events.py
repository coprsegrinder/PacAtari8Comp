"""Register-level audit of the game's sounds against the CODE (docs/22-sound.md, OPEN-VERIFICATION.md OV-10).  Usage:
  python -I tools/analyze_sound_events.py <trace.txt> [--summary-file out.txt]      (trace from tools/altirra_sound_events.cmd; exit code 1 if a check fails)

Each routine of the ROM that makes a sound is ported to Python from its disassembly (src/asm/pacman.s) and run against what the game really wrote:
  bonus item eaten   Sub_ABC9 ($ABC9): AUDF1/AUDC1, one call per frame, 31 frames
  ghost eaten        $A8EC and $B049-$B088: AUDF1/3/4, AUDC1/3/4, AUDCTL = $84, until ClearPokeyRegisters
  frightened phase   Sub_AFD7 ($AFD7): AUDF2/AUDC2, one call per frame while FrightenPhase <> 0 and no eaten ghost is returning
  eyes returning     Sub_B02C ($B02C): AUDF2/AUDC2 = $A4, one call per frame while an eaten ghost is returning (zp_F2 <> 0) and no ghost-eaten sound runs
Checked frame by frame: every register write of every episode equals the port's prediction (value and register), and the writes happen only from the PCs the port expects.
Also reported: who owns channel 2 in each situation, and which PCs write any sound register around the extra life and the board change (no routine exists for them).
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as DS  # noqa: E402
import video as V  # noqa: E402


def parse(path):
    W, FR, EV = [], {}, []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = re.match(r"SNDW a=\$(D20[0-9A-F]) v=\$([0-9A-F]{2}) pc=\$([0-9A-F]{4}) f=(\d+) vp=(\d+) hp=(\d+)$", line)
            if m:
                f_, t_ = int(m.group(4)), int(m.group(5)) * 114 + int(m.group(6))
                # The game routine starts at the vertical blank (vpos about 248, where the FR line is logged) and its writes come at vpos 250-262 of that frame or, when it runs long,
                # at the start of the next one: a write belongs to the routine of frame rf = f when vpos >= 240, else f - 1.
                W.append(dict(f=f_, rf=f_ if t_ >= 240 * 114 else f_ - 1, reg=int(m.group(1), 16) - 0xD200, v=int(m.group(2), 16), pc=int(m.group(3), 16), t=t_))
                continue
            if line.startswith("FR ") and re.search(r" t1=\d+$", line):
                d = dict(re.findall(r"(\w+)=(\S+)", line))
                FR[int(d["f"])] = dict(fc=int(d["fc"]), fd=int(d["fd"]), f2=int(d["f2"]), e5=int(d["e5"]), f7=int(d["f7"]), f4=int(d["f4"]), lives=[int(x) for x in d["lives"].split(",")], lv=int(d["lv"]), p=int(d["p"]), cyc=int(d["cyc"]),
                               d34=int(d["d34"]) if "d34" in d else None, d36=int(d["d36"]) if "d36" in d else None, sl=int(d["sl"]) if "sl" in d else None)
                continue
            m = re.match(r"([A-Z_]+) f=(\d+)( x=(\d+))?$", line)
            if m and m.group(1) != "FR":
                EV.append((m.group(1), int(m.group(2)), int(m.group(4)) if m.group(4) else None))
    return [w for w in W if w["reg"] <= 8], FR, EV


# ------------------------------------------------------------------ ports of the ROM routines
def bonus_sequence():
    """Sub_ABC9 from F7 = 1, F8 = $78: list of (AUDF1, AUDC1) per call until the sound stops (the last call writes AUDF1 = 0, AUDC1 = 0)."""
    F7, F8, out = 1, 0x78, []
    while True:
        X = F7
        if X == 0:
            break
        A, Y = F8, 0xA5
        if X < 7:
            if A == 0xB4:                       # LABDE
                F7 += 1
                Y = 0xA3
            else:
                A = (A + 5) & 0xFF
        else:                                   # LABE4
            if X == 9:
                F7 += 1
            else:
                Y = 0xA3
            if A == 0x78:                       # LABEE
                A, F7, Y = 0, 0, 0
            else:
                A = (A - 5) & 0xFF
        F8 = A
        out.append((A, Y))
        if F7 == 0:
            break
    return out


def ghost_eaten_frames():
    """$A8EC then LB049/LB067 each frame: list of per-frame write dicts {reg: value}; the last frame is LB085 (ClearPokeyRegisters, AUDCTL := 0)."""
    E6, E7 = 2, 0x84
    frames = [{3: 0}]                           # A8EE: AUDC2 := 0 (in the frame of the collision, followed at once by the first sweep call? see check)
    first = True
    while True:
        w = {}
        E6 -= 1
        if E6 == 0:                             # LB067
            E6 = 2
            E7 = (E7 - 3) & 0xFF
            w = {0: E7, 4: E7, 6: E7, 5: 0xA8, 7: 0xA8, 1: 0xA8}
        else:
            E7 = (E7 - 4) & 0xFF
            if E7 == 0x10:                      # LB085
                w = {r: 0 for r in range(8)}
                w[8] = 0
                frames.append(w)
                return frames
            w = {0: E7, 6: E7, 8: 0x84, 7: 0xA4, 1: 0xA4}
        frames.append(w)
        if len(frames) > 400:
            raise RuntimeError("ghost-eaten port does not terminate")


def siren_step(d34, d36):
    """Sub_B5C7 ($B5D3-$B5FF): zp_9C, the siren step, from the dots eaten (zp_34; zp_36 is the high byte)."""
    if d36:
        return 5
    if d34 >= 0xF0:
        return 5
    if d34 >= 0xE0:
        return 4
    if d34 >= 0xB0:
        return 3
    return 2


class Siren:
    """LB508..LB54E (zp_DE, zp_DF, zp_E0): call(step) -> (AUDF2, AUDC2).  Also sets zp_E4 := 0 (re-initialises the frightened sound)."""

    def __init__(self):
        self.DE = self.DF = self.E0 = 0

    def call(self, step):
        if self.E0 == 0:
            self.DE, self.E0, self.DF = 0x28, 1, 1
        if self.DF == 1:
            if self.DE >= 0x40:
                self.DF = 2
                a = (self.DE - step) & 0xFF
            else:
                a = (step + self.DE) & 0xFF
        else:
            if self.DE >= 0x28:
                a = (self.DE - step) & 0xFF
            else:
                self.DF = 1
                a = (step + self.DE) & 0xFF
        self.DE = a
        return a, 0xA1


class Frightened:
    """Sub_AFD7 state (zp_E1..E4): call() -> (AUDF2, AUDC2)."""

    def __init__(self):
        self.E1 = self.E2 = self.E3 = self.E4 = 0

    def reset(self):
        self.E4 = 0

    def call(self):
        if self.E4 == 0:
            self.E3, self.E2, self.E4, self.E1 = 5, 2, 1, 0x90
        if self.E2 == 1:
            if self.E1 == 0x90:
                if self.E3 == 3:
                    self.E3 = 5
                self.E3 -= 1                      # LAFFF
                self.E2 = 2
                self.E1 = (self.E1 - 0x10) & 0xFF   # LB01A
            else:                                 # LB007
                s = (self.E1 + 0x10) & 0xFF
                if s == 0:
                    raise RuntimeError("fall-through into LB00E not expected")
                self.E1 = s
        else:                                     # LB00E
            if self.E1 == 0x40:
                self.E2 = 1
                s = (self.E1 + 0x10) & 0xFF       # LB007
                self.E1 = s
            else:
                self.E1 = (self.E1 - 0x10) & 0xFF   # LB01A
        return self.E1, (self.E3 | 0xA0)


class Eyes:
    """Sub_B02C with zp_F3; zp_F3 := 0 whenever zp_F2 = 0 (B6F5)."""

    def __init__(self):
        self.F3 = 0

    def reset(self):
        self.F3 = 0

    def call(self):
        if self.F3 == 0:
            self.F3 = 0x0C
        elif self.F3 == 0x17:
            self.F3 = 0x0C
        self.F3 += 1
        return self.F3, 0xA4


def main():
    args = sys.argv[1:]
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    lenient = "--lenient" in args          # a sound that did not occur in this run (e.g. no ghost could be eaten at a level) is information, not a failure
    if lenient:
        args.remove("--lenient")
    path = args[0]
    out, problems = [], []
    P = lambda *a: out.append(" ".join(str(x) for x in a))

    def check(ok, text):
        P(("  ok   " if ok else "  FAIL ") + text)
        if not ok:
            problems.append(text)

    W, FR, EV = parse(path)
    P("Trace: %d sound-register writes, %d frames (f=%d..%d), %d events." % (len(W), len(FR), min(FR), max(FR), len(EV)))
    last = max(FR) - 3
    byf = collections.defaultdict(list)
    for w in W:
        byf[w["rf"]].append(w)
    cnt = collections.Counter(e[0] for e in EV)
    P("Events:", dict(cnt))

    # ----------------------------------------------------------- start tune (every game start)
    P("\n" + "0. Start tune (the loop at $A7D3, PCs $A7E2 $A7E8 $A7ED $A7F2)")
    t1 = [DS.rd(0xBC50 + i) for i in range(64)]
    t2 = [DS.rd(0xBC90 + i) for i in range(64)]
    tune_steps = {}
    for f in sorted(byf):
        ws = byf[f]
        a1 = [w for w in ws if w["pc"] == 0xA7E2]
        a2 = [w for w in ws if w["pc"] == 0xA7E8]
        c1 = [w for w in ws if w["pc"] == 0xA7ED]
        c2 = [w for w in ws if w["pc"] == 0xA7F2]
        if a1 and a2 and c1 and c2:
            tune_steps[f] = (a1[0]["v"], a2[0]["v"], c1[0]["v"], c2[0]["v"])
    steps = sorted(tune_steps)
    games = [e for e in EV if e[0] == "NEWGAME"]
    check(len(steps) == 64 * len(games) or lenient, "%d tune steps for %d game start(s)" % (len(steps), len(games)))
    for gi in range(len(steps) // 64):
        blk = steps[gi * 64:(gi + 1) * 64]
        bad = [i for i, f in enumerate(blk) if tune_steps[f] != (t1[i], t2[i], 0xA8, 0xA4)]
        gaps = {blk[i + 1] - blk[i] for i in range(63)}
        lvl = FR[blk[0]].get("sl") if blk[0] in FR else None
        lv0 = FR[blk[0]]["lv"] if blk[0] in FR else None
        check(not bad and gaps == {4}, "game %d: 64 steps from f=%d, every (AUDF1, AUDF2, AUDC1, AUDC2) equals the ROM tables and AUDC $A8/$A4, one step every 4 frames (level counter %s, StartLevel %s)" % (gi + 1, blk[0], lv0, lvl))

    # ----------------------------------------------------------- siren
    P("\n" + "0b. Siren (LB508..LB54E, PCs $B546/$B54B; the step zp_9C comes from the dots eaten, Sub_B5C7)")
    sir = {}
    for f in sorted(byf):
        a = [w for w in byf[f] if w["pc"] == 0xB546]
        c = [w for w in byf[f] if w["pc"] == 0xB54B]
        if a and c:
            sir[f] = (a[0]["v"], c[0]["v"])
    have_dots = all(FR[f]["d34"] is not None for f in FR)
    if not sir:
        check(lenient, "no siren call in this trace")
    elif not have_dots:
        P("   (this trace has no dot counter in its state lines: the siren step cannot be derived, not judged; use a trace from tools/altirra_sound_levels.cmd)")
    else:
        sr = Siren()
        mism = 0
        steps_seen = collections.Counter()
        inits = sorted(e[1] for e in EV if e[0] == "INIT_BOARD")       # the board set-up clears the siren state (zp_E0 and zp_9C): the next call starts again at $28 with step 0
        ii = 0
        for f in sorted(sir):
            if f > last:
                break
            while ii < len(inits) and inits[ii] <= f:
                sr = Siren()
                ii += 1
            # The siren runs at $A994, BEFORE Sub_B5C7 ($A9CE) sets zp_9C in the same routine, so it uses the step chosen in the previous routine, i.e. from the dot counter as
            # logged at the start of this routine (or of the one before it); zp_9C is still 0 at the very first call after the reset.
            cand = []
            for g in (f, f - 1):
                if g in FR and FR[g]["d34"] is not None:
                    cand.append(siren_step(FR[g]["d34"], FR[g]["d36"]))
            if sr.E0 == 0:
                cand.append(0)
            cand = cand or [2]
            ok = False
            for st in dict.fromkeys(cand):
                trial = Siren()
                trial.DE, trial.DF, trial.E0 = sr.DE, sr.DF, sr.E0
                if trial.call(st) == sir[f]:
                    sr = trial
                    steps_seen[st] += 1
                    ok = True
                    break
            if not ok:
                mism += 1
                if mism <= 5:
                    P("   mismatch at f=%d: wrote %s, port (steps %s) from DE=%d DF=%d" % (f, tuple(hex(v) for v in sir[f]), cand, sr.DE, sr.DF))
                trial = Siren()
                trial.DE, trial.DF, trial.E0 = sr.DE, sr.DF, sr.E0
                sr = trial
                sr.call(cand[0])
        check(mism == 0, "siren: %d calls, every (AUDF2, AUDC2) equals the port with the step from the dot counter (%d mismatches); steps seen %s" % (sum(1 for f in sir if f <= last), mism, dict(sorted(steps_seen.items()))))
        if have_dots:
            maxd = max(FR[f]["d34"] + 256 * FR[f]["d36"] for f in FR)
            P("   dots eaten reached %d (siren steps 3 / 4 / 5 start at 176 / 224 / 240)" % maxd)
    # ----------------------------------------------------------- bonus
    P("\n1. Bonus item eaten (Sub_ABC9, PCs $ABFE/$AC01)")
    seq = bonus_sequence()
    P("   port: %d calls; AUDF1 %s ... AUDC1 %s" % (len(seq), [hex(a) for a, _ in seq[:3]] + ["..."] + [hex(a) for a, _ in seq[-3:]], sorted({hex(y) for _, y in seq})))
    ab = [w for w in W if w["pc"] in (0xABFE, 0xAC01)]
    frames = sorted({w["rf"] for w in ab})
    eps, cur = [], []
    for f in frames:
        if cur and f != cur[-1] + 1:
            eps.append(cur)
            cur = []
        cur.append(f)
    if cur:
        eps.append(cur)
    check(len(eps) >= (0 if lenient else 1), "%d bonus sound episodes in the trace (BONUS_APPEAR events: %d)" % (len(eps), cnt.get("BONUS_APPEAR", 0)))
    for ep in eps:
        got = [(next(w["v"] for w in byf[f] if w["pc"] == 0xABFE), next(w["v"] for w in byf[f] if w["pc"] == 0xAC01)) for f in ep]
        # an episode that the game's own death sequence cuts short (Pac-Man eaten within a few frames of the bonus item: DEATH_START right after the last call) must equal the FIRST calls of the port
        cut = [e for (n_, e, _x) in EV if n_ == "DEATH_START" and ep[-1] < e <= ep[-1] + 3]
        if cut and len(got) < len(seq) and got == seq[:len(got)]:
            check(True, "episode f=%d..%d: %d of %d calls, every (AUDF1, AUDC1) equals the port; cut short by DEATH_START at f=%d (Pac-Man was caught %d frames after eating the item)" % (ep[0], ep[-1], len(got), len(seq), cut[0], cut[0] - ep[0]))
            continue
        check(got == seq, "episode f=%d..%d: %d calls, every (AUDF1, AUDC1) equals the port%s" % (ep[0], ep[-1], len(ep), "" if got == seq else "  first difference at call %d: %s" % (next((i for i, (a, b) in enumerate(zip(got, seq)) if a != b), min(len(got), len(seq))), got[:3])))
        # the sound starts one frame after the eating frame: zp_F7 := 1 is set by the collision code, the call follows in the same frame order
        fr0 = FR.get(ep[0])
        P("     zp_F7 in the frame of the first call: %s" % (fr0 and fr0["f7"]))

    # ----------------------------------------------------------- ghost eaten
    P("\n2. Ghost eaten (the code at $A8EC and $B049-$B088)")
    model = ghost_eaten_frames()
    P("   port: %d frames (the collision frame, then %d sweep calls; last = ClearPokeyRegisters and AUDCTL := 0); AUDF1 first %s last %s" % (len(model), len(model) - 2, hex(model[1][0]), hex(model[-2][0])))
    ge = [(f, x) for (n, f, x) in EV if n == "GHOST_EATEN"]
    starts = sorted({w["rf"] for w in W if w["pc"] == 0xA8EE})
    check(len(starts) == len(ge), "A8EE (AUDC2 := 0) ran %d times for %d GHOST_EATEN events" % (len(starts), len(ge)))
    allowed_pcs = {0xA8EE, 0xB058, 0xB05B, 0xB060, 0xB072, 0xB075, 0xB078, 0xB07D, 0xB080, 0xB0E2, 0xB0EA, 0xB088}
    ok_all = True
    for f0 in starts:
        if f0 > last - 60:
            P("   (ghost eaten at f=%d is within 60 frames of the end of the trace: not judged)" % f0)
            continue
        # the first sweep call is in the same frame as A8EE or the next one; find the frame of the last (clear) write
        fe = next((f for f in range(f0, f0 + 200) if any(w["pc"] == 0xB088 for w in byf.get(f, []))), None)
        if fe is None:
            ok_all = False
            P("  FAIL ghost eaten at f=%d: no ClearPokeyRegisters/AUDCTL := 0 within 200 frames" % f0)
            continue
        start_sweep = f0 if any(w["pc"] in (0xB058, 0xB072) for w in byf.get(f0, [])) else f0 + 1
        # frame-by-frame comparison
        got = []
        t_a = min(w["t"] for w in byf.get(f0, []) if w["pc"] == 0xA8EE)
        before = [w for w in byf.get(f0, []) if w["pc"] != 0xA8EE and (w["rf"], w["t"]) < (f0, t_a) and w["t"] < t_a]
        for f in range(f0, fe + 1):
            d = {}
            for w in byf.get(f, []):
                if f == f0 and w in before:
                    continue                    # written by the normal sound routines (eyes, siren ...) earlier in the same routine, before the collision silenced channel 2
                if w["pc"] in allowed_pcs:
                    d.setdefault(w["reg"], w["v"])
                    d[w["reg"]] = w["v"]
                else:
                    d.setdefault(("other", w["pc"]), w["v"])
            got.append(d)
        # model frames: index 0 = A8EE (frame f0), then one sweep call per frame
        offset = 0 if start_sweep == f0 else 1
        exp = []
        if offset == 0:
            exp.append({**model[0], **model[1]})
            exp += model[2:]
        else:
            exp.append(model[0])
            exp += model[1:]
        bad = None
        if len(got) != len(exp):
            bad = "length %d frames against %d" % (len(got), len(exp))
        else:
            for i, (g, e) in enumerate(zip(got, exp)):
                gg = {k: v for k, v in g.items() if not isinstance(k, tuple)}
                if gg != e:
                    bad = "frame +%d: wrote %s expected %s" % (i, {k: hex(v) for k, v in gg.items()}, {k: hex(v) for k, v in e.items()})
                    break
        extra = {k for g in got for k in g if isinstance(k, tuple)}
        if before:
            P("     (f=%d: %d write(s) before the collision in the same routine, from PCs %s, are the normal routines')" % (f0, len(before), sorted("%04X" % w["pc"] for w in before)))
        if bad or extra:
            ok_all = False
        check(not bad and not extra, "ghost eaten at f=%d (ghost %s): %d frames to f=%d, every write equals the port%s%s" % (f0, next((x for (f, x) in ge if f in (f0, f0 - 1)), "?"), len(got), fe, "" if not bad else "; " + bad, "" if not extra else "; other writers %s" % sorted("%04X" % k[1] for k in extra)))
    P("   the ghost-eaten sound is a sweep from %.0f Hz up to %.0f Hz over %d frames (%.2f s); the rest of the game does not run meanwhile (the main loop jumps to $B049 at $A840)" % (
        V.CPU / 28 / 2 / (model[1][0] + 1), V.CPU / 28 / 2 / (model[-2][0] + 1), len(model), len(model) / V.FRAME_HZ))

    # ----------------------------------------------------------- frightened and eyes
    P("\n3. Frightened phase (Sub_AFD7, PCs $B021/$B028) and eyes returning (Sub_B02C, PCs $B042/$B028)")
    fr_calls, eye_calls = [], []
    for f in sorted(byf):
        ws = byf[f]
        a = [w for w in ws if w["pc"] == 0xB021]
        c = [w for w in ws if w["pc"] == 0xB028]
        e = [w for w in ws if w["pc"] == 0xB042]
        if a:
            fr_calls.append((f, a[0]["v"], c[0]["v"] if c else None))
        if e:
            eye_calls.append((f, e[0]["v"], c[0]["v"] if c else None))
    # zp_E4 (the frightened sound's "started" flag) is cleared (a) by the siren routine at every call ($B50A) and (b) when the frightened time ends ($AFAB).  Both can happen inside one
    # routine, so they are taken from the trace itself: a siren call (PC $B546) in a routine, or FrightenPhase = 0 at the start of the next routine after a call.
    fr_model = Frightened()
    mism = 0
    calls_checked = 0
    fr_by_f = {f: (v, ac) for f, v, ac in fr_calls}
    siren_f = {w["rf"] for w in W if w["pc"] == 0xB546}
    episode = 0
    prev_call = False
    for f in sorted(FR):
        if f > last:
            break
        if f in siren_f:
            fr_model.reset()
            prev_call = False
        if f - 1 in FR and FR[f - 1]["fc"] > 0 and FR[f]["fc"] == 0:
            fr_model.reset()                    # the time ended in the previous routine (AFAB), possibly while the eyes sound held channel 2 and no frightened call showed it
            prev_call = False
        if f in fr_by_f:
            if not prev_call:
                episode += 1
            exp = fr_model.call()
            calls_checked += 1
            prev_call = True
            if exp != fr_by_f[f]:
                mism += 1
                if mism <= 5:
                    P("   mismatch at f=%d: wrote %s expected %s" % (f, tuple(hex(v) for v in fr_by_f[f]), tuple(hex(v) for v in exp)))
            if f + 1 in FR and FR[f + 1]["fc"] == 0:
                fr_model.reset()                # the time ended in this routine: AFAB
                prev_call = False
    check((calls_checked > 0 or lenient) and mism == 0, "frightened: %d calls in %d episodes, every (AUDF2, AUDC2) equals the port (%d mismatches)" % (calls_checked, episode, mism))
    # Data flow inside one routine n (the state line FR(n) is logged BEFORE it runs, FR(n+1) after it): zp_F2 is recomputed at its start (Sub_B69E), so its value at the sound call is the one
    # logged in FR(n+1); zp_E5 and FrightenPhase at the call are those of FR(n) (a pellet eaten in this routine can start the phase; the time can end later in it).
    pellets = {e[1] for e in EV if e[0] == "PELLET"}
    near_pellet = lambda f: any(g in pellets for g in (f - 1, f, f + 1))
    wrong = [f for f in fr_by_f if f <= last and not (f in FR and f + 1 in FR and (FR[f]["fc"] > 0 or near_pellet(f)) and FR[f + 1]["f2"] == 0 and FR[f]["e5"] == 0)]
    check(not wrong, "the frightened routine is called only while FrightenPhase <> 0 (at the start of the routine, or a pellet is eaten in it), no eaten ghost is returning (zp_F2 = 0 as recomputed in it) and no ghost-eaten sound runs (zp_E5 = 0): %d exceptions %s" % (len(wrong), wrong[:3]))
    # eyes
    eyes = Eyes()
    mism = 0
    ec_by_f = {f: (v, ac) for f, v, ac in eye_calls}
    for f in sorted(FR):
        if f > last:
            break
        if FR[f]["f2"] == 0:
            eyes.reset()                        # B6F5: zp_F3 := 0
        if f in ec_by_f:
            exp = eyes.call()
            if exp != ec_by_f[f]:
                mism += 1
                if mism <= 5:
                    P("   mismatch at f=%d: wrote %s expected %s" % (f, tuple(hex(v) for v in ec_by_f[f]), tuple(hex(v) for v in exp)))
    check((len(eye_calls) > 0 or lenient) and mism == 0, "eyes: %d calls, every (AUDF2, AUDC2) equals the port (%d mismatches); values %s" % (len(eye_calls), mism, ("%d..%d" % (min(v for _, v, _ in eye_calls), max(v for _, v, _ in eye_calls))) if eye_calls else "-"))
    wrong = [f for f in ec_by_f if f <= last and not (f in FR and f + 1 in FR and FR[f + 1]["f2"] > 0 and FR[f]["e5"] == 0)]
    check(not wrong, "the eyes routine is called only while an eaten ghost is returning (zp_F2 <> 0 as recomputed in the routine) and no ghost-eaten sound runs (zp_E5 = 0 at its start): %d exceptions %s" % (len(wrong), wrong[:3]))

    # ----------------------------------------------------------- channel 2 ownership
    P("\n4. Who writes channel 2 (AUDC2) in each situation (frames, PCs)")
    own = collections.defaultdict(collections.Counter)
    for f in sorted(FR):
        if f > last or f < 1520:
            continue
        s = FR[f]
        sit = "ghost-eaten sound (zp_E5)" if s["e5"] else ("eaten ghost returning (zp_F2)" if s["f2"] else ("frightened (FrightenPhase)" if s["fc"] else "normal"))
        pcs = tuple(sorted({"%04X" % w["pc"] for w in byf.get(f, []) if w["reg"] == 3}))
        own[sit][pcs] += 1
    for sit, c in own.items():
        P("   %-32s %s" % (sit, dict(c.most_common(4))))

    # ----------------------------------------------------------- extra life and board change
    P("\n5. Extra life and board change: no sound routine exists (census of all POKEY write sites: 31, none for these)")
    for (n, f, x) in EV:
        if n == "EXTRA_LIFE":
            fb, fa = FR[f - 2]["lives"], FR[f + 3]["lives"]
            pcs = collections.Counter("%04X" % w["pc"] for ff in range(f - 1, f + 90) for w in byf.get(ff, []) if w["reg"] <= 8)
            P("   EXTRA_LIFE f=%d: lives %s -> %s; sound writers in the next 90 frames: %s" % (f, fb, fa, dict(pcs)))
            check(fa[0] == fb[0] + 1, "the extra life adds one life (player 1: %d -> %d)" % (fb[0], fa[0]))
            check(set(pcs) <= {"B546", "B54B", "B0DD", "B0E2", "B021", "B028", "B042", "ABFE", "AC01", "A8EE", "B058", "B05B", "B060", "B072", "B075", "B078", "B07D", "B080", "B088", "B0EA"}, "no PC outside the known sound routines writes a sound register around the extra life")
    for (n, f, x) in EV:
        if n == "LEVEL_ADV":
            pcs = collections.Counter("%04X" % w["pc"] for ff in range(f - 200, f + 120) for w in byf.get(ff, []) if w["reg"] <= 8)
            tunes = [e for e in EV if e[0] == "TUNE" and f - 200 <= e[1] <= f + 300]
            P("   LEVEL_ADV f=%d: level counter %d -> %d; sound writers f-200..f+120: %s; start tune steps in f-200..f+300: %d" % (f, FR[f - 3]["lv"], FR[f + 100]["lv"], dict(pcs), len(tunes)))
            check(len(tunes) == 0, "the start tune does not play at a board change")

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
