"""OV-64: a search for the heaviest play frame of the vertical-blank handler on the CONCRETE 6502 (tools/cpu6502.py), to set a lower bound beside the static upper bound of tools/static_wcet.py.
The handler ($A5FD) runs on a machine whose memory is a random play frame (tools/algorithm_models7.py frame_setup, the one the stage-55 tests use) and the instruction cycles are counted exactly: the cycle table of
tools/static_wcet.py with the real index registers (page crossings) and the real branch outcomes.  A hill climb then changes one byte of the zero page and of the tables at a time and keeps what costs at least as much.
The states reached are arbitrary memory with the dispatcher in the play state: not all of them can happen in a game, so the maximum found is an upper estimate of what real play costs and a lower bound of the static bound.
Usage: python -I tools/fuzz_concrete.py [--seconds 600] [--seed 1] [--write analysis/evidence-fuzz-concrete-summary.txt]"""
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import algorithm_models as A      # noqa: E402
import algorithm_models6 as M6    # noqa: E402
import algorithm_models7 as M7    # noqa: E402
import cpu6502 as C               # noqa: E402
import static_wcet as W           # noqa: E402
import absint6502 as AB           # noqa: E402

DOMAINS = False
ANNEAL = False
STEPS = 4000
T0 = 400.0
PROG = AB.Program()
INS = PROG.ins


class Counter:
    """counts the cycles of every instruction the concrete machine executes"""

    def __init__(self):
        self.total = 0
        self.calls = {}                                          # callee -> inclusive cycles (calls made from the handler's own level)
        self.bypc = {}                                           # pc -> cycles spent at that instruction
        self.stack = []
        self.orig = C.Machine.step

    def install(self):
        counter = self

        def step(m):
            pc, x, y = m.pc, m.x, m.y
            ins = INS.get(pc)
            counter.orig(m)
            if ins is not None and ins[1] == "jsr":
                counter.stack.append((ins[3], counter.total))
            if ins is not None and ins[1] == "rts" and counter.stack:
                e, t0 = counter.stack.pop()
                counter.calls[e] = counter.calls.get(e, 0) + counter.total + 6 - t0
            if ins is not None:
                ln, mn, mode, op = ins
                c = W.cost(INS, pc, m.pc, x, y)
                if mode == "izy" and mn in W.READ:               # the exact page crossing of an indirect indexed read
                    c -= 1
                    if (m.mem[op] + y) > 0xFF:
                        c += 1
                counter.total += c
                counter.bypc[pc] = counter.bypc.get(pc, 0) + c
        C.Machine.step = step

    def remove(self):
        C.Machine.step = self.orig


def build(base, rng):
    m = M6.prepare(base, rng)
    M7.frame_setup(m, rng, "play")
    m.random = [rng.randrange(256) for _ in range(12)]
    return m


def cost_of(m, counter):
    counter.total = 0
    counter.calls = {}
    counter.stack = []
    counter.bypc = {}
    try:
        m.call(0xA5FD)
    except Exception:
        return -1
    return counter.total


# the bytes the climb may change: the zero page and the tables the frame setup fills (the sight offsets, the maze pointer area is left alone)
CLIMB = list(range(0x00, 0x100)) + list(range(0x2000, 0x2050)) + list(range(0x0278, 0x027A)) + [0xD009, 0xD00A, 0xD002] + list(range(0x02C0, 0x02C4))
# --domains: the bytes of the game that have a documented domain are changed within it (ghost states: the 16 states of docs/34; directions 1, 2, 4, 8; positions: a junction line or a maze coordinate; timers 0-$96; move delays 0-7)
D16 = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0]
JY = [0x0C, 0x1C, 0x2C, 0x3C, 0x4C, 0x5C, 0x6C, 0x7C, 0x8C, 0x9C]      # filled from the ROM below
JX = list(JY)


