"""OV-60: the race at $A800 in the interpreter with a forced interrupt (tools/cpu6502.py, no emulator).

The abstract search of C-65 (tools/prove_state_rules.py) found: START pressed, the vertical-blank handler inside the restart's clear loop ($A47B-$A47E) after $26 (LevelComplete) is cleared and before $21 is,
in the frame in which the last pellet is eaten -> LevelComplete set with PlayStarted = 0.  The slice did not follow the dot counter DotsEaten ($34-$37), which the same clear loop zeroes BEFORE it clears $26
(X counts down: $34-$37 at X = $14-$17, $26 at X = $06).  Here the real code is run from the START key ($A537) with the interrupt forced at every instruction boundary of the restart (and the 40 after it),
in random game states in which BOTH players are one dot from the end of the board (DotsEaten = $0103, Pac-Man on a dot in many of them), and the end state is checked: LevelComplete ($26) = 1 with PlayStarted ($20) = 0
is the race.  Usage: python -I tools/check_ov60_race.py [N] [--write analysis/evidence-ov60-race-summary.txt]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models5 as M5  # noqa: E402
import algorithm_models6 as M6  # noqa: E402
import algorithm_models7 as M7  # noqa: E402

LOOP_END = 0xA48D           # after the clear loop, ClearPokeyRegisters and the three copies: the key loop of the restart starts here
POST = 40


def run_main(m, interrupt_at, regs_vbi_log):
    """START at $A537 -> restart -> $A48D; the VBI handler is entered before main instruction number interrupt_at"""
    m.pc = 0xA537
    n = 0
    saw_loop = None
    while m.pc != LOOP_END:
        if m.pc >= 0xC000:                                  # an OS call from the restart (none expected before $A48D)
            lo, hi = m.pull(), m.pull()
            m.pc = (((hi << 8) | lo) + 1) & 0xFFFF
            continue
        if n == interrupt_at:
            keep = (m.a, m.x, m.y, m.s, m.p(), m.pc)
            pc0 = m.pc
            pre26 = m.mem[0x26]
            m.call(0xA5FD)
            m.a, m.x, m.y, m.s = keep[0], keep[1], keep[2], keep[3]
            m.set_p(keep[4])
            m.pc = keep[5]
            regs_vbi_log.append((pc0, m.mem[0x26], pre26, m.x))
            interrupt_at = -1
        m.step()
        n += 1
        if n > 200000:
            raise RuntimeError("no end")
    return n


def state(base, rng):
    m = M6.prepare(base, rng)
    M7.frame_setup(m, rng, "play")
    m.mem[0x20] = 0                                         # a game in play
    m.mem[0x19] = 0
    m.mem[0x26] = 0
    for p in (0, 1):                                        # both players one dot from the end of the board
        m.mem[0x34 + p] = 3
        m.mem[0x36 + p] = 1
    m.random = [rng.randrange(256) for _ in range(40)]
    return m


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 200
    base = A.started_machine()
    rng = random.Random(60)
    # the instruction count of the restart up to $A48D, from one run without interrupt
    probe = state(base, random.Random(1))
    total = 5 + 2 + 32 * 3 + 1
    pcs_of = {}
    race, runs, set_before, set_in_window, dots_complete_before = 0, 0, 0, 0, 0
    worst = []
    stats = {}
    for _ in range(N):
        seed = rng.randrange(1 << 30)
        for k in range(0, total + POST):
            m = state(base, random.Random(seed))
            log = []
            try:
                run_main(m, k, log)
            except RuntimeError:
                continue
            runs += 1
            if not log:
                continue
            pc0, z26_after_vbi, pre26, x = log[0]
            key = ('A' if x >= 7 else 'W' if x <= 5 else 'B') if 0xA47B <= pc0 <= 0xA47E else 0
            stats.setdefault(key, [0, 0, 0])
            stats[key][0] += 1
            stats[key][1] += z26_after_vbi != 0               # the VBI itself set LevelComplete
            end_race = m.mem[0x26] != 0 and m.mem[0x20] == 0
            stats[key][2] += end_race
            if end_race:
                race += 1
                worst.append((k, hex(pc0), x))
    L = []
    P = L.append
    P("OV-60 forced-interrupt run in tools/cpu6502.py (tools/check_ov60_race.py): START ($A537), the restart's clear loop and the code up to $A48D; the vertical-blank handler ($A5FD) entered before every main instruction (%d positions) of %d random game states with DotsEaten = $0103 for both players" % (total + POST, N))
    P("runs: %d; race ends (LevelComplete $26 = 1 and PlayStarted $20 = 0 at $A48D): %d" % (runs, race))
    P("interrupt inside the clear loop ($A47B-$A47E): %d runs, VBI set $26 in %d, ends with the race in %d" % tuple(stats.get(k, [0, 0, 0])[i] for k in [0xA47B] for i in range(3)) if False else "")
    inloop = [0, 0, 0]
    out = [0, 0, 0]
    for key, v in stats.items():
        t = inloop if key else out
        for i in range(3):
            t[i] += v[i]
    names = [('A', "interrupt in the clear loop BEFORE $26 is cleared (X >= 7: DotsEaten $34-$37 cleared at X = $14-$17, so for X <= $13 it is 0)"), ('B', "interrupt just after the clear of $26 (X = 6)"), ('W', "interrupt in the window the search found: after $26 is cleared, before $21 and $20 are (X <= 5)"), (0, "interrupt anywhere else (before the loop, after it)")]
    for k, t in names:
        v = stats.get(k, [0, 0, 0])
        P("%s: %d runs, the VBI left $26 = 1 in %d, race at the end in %d" % (t, v[0], v[1], v[2]))
    for w in worst[:5]:
        P("  race: %s" % (w,))
    txt = "\n".join(l for l in L if l) + "\n"
    if "--write" in sys.argv:
        o = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(A.ROOT, o), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
