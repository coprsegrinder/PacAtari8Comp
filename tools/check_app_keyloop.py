"""Stage 78d: the main program (the key loop `$A4BA-$A572`) in port form (tools/core_app.key_loop) against the ROM on the concrete 6502, from random states, branch by branch (docs/40: 27 conditional branches, 54
outcomes).  A state is the World the game could be in, the place the main program is in between two frames (a pass, the debounce, the release, the wait for the clock), its accumulator, and the inputs of the frame
(the console, the two triggers, the keyboard shadow and its delay, the attract values).  The ROM runs the main program until it settles (a wait, or idle passes), the port runs `key_loop`; the whole state and the place
the program is in are compared.
Usage: python -I tools/check_app_keyloop.py [--write analysis/evidence-app-keyloop-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import check_app as CA  # noqa: E402
import check_app_board as CAB  # noqa: E402
import check_app_frame as CAF  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_play as CPL  # noqa: E402
import core_app as APP  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT
PHASE_PC = {APP.TOP: 0xA4BA, APP.DEBOUNCE: 0xA511, APP.RELEASE: 0xA51C, APP.CLOCK_WAIT: 0xA493}
CONSOLES = [7, 7, 7, 6, 5, 3, 4, 2, 1, 0]


def setup(m, rng, phase):
    CAF.base_state(m, rng)
    for a in range(0x100):
        if a not in (0x14, 0x2B) and rng.random() < 0.15:        # the clock and the player on turn (an index) stay as they are
            m.mem[a] = rng.randrange(256)
    m.mem[0x19] = rng.choice([0, 0, 1, 2, 3, 3, 4, 5])                    # GameState
    m.mem[0x1B] = rng.choice([0, 1, 2, 4, 6, 8, 10, 12, 12, 3, rng.randrange(256)])
    m.mem[0x1A] = rng.randrange(2)
    m.mem[0x9B] = rng.choice([0, 0, 1])
    m.mem[0x20] = rng.choice([0, 0, 1])
    m.mem[0x1E] = rng.choice([0, 0, 1, 5, 0xE2])
    m.mem[0x1C] = rng.choice([0, 1, 2])
    m.mem[0x45] = rng.choice([0, 0, 1, 0xFF])
    m.mem[0x46] = rng.choice(CONSOLES)
    m.mem[0x4E] = rng.choice([0xFF, 0xF6, rng.randrange(256)])
    m.mem[0x4F] = rng.choice([0, 0x80, rng.randrange(256)])
    m.mem[0x0284] = rng.choice([1, 1, 1, 0])
    m.mem[0x0285] = rng.choice([1, 1, 1, 0])
    m.mem[0x02FC] = rng.choice([0xFF, 0xFF, 0x21, rng.randrange(256)])
    m.mem[0x02F1] = rng.choice([0, 0, 0, 3])
    m.mem[0xD01F] = rng.choice(CONSOLES)
    acc = rng.choice(CONSOLES)
    m.pc = PHASE_PC[phase]
    m.a = acc if phase in (APP.DEBOUNCE, APP.RELEASE) else (m.mem[0x14] if rng.random() < 0.5 else rng.randrange(256))
    m.s = 0xFF
    return acc


def settle(m):
    last = None
    for _ in range(CA.MAX_CHUNKS):
        for _ in range(CA.CHUNK):
            if m.pc >= 0xC000:
                lo, hi = m.pull(), m.pull()
                m.pc = (((hi << 8) | lo) + 1) & 0xFFFF
                continue
            m.step()
        snap = (bytes(m.mem[0:0x100]), bytes(m.mem[0x200:0x300]), bytes(m.mem[0x0C00:0x1800]))
        if snap == last and (0xA4BA <= m.pc <= 0xA572 or 0xA493 <= m.pc <= 0xA495):
            return
        last = snap
    raise RuntimeError("did not settle")


class Stub:
    def __init__(self, console):
        self.c = console

    def console(self):
        return self.c


def run_phase(phase, n, seed):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    C.Machine.wr = CAB._wr
    C.Machine.rd = CPL._rd
    reached = {}
    try:
        for _ in range(n):
            vals = [rng.randrange(256) for _ in range(12)]
            m = A.fresh(base, vals)
            acc = setup(m, rng, phase)
            m.hw = [0] * 16
            console = m.mem[0xD01F]
            w = W.World().load(m.mem)
            kl = APP.KeyLoop()
            kl.pc = phase
            kl.acc = acc if phase in (APP.DEBOUNCE, APP.RELEASE) else 0
            kl.clock = m.a if phase == APP.CLOCK_WAIT else 0
            del CAB.LOG[:]
            w.pokey = []
            settle(m)
            APP.key_loop(w, Stub(console), kl, console)
            d = CAB.diffs(m, w, CG.SCRATCH)
            if CA.RomApp.phase(type("R", (), {"m": m})()) != kl.state():
                d.append("main program %s != %s" % (CA.RomApp.phase(type("R", (), {"m": m})()), kl.state()))
            reached[kl.pc] = reached.get(kl.pc, 0) + 1
            if d:
                bad.append((phase, console, d[:4]))
    finally:
        C.Machine.wr = CAB._orig
        C.Machine.rd = CPL._orig_rd
    return n, bad, reached


def report(quick=False):
    n = 400 if quick else 4000
    L = ["The main program (the key loop) in port form (tools/core_app.key_loop) against the ROM on the concrete 6502 (tools/check_app_keyloop.py, stage 78d): from each place the program can be in between two frames, from random states and inputs: zero page (except the scratch), maze and its three copies, title screen, status rows, shadows, pages, positions, picture buffers, the ordered chip writes, and the place the program is in with its accumulator compared", ""]
    rows = []
    for phase in (APP.TOP, APP.DEBOUNCE, APP.RELEASE, APP.CLOCK_WAIT):
        nn, bad, reached = run_phase(phase, n, 11 + len(phase))
        rows.append((phase, bad))
        L.append("from '%s': %d states: %d differences (the program ends in: %s)" % (phase, nn, len(bad), ", ".join("%s %d" % kv for kv in sorted(reached.items()))))
        for b in bad[:3]:
            L.append("  %s" % (b,))
    return L, rows


def main():
    L, rows = report("--quick" in sys.argv)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if any(b for _, b in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
