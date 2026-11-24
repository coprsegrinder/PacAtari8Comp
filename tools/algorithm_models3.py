"""OV-58, third set: the ghost house, the eaten ghost's return and the drawing of an entity, run against models (see tools/algorithm_models2.py for the method: the whole memory is compared after every call).

  step_and_draw         StepAndDrawEntity $B902: one step in a direction and the 16-byte shape copied to the player page (A21, A13)
  house_bob             HouseBobStep $B7D6: the bobbing between y $70 and $78 (A13)
  house_leave           HouseLeaveStep $B738, HouseLeaveGhost2 $B76D, HouseLeaveGhost3 $B777: the way out of the house (A13)
  house_enter           HouseEnterStep $B781: the way in of an eaten ghost (A16)
  house_waiting_tick    HouseWaitingTick $B7A5: the loop over ghosts 1-3 (A13)
  eyes_returning_sound  EyesReturningSound $B02C: the sweep while eyes are on their way (A16, A22)
  eyes_and_house        EyesAndHousePerFrame $B69E: the per-frame loop of eaten ghosts and ghosts in the house (A16)

A callee that is already proved equal to a model in tools/algorithm_models.py (JunctionLookup, SteerToTarget) is run as the real ROM code inside the model of its caller (`run_verified`); the model of the caller is what is under test.
Usage: python -I tools/algorithm_models3.py [--write analysis/evidence-algorithms3-summary.txt]
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT
rd = A.rd
diff, randomize = M2.diff, M2.randomize
ENTITY_Y, ENTITY_X, ENTITY_DIR, GHOST_STATE = A.ENTITY_Y, A.ENTITY_X, A.ENTITY_DIR, A.GHOST_STATE
TARGET_X, TARGET_Y = A.TARGET_X, A.TARGET_Y
GHOST_TIMER, START_ROUTE_STEP = A.GHOST_TIMER, 0xD2
LEG_PHASE, ZP_AE = 0xAF, 0xAE
F2, F3, E5, E8 = 0xF2, 0xF3, 0xE5, 0xE8
PCOLR0 = 0x02C0
SHAPES = 0xBAC0
CHASE_TIMER = 0xAD
ONE_MACHINE = None


def run_verified(mem, addr, x, rnd):
    """run a routine that is already proved equal to its model, on the memory mem (changed in place); returns the carry and the RANDOM values used"""
    m = C.Machine(A.ROM, list(rnd))
    m.mem[:] = mem
    m.mem[0xA000:0xC000] = A.ROM
    m.call(addr, x=x)
    mem[:] = m.mem
    mem[0xA000:0xC000] = A.ROM
    return m.c, len(m.random_reads)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_step_and_draw(mem, x, a):
    if a == 1:
        if mem[ZP_AE] == 0:
            mem[ENTITY_Y + x] = (mem[ENTITY_Y + x] - 2) & 0xFF
        off = 0x00
    elif a == 2:
        if mem[ZP_AE] == 0:
            mem[ENTITY_Y + x] = (mem[ENTITY_Y + x] + 2) & 0xFF
        off = 0x0A
    elif a == 4:
        if mem[ZP_AE] == 0:
            mem[ENTITY_X + x] = (mem[ENTITY_X + x] - 1) & 0xFF
        off = 0x14
    elif a == 8:
        if mem[ZP_AE] == 0:
            mem[ENTITY_X + x] = (mem[ENTITY_X + x] + 1) & 0xFF
        off = 0x1E
    else:
        return
    s = mem[GHOST_STATE + x]
    if s & 0x80:
        off = 0x28                                            # frightened shape (the two blue pictures)
    if s & 0x40:                                              # eaten: the eyes, no leg phase
        off, flag = 0x32, 0x00
    else:
        flag = 0xAA if mem[LEG_PHASE] else 0x54
    mem[0x041C] = flag
    for k in range(10):
        mem[0x0412 + k] = rd(SHAPES + off + k)
    mem[0x3C], mem[0x3D] = 0x10, 0x04
    mem[0xD000 + x] = mem[ENTITY_X + x]
    mem[0x3E] = mem[ENTITY_Y + x]
    mem[0x3F] = (0x24 + x) & 0xFF
    dst = (mem[0x3F] << 8) | mem[0x3E]
    for k in range(16):
        mem[dst + k] = mem[0x0410 + k]


def setup_entities(m, rng):
    for g in range(5):
        m.mem[ENTITY_X + g] = rng.choice([0x7C, 0x70, 0x88, 0x76, 0x82, rng.randrange(256)])
        m.mem[ENTITY_Y + g] = rng.choice([0x64, 0x70, 0x74, 0x78, 0x72, rng.randrange(256)])
        m.mem[ENTITY_DIR + g] = rng.choice([1, 2, 4, 8, 4, 8])
    m.mem[ZP_AE] = rng.choice([0, 0, 0, 1, 7])
    m.mem[LEG_PHASE] = rng.randrange(2)


def check_step_and_draw(n=8000, seed=70):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        setup_entities(m, rng)
        random_state(m, rng)
        x = rng.randrange(5) if rng.random() < 0.3 else rng.randrange(4)
        a = rng.choice([1, 2, 4, 8, 8, 0, 3, 0x10])
        mem = bytearray(m.mem)
        m.call(0xB902, a=a, x=x)
        model_step_and_draw(mem, x, a)
        d = diff(m, mem)
        if d:
            bad.append((x, a, [hex(k) for k in d[:4]]))
    return n, bad


STATES = [0x00, 0x01, 0x02, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x82, 0x88, 0xA0, 0xC2, 0xC4, 0x84, 0x40, 0x04]


def random_state(m, rng):
    for g in range(4):
        m.mem[GHOST_STATE + g] = rng.choice(STATES)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_house_bob(mem, x):
    d = mem[ENTITY_DIR + x]
    if d == 1:
        if mem[ENTITY_Y + x] == 0x70:
            mem[ENTITY_DIR + x] = 2
    elif mem[ENTITY_Y + x] == 0x78:
        mem[ENTITY_DIR + x] = 1
    model_step_and_draw(mem, x, mem[ENTITY_DIR + x])


def check_house_bob(n=4000, seed=71):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        setup_entities(m, rng)
        random_state(m, rng)
        x = rng.randrange(1, 4)
        m.mem[ENTITY_DIR + x] = rng.choice([1, 2, 4, 8, 0])
        mem = bytearray(m.mem)
        m.call(0xB7D6, x=x)
        model_house_bob(mem, x)
        d = diff(m, mem)
        if d:
            bad.append((x, [hex(k) for k in d[:4]]))
    return n, bad


def model_house_leave_step(mem, x):
    if mem[ENTITY_Y + x] != 0x64:
        mem[ENTITY_DIR + x] = 1
        model_step_and_draw(mem, x, 1)
        return
    s = mem[GHOST_STATE + x]
    if s == 0:
        a, y = 1, 4
    else:
        a = (s & 0x80) | 2
        if a & 0x80:
            mem[CHASE_TIMER] = a                              # stores the state value in ChaseTimer (a quirk of the code, $B74C)
            y = 8
        else:
            y = 4
    mem[ENTITY_DIR + x] = y
    mem[GHOST_STATE + x] = a


def model_house_leave(mem, x):
    """x = 2: HouseLeaveGhost2, x = 3: HouseLeaveGhost3, otherwise HouseLeaveStep"""
    if x in (2, 3):
        if mem[ENTITY_X + x] != 0x7C:
            d = 8 if x == 2 else 4
            mem[ENTITY_DIR + x] = d
            model_step_and_draw(mem, x, d)
            return
    model_house_leave_step(mem, x)


def check_house_leave(n=9000, seed=72):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    entry = {1: 0xB738, 2: 0xB76D, 3: 0xB777}
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        setup_entities(m, rng)
        random_state(m, rng)
        x = rng.randrange(1, 4)
        mem = bytearray(m.mem)
        m.call(entry[x], x=x)
        model_house_leave(mem, x)
        d = diff(m, mem)
        if d:
            bad.append((x, [hex(k) for k in d[:4]]))
    return n, bad


def model_house_enter(mem, x):
    if mem[ENTITY_Y + x] != 0x74:
        mem[ENTITY_DIR + x] = 2
        model_step_and_draw(mem, x, 2)
        return
    if x == 2 and mem[ENTITY_X + x] != 0x70:
        mem[ENTITY_DIR + x] = 4
        model_step_and_draw(mem, x, 4)
        return
    if x == 3 and mem[ENTITY_X + x] != 0x88:
        mem[ENTITY_DIR + x] = 8
        model_step_and_draw(mem, x, 8)
        return
    mem[GHOST_STATE + x] &= 0x0F                              # home again: bits 7 and 6 removed, the normal colour
    mem[PCOLR0 + x] = rd(0xBBE2 + x)


def check_house_enter(n=9000, seed=73):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        setup_entities(m, rng)
        random_state(m, rng)
        x = rng.randrange(4)
        mem = bytearray(m.mem)
        m.call(0xB781, x=x)
        model_house_enter(mem, x)
        d = diff(m, mem)
        if d:
            bad.append((x, [hex(k) for k in d[:4]]))
    return n, bad


def model_house_waiting_tick(mem):
    for x in (1, 2, 3):
        if mem[GHOST_STATE + x] & 0x7F:
            continue
        if mem[GHOST_TIMER + x] != 0:
            mem[GHOST_TIMER + x] -= 1
            model_house_bob(mem, x)
        else:
            model_house_leave(mem, x)


def check_house_waiting_tick(n=9000, seed=74):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        setup_entities(m, rng)
        for g in range(4):
            m.mem[GHOST_STATE + g] = rng.choice([0x00, 0x00, 0x80, 0x01, 0x02, 0x82, 0x08, 0x44])
            m.mem[GHOST_TIMER + g] = rng.choice([0, 0, 1, 5, rng.randrange(256)])
        mem = bytearray(m.mem)
        m.call(0xB7A5)
        model_house_waiting_tick(mem)
        d = diff(m, mem)
        if d:
            bad.append(([hex(k) for k in d[:4]],))
    return n, bad


def model_eyes_sound(mem):
    if mem[F3] == 0:
        mem[F3] = 0x0C
    elif mem[F3] == 0x17:
        mem[F3] = 0x0C
    mem[F3] = (mem[F3] + 1) & 0xFF
    mem[0xD202] = mem[F3]
    mem[0xD203] = 0xA4


def check_eyes_sound(n=3000, seed=75):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for i in range(n):
        m = A.fresh(base)
        m.mem[F3] = rng.choice([0, 0x0C, 0x16, 0x17, 0x18, rng.randrange(256)])
        mem = bytearray(m.mem)
        m.call(0xB02C)
        model_eyes_sound(mem)
        d = diff(m, mem)
        if d:
            bad.append((i, [hex(k) for k in d[:4]]))
    m = A.fresh(base)                                         # 200 frames in a row
    mem = bytearray(m.mem)
    for f in range(200):
        m.call(0xB02C)
        model_eyes_sound(mem)
        if diff(m, mem):
            bad.append(("sweep", f))
            break
    return n + 200, bad


def model_eyes_and_house(mem, rnd):
    """returns the number of RANDOM values used"""
    used = 0
    mem[F2] = 0
    for x in (3, 2, 1, 0):
        s = mem[GHOST_STATE + x]
        if s == 0x44 or not (s & 0x40) or x == mem[E8]:       # not an eaten ghost on its way (bit 6 clear), or at the door, or the one paused
            continue
        mem[F2] += 1
        px, py = mem[ENTITY_X + x], mem[ENTITY_Y + x]
        if px == 0x7C and py == 0x64:
            if mem[ENTITY_DIR + x] == 1:
                mem[ENTITY_DIR + x] = 4
                if mem[ENTITY_Y + x] == 0:                    # (the code reloads Y and branches on it: only y = 0 falls through)
                    mem[GHOST_STATE + x] = 0x44
                    mem[START_ROUTE_STEP + x] = 0xFF
                    continue
            else:
                mem[GHOST_STATE + x] = 0x44
                mem[START_ROUTE_STEP + x] = 0xFF
                continue
        carry, k = run_verified(mem, 0xB48E, x, rnd[used:])
        used += k
        if carry:
            mem[TARGET_X + x], mem[TARGET_Y + x] = 0x7C, 0x64
            carry2, k = run_verified(mem, 0xB999, x, rnd[used:])
            used += k
        model_step_and_draw(mem, x, mem[ENTITY_DIR + x])
    if mem[F2] == 0:
        mem[F3] = 0
    elif mem[E5] == 0:
        model_eyes_sound(mem)
    for x in (3, 2, 1, 0):
        s = mem[GHOST_STATE + x]
        if not ((s >> 2) & 1):                               # the carry of the third lsr: bit 2 of the state (eyes at the door $44, or frightened-in-house)
            continue
        if s & 0x40:
            model_house_enter(mem, x)
        elif mem[0x14] & 3 == 0:
            model_house_leave(mem, x)
    return used


def check_eyes_and_house(n=6000, seed=76):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, hits = [], [0, 0]
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        setup_entities(m, rng)
        for g in range(4):
            m.mem[GHOST_STATE + g] = rng.choice([0x42, 0x42, 0x44, 0x08, 0x00, 0x80, 0x01, 0x02, 0x4A, 0x48, 0xC2, 0x40])
            m.mem[ENTITY_X + g] = rng.choice([0x7C, 0x7C, 0x70, 0x88, rng.randrange(256)])
            m.mem[ENTITY_Y + g] = rng.choice([0x64, 0x64, 0x74, 0x70, rng.randrange(256), 0x00])
            if rng.random() < 0.5:
                m.mem[ENTITY_X + g], m.mem[ENTITY_Y + g] = M2.lattice_position(rng)
        m.mem[E8] = rng.choice([0xFF, 0xFF, 0, 1, 2, 3])
        m.mem[E5] = rng.choice([0, 0, 1])
        m.mem[0x14] = rng.randrange(256)
        rnd = [rng.randrange(256), rng.randrange(256)]
        m.random = list(rnd)
        mem = bytearray(m.mem)
        m.call(0xB69E)
        used = model_eyes_and_house(mem, rnd)
        hits[0] += 1 if used else 0
        hits[1] += 1 if any(mem[GHOST_STATE + g] == 0x44 for g in range(4)) else 0
        d = diff(m, mem)
        if d or len(m.random_reads) != used:
            bad.append(([hex(k) for k in d[:4]], len(m.random_reads), used))
    return n, bad, hits


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def report():
    L = []
    P = L.append
    P("Third set of algorithm models against the ROM executed in tools/cpu6502.py (tools/algorithm_models3.py, OV-58); whole memory (zero page, $0200-$9FFF, $D000-$D7FF) compared after every call")
    P("")
    R = []
    n, bad = check_step_and_draw()
    P("step_and_draw: %d calls (4 directions and 4 invalid values, 5 entities, every ghost state, both leg phases, the step switch off and on): %d differences" % (n, len(bad)))
    R.append(("step_and_draw", bad))
    n, bad = check_house_bob()
    P("house_bob: %d calls (direction up / down / other, y at the two ends and elsewhere): %d differences" % (n, len(bad)))
    R.append(("house_bob", bad))
    n, bad = check_house_leave()
    P("house_leave: %d calls (ghosts 1, 2, 3 at and away from x $7C, y $64 and elsewhere, 17 states): %d differences" % (n, len(bad)))
    R.append(("house_leave", bad))
    n, bad = check_house_enter()
    P("house_enter: %d calls (ghosts 0-3 at y $74 and elsewhere, x $70 / $88 and elsewhere): %d differences" % (n, len(bad)))
    R.append(("house_enter", bad))
    n, bad = check_house_waiting_tick()
    P("house_waiting_tick: %d calls (states $00 / $80 waiting and others, timers 0 / 1 / any): %d differences" % (n, len(bad)))
    R.append(("house_waiting_tick", bad))
    n, bad = check_eyes_sound()
    P("eyes_returning_sound: %d calls (and 200 frames in a row): %d differences" % (n, len(bad)))
    R.append(("eyes_returning_sound", bad))
    n, bad, hits = check_eyes_and_house()
    P("eyes_and_house: %d calls (eaten ghosts at the door square and away, ghosts leaving and entering, the paused ghost, RANDOM and the steering through the real JunctionLookup / SteerToTarget): %d differences (%d with steering, %d reaching the door)" % (n, len(bad), hits[0], hits[1]))
    R.append(("eyes_and_house", bad))
    for name, b in R:
        for t in b[:3]:
            P("  %s: %s" % (name, t))
    return L, R


def main():
    L, R = report()
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