def load_junctions():
    global JY, JX
    with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
        rom = fh.read()
    JY = list(rom[0xBB83 - 0xA000:0xBB83 - 0xA000 + 10])
    JX = list(rom[0xBB8D - 0xA000:0xBB8D - 0xA000 + 10])


def domain_value(addr, rng):
    if 0xCE <= addr <= 0xD1:
        return rng.choice(D16)
    if 0x8F <= addr <= 0x93:
        return rng.choice([1, 2, 4, 8])
    if 0x85 <= addr <= 0x89:
        return rng.choice(JY) if rng.random() < 0.8 else rng.randrange(0x20, 0xB0)
    if 0x8A <= addr <= 0x8E:
        return rng.choice(JX) if rng.random() < 0.8 else rng.randrange(0x2A, 0xCB)
    if 0xCA <= addr <= 0xCD:
        return rng.choice([0, 0, 0, 1, rng.randrange(0x97)])
    if 0xB5 <= addr <= 0xB9:
        return rng.randrange(8)
    return None


PLAY_FIXED = {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 1, 0x22: 1, 0x24: 0, 0x23: 0, 0xAA: 0, 0xE5: 0, 0xED: 0}      # the dispatcher stays in the play frame


def snapshot(m):
    return (bytes(m.mem), list(m.random))


def restore(m, snap):
    m.mem[:] = snap[0]
    m.random = list(snap[1])


GHOST_BLOCK = [(0xCE, 1), (0xCA, 1), (0x85, 1), (0x8A, 1), (0x8F, 1), (0xB5, 1)]     # (first byte, step): the per-ghost bytes, ghost g at first + g


def mutate(m, rng):
    """one change of the memory of a frame: a byte, a random number the frame reads, or a whole ghost copied onto another"""
    r = rng.random()
    if r < 0.12:
        m.random[rng.randrange(len(m.random))] = rng.randrange(256)
        return
    if ANNEAL and r < 0.22:                                  # copy ghost g's state, timer, position, direction and delay onto ghost h: the heavy cases together
        g, h = rng.sample(range(4), 2)
        for first, st in GHOST_BLOCK:
            m.mem[first + h * st] = m.mem[first + g * st]
        return
    addr = rng.choice(CLIMB)
    if addr in PLAY_FIXED:
        return
    dv = domain_value(addr, rng) if DOMAINS else None
    if DOMAINS and dv is None and rng.random() < 0.9:
        return                                               # in --domains mode the bytes without a documented domain are changed rarely
    m.mem[addr] = dv if dv is not None else (rng.randrange(256) if rng.random() < 0.7 else rng.choice([0, 1, 2, 4, 8, 0x10, 0x20, 0x42, 0x44, 0x80, 0xFF]))


