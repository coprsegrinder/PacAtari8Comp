"""OV-67: the port-form ghost state machine (tools/core_ghost.py) against the ROM routines on the concrete 6502.  For each call the World is loaded from the memory image, the ROM routine runs on the machine, the
port function runs on the World, and the zero page (except the declared scratch bytes), the maze, the status rows and the OS colour shadows are compared; the number of RANDOM values used must be equal too.
Usage: python -I tools/check_ghost.py [--write analysis/evidence-ghost-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import core_ghost as G  # noqa: E402
import core_tables as T  # noqa: E402
import core_world as W  # noqa: E402

ROOT = A.ROOT
SCRATCH = {0x2A, 0x3C, 0x3D, 0x3E, 0x3F, 0xA5}     # Scratch2A (the mask between JunctionLookup and the steering), SrcPtr, DstPtr (the pointers of the drawing: the pictures themselves are compared), JunctionTemp ($A5): temporaries of the ROM routines
YS = [T.rom(0xBB83 + i) for i in range(10)]
XS = [T.rom(0xBB8D + i) for i in range(10)]
STATES = [0x00, 0x01, 0x02, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0, 0xC2, 0x04, 0x40, 0xFF]


def world_diff(m, w, before):
    """names of the bytes where the machine and the World differ"""
    exp = bytearray(m.mem)
    w.store(exp)
    out = []
    for a in range(0x100):
        if a not in SCRATCH and m.mem[a] != exp[a]:
            out.append("%02X:%02X!=%02X" % (a, m.mem[a], exp[a]))
    if m.mem[0x0C00:0x1000] != exp[0x0C00:0x1000]:
        out.append("maze")
    if m.mem[0x2000:0x2050] != exp[0x2000:0x2050]:
        out.append("status")
    if m.mem[0x0200:0x0300] != exp[0x0200:0x0300]:
        out.append("shadow")
    if m.mem[0x2300:0x2800] != exp[0x2300:0x2800]:               # the scene (OV-69): the player-missile pages, the eight positions, the picture buffers
        out.append("pm")
    if m.mem[0xD000:0xD008] != exp[0xD000:0xD008]:
        out.append("hpos")
    if m.mem[0x0400:0x0420] != exp[0x0400:0x0420]:
        out.append("picbuf")
    return out


def lattice(rng):
    y = rng.choice(YS) if rng.random() < 0.75 else rng.randrange(256)
    x = rng.choice(XS) if rng.random() < 0.75 else rng.randrange(256)
    return x, y


def setup(m, rng, ghosts=True):
    M2.randomize(m, rng)
    for g in range(5):
        x, y = lattice(rng)
        if rng.random() < 0.15:
            x, y = rng.choice([0x7C, 0x70, 0x88, 0x76, 0x82]), rng.choice([0x64, 0x70, 0x74, 0x78])
        m.mem[0x8A + g], m.mem[0x85 + g] = x, y
        m.mem[0x8F + g] = rng.choice([1, 2, 4, 8])
    if rng.random() < 0.3:                                       # Pac-Man in line with a ghost
        g = rng.randrange(4)
        if rng.random() < 0.5:
            m.mem[0x89] = m.mem[0x85 + g]
        else:
            m.mem[0x8E] = m.mem[0x8A + g]
    m.mem[A.DRAW_ONLY if hasattr(A, "DRAW_ONLY") else 0xAE] = rng.choice([0, 0, 0, 1, 7])
    for g in range(4):
        m.mem[0xCE + g] = rng.choice(STATES)
        m.mem[0xCA + g] = rng.choice([0, 1, 2, 0x96, rng.randrange(256)])
        m.mem[0xD2 + g] = rng.choice([0, 1, 5, 0xFF, rng.randrange(14), (13, 8, 8, 11)[g] - 1, (13, 8, 8, 11)[g], (13, 8, 8, 11)[g] - 2])
        m.mem[0xBA + g] = rng.randrange(16)
        m.mem[0xBE + g] = rng.choice([0, 1, 5, 20, rng.randrange(256)])
        m.mem[0xC2 + g], m.mem[0xC6 + g] = lattice(rng)
        if rng.random() < 0.3:                                   # the ghost stands on its target: the arrival branches
            m.mem[0xC2 + g], m.mem[0xC6 + g] = m.mem[0x8A + g], m.mem[0x85 + g]
        if rng.random() < 0.15:                                  # the target is the ghost's patrol start or corner
            r = rng.randrange(16)
            m.mem[0xBA + g] = r
            m.mem[0x8A + g], m.mem[0x85 + g] = T.rom(0xBCEE + 2 * r), T.rom(0xBCEE + 2 * r + 1)
            m.mem[0xC2 + g], m.mem[0xC6 + g] = m.mem[0x8A + g], m.mem[0x85 + g]
        if rng.random() < 0.1:
            m.mem[0x8A + g], m.mem[0x85 + g] = T.rom(0xBD0E + 2 * g), T.rom(0xBD0E + 2 * g + 1)
    m.mem[0xAD] = rng.choice([0, 1, 0x50, 0xA0, rng.randrange(256)])
    m.mem[0x14] = rng.randrange(256)
    m.mem[0x2B] = rng.randrange(2)
    for p in range(2):
        m.mem[0x34 + p] = rng.choice([0, 0x50, 0xAF, 0xB0, 0xDF, 0xE0, 0xEF, 0xF0, rng.randrange(256)])
        m.mem[0x36 + p] = rng.choice([0, 0, 0, 1])


def run(name, rom_addr, rom_regs, port, n, seed, per=None):
    """n random states; `rom_regs(rng, m)` -> dict(x=..) for the ROM call; `port(w, rng_values)` runs the port function"""
    base = A.started_machine()
    rng = random.Random(seed)
    bad, used = [], [0, 0, 0, 0]
    trans = {}
    for k in range(n):
        rnd = [rng.randrange(256) for _ in range(4)]
        m = A.fresh(base, list(rnd))
        setup(m, rng)
        regs = rom_regs(rng, m)
        w = W.World().load(m.mem)
        st0 = m.mem[0xCE + regs["x"]] if regs.get("x", 9) < 4 else None
        it = iter(rnd)
        m.call(rom_addr, **regs)
        port(w, regs, it)
        left = len(list(it))
        if regs.get("x", 9) < 4:
            trans[(st0, m.mem[0xCE + regs["x"]])] = trans.get((st0, m.mem[0xCE + regs["x"]]), 0) + 1
        u = len(rnd) - left
        used[u] += 1
        d = world_diff(m, w, None)
        if len(m.random_reads) != u:
            d.append("random %d!=%d" % (len(m.random_reads), u))
        if d:
            bad.append((regs, d[:5]))
    return n, bad, used, trans


def main_checks(quick=False):
    N = 800 if quick else 6000
    rows = []

    def add(name, what, rom_addr, regs, port, n=N, seed=1):
        nn, bad, used, trans = run(name, rom_addr, regs, port, n, seed)
        rows.append((name, what, nn, bad, used, trans))

    gx = lambda rng, m: {"x": rng.randrange(4)}
    add("ghost_behaviour", "GhostBehaviour $B7F5: every state ($00 .. $FF set, 19 values), on and off the lattice, RANDOM", 0xB7F5, gx, lambda w, r, it: G.ghost_behaviour(w, r["x"], it), N * 4)
    add("ghost_sees", "GhostSeesPacMan $BA19 (ghost and Pac-Man in line on lattice rows and columns, 4 directions, every RTCLOK2)", 0xBA19, gx, lambda w, r, it: G.ghost_sees_pacman(w, r["x"]), N * 3)
    add("chase_timer_siren_sight", "ChaseTimerSirenSight $B5C7 (the dots around every threshold, RTCLOK2 multiples of 8, the forced chase)", 0xB5C7, lambda rng, m: {}, lambda w, r, it: G.chase_timer_siren_sight(w), N * 2)
    add("force_chase", "ForceChase $B616 (with the chase timer left at $FF)", 0xB616, lambda rng, m: {"x": rng.randrange(4)}, lambda w, r, it: G.force_chase(w, r["x"]), N)
    add("step_entity", "StepAndDrawEntity $B902 (the movement and the picture; the four ghosts: x = 4 is never drawn this way)", 0xB902, lambda rng, m: {"x": rng.randrange(4), "a": rng.choice([1, 2, 4, 8, 8, 0, 3, 0x10])},
        lambda w, r, it: G.step_entity(w, r["x"], r["a"]), N)
    add("house_waiting_tick", "HouseWaitingTick $B7A5", 0xB7A5, lambda rng, m: {}, lambda w, r, it: G.house_waiting_tick(w), N * 2)
    add("house_bob_step", "HouseBobStep $B7D6", 0xB7D6, lambda rng, m: {"x": rng.randrange(1, 4)}, lambda w, r, it: G.house_bob_step(w, r["x"]), N)
    add("house_leave", "HouseLeaveStep $B738 / HouseLeaveGhost2 $B76D / HouseLeaveGhost3 $B777 (as the code reaches them)", 0xB738, lambda rng, m: {"x": rng.randrange(1, 4)}, lambda w, r, it: G.house_leave_step(w, r["x"]), N)
    add("house_leave2", "HouseLeaveGhost2 $B76D", 0xB76D, lambda rng, m: {"x": 2}, lambda w, r, it: G.house_leave_ghost2(w, 2), N)
    add("house_leave3", "HouseLeaveGhost3 $B777", 0xB777, lambda rng, m: {"x": 3}, lambda w, r, it: G.house_leave_ghost3(w, 3), N)
    add("house_enter_step", "HouseEnterStep $B781 (the eaten ghost's way into the house)", 0xB781, lambda rng, m: {"x": rng.randrange(4)}, lambda w, r, it: G.house_enter_step(w, r["x"]), N)
    return rows


def report(quick=False):
    rows = main_checks(quick)
    L = ["The ghost state machine in port form (tools/core_ghost.py) against the ROM routines on the concrete 6502 (tools/check_ghost.py, OV-67): zero page (except the scratch $2A, SrcPtr, DstPtr, $A5), maze, status rows, colour shadows and the RANDOM reads compared after every call", ""]
    for name, what, n, bad, used, trans in rows:
        L.append("%s: %s: %d calls: %d differences (RANDOM read 0 / 1 / 2 times: %d / %d / %d)" % (name, what, n, len(bad), used[0], used[1], used[2]))
        for b in bad[:3]:
            L.append("  %s" % (b,))
        if name == "ghost_behaviour":
            keys = sorted(trans)
            L.append("  state changes reached (before -> after, the number of calls): " + ", ".join("$%02X>$%02X:%d" % (a, b, trans[(a, b)]) for a, b in keys if a != b))
            L.append("  states left as they were: %d calls over %d states" % (sum(v for (a, b), v in trans.items() if a == b), len({a for (a, b) in trans if a == b})))
    return L, rows


def main():
    L, rows = report("--quick" in sys.argv)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if any(r[3] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