def main():
    a = sys.argv
    seconds = float(a[a.index("--seconds") + 1]) if "--seconds" in a else 600.0
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 1
    rng = random.Random(seed)
    global DOMAINS, ANNEAL, STEPS, T0
    DOMAINS = "--domains" in a
    ANNEAL = "--anneal" in a
    STEPS = int(a[a.index("--steps") + 1]) if "--steps" in a else 4000
    T0 = float(a[a.index("--temp") + 1]) if "--temp" in a else 400.0
    if DOMAINS:
        load_junctions()
    base = A.started_machine()
    counter = Counter()
    counter.install()
    best_overall, best_start, runs, restarts = 0, 0, 0, 0
    best_state = None
    hist = []
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            m = build(base, rng)
            for k, v in PLAY_FIXED.items():
                m.mem[k] = v
            if DOMAINS:
                for ad in list(range(0xCE, 0xD2)) + list(range(0x8F, 0x94)) + list(range(0x85, 0x8F)) + list(range(0xCA, 0xCE)) + list(range(0xB5, 0xBA)):
                    m.mem[ad] = domain_value(ad, rng)
            snap = snapshot(m)
            cur = cost_of(m, counter)
            runs += 1
            restart_best = cur
            stale = 0
            step_no = 0
            rbest, rbest_snap = cur, snap
            while time.time() - t0 < seconds:
                if ANNEAL:
                    if step_no >= STEPS:
                        break
                    temp = T0 * (1.0 - step_no / STEPS) + 1e-9
                elif stale >= 400:
                    break
                step_no += 1
                restore(m, snap)
                nmut = 1 if (not ANNEAL or rng.random() < 0.6) else rng.randint(2, 4)
                for _ in range(nmut):
                    mutate(m, rng)
                inp = snapshot(m)                                  # the INPUT of this run (the run changes the memory)
                c = cost_of(m, counter)
                runs += 1
                take = c >= cur or (ANNEAL and rng.random() < math.exp((c - cur) / temp))
                if take:
                    stale = 0 if c > cur else stale + 1
                    cur = c
                    snap = inp
                else:
                    stale += 1
                if cur > rbest:
                    rbest, rbest_snap = cur, snap
            cur, snap = rbest, rbest_snap
            restarts += 1
            hist.append(cur)
            if cur > best_overall:
                best_overall = cur
                restore(m, snap)
                cost_of(m, counter)
                best_state = (snap, dict(counter.calls), dict(counter.bypc))
            print("restart %d: %d cycles (best %d, %d runs, %.0f s)" % (restarts, cur, best_overall, runs, time.time() - t0), flush=True)
    finally:
        counter.remove()
    hist.sort()
    lines = [("Simulated-annealing" if ANNEAL else "Hill-climbing") + " search for the heaviest play frame on the concrete 6502 (tools/fuzz_concrete.py, seed %d%s): %d handler runs in %d restarts, %.0f s" % (seed, ", annealing %d steps from %.0f" % (STEPS, T0) if ANNEAL else "", runs, restarts, time.time() - t0),
             "instruction cycles of the heaviest frame found: %d (static bound of the play frame: 32,049; budget on the game screen 16,100)" % best_overall,
             "heaviest of each restart (sorted): " + " ".join(str(v) for v in hist[-15:])]
    if best_state is not None:
        snap, calls, bypc = best_state
        z = snap[0]            # the memory the best frame started from
        lines.append("the random values it reads: " + " ".join("%02X" % v for v in snap[1]))
        lines.append("the heaviest frame: GhostState %s, GhostTimer %s, EntityY %s, EntityX %s, EntityDir %s, MoveDelayCount %s, RTCLOK2 %02X" % (
            " ".join("%02X" % z[0xCE + g] for g in range(4)), " ".join("%02X" % z[0xCA + g] for g in range(4)), " ".join("%02X" % z[0x85 + g] for g in range(5)),
            " ".join("%02X" % z[0x8A + g] for g in range(5)), " ".join("%02X" % z[0x8F + g] for g in range(5)), " ".join("%02X" % z[0xB5 + g] for g in range(5)), z[0x14]))
        owner = {}
        for e, f in sorted(PROG.F.items(), key=lambda kv: -len(kv[1].body)):
            for ad in f.body:
                owner[ad] = e
        per = {}
        for pcx, cc in bypc.items():
            per[owner.get(pcx, 0)] = per.get(owner.get(pcx, 0), 0) + cc
        lines.append("cycles by routine (the instruction's own routine): " + ", ".join("$%04X %d" % (e, c) for e, c in sorted(per.items(), key=lambda kv: -kv[1])[:10]))
        top = sorted(bypc.items(), key=lambda kv: -kv[1])[:8]
        lines.append("the 8 instructions that cost most: " + ", ".join("$%04X %d" % kv for kv in top))
        lines.append("calls in it (inclusive cycles): " + ", ".join("$%04X %d" % (e, c) for e, c in sorted(calls.items(), key=lambda kv: -kv[1])[:12]))
    txt = chr(10).join(lines) + chr(10)
    if "--write" in a:
        with open(os.path.join(ROOT, a[a.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
