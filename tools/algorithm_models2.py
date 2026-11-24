"""OV-58: executable models of more algorithms of the Pac-Man ROM, compared with the ROM code run instruction by instruction (tools/cpu6502.py).

Same method as tools/algorithm_models.py, but the comparison is stricter: each model works on a COPY OF THE WHOLE MEMORY (a bytearray) and the real routine is run on another copy; afterwards
RAM $0000-$00FF and $0200-$9FFF (not the stack page) and the hardware page $D000-$D7FF (the POKEY / GTIA writes land in the array) must be byte-for-byte equal, so a side effect the model does not know about is a difference.
The random state is made so that every branch of the routine is reached (random zero page, positions on the lattice rows, every ghost state).

  sight_test            GhostSeesPacMan $BA19 against tools/sight_model.py (A12)
  force_chase           ForceChase $B616 (A11)
  chase_timer_siren     ChaseTimerSirenSight $B5C7: the 8-jiffy chase timer, the late-board thresholds, the siren step, the sight test of ghosts in patrol (A11)
  frightened_sound      FrightenedSound $AFD7: the two-tone sweep state machine on POKEY channel 2 (A14, A22)
  frightened_tick       FrightenedTick $AF54, the frightened phase path (the siren path of phase 0 is not modelled): countdown, flashing, the end of the period for every Level (A14)
  eat_dot               EatDotAtPacMan $B33A: dot, cleared cell, the dot count, the board-complete flag (A06)
  power_pellet          PowerPelletCheck $B39F + PowerPelletEaten $B3DE: the four squares, PelletFlags, 50 points, the frighten start, the reversal (A06, A14)

Usage: python -I tools/algorithm_models2.py [--write analysis/evidence-algorithms2-summary.txt]
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import sight_model as SM  # noqa: E402

ROOT = A.ROOT
rd = A.rd
ENTITY_Y, ENTITY_X, ENTITY_DIR = A.ENTITY_Y, A.ENTITY_X, A.ENTITY_DIR
GHOST_STATE, CHASE_TIMER, SIREN_STEP = A.GHOST_STATE, 0xAD, 0x9C
RTCLOK2 = 0x14
DOTS_LO, DOTS_HI, PELLETS = 0x34, 0x36, 0x32
PCOLR0 = 0x02C0
PAC_Y, PAC_X = 0x89, 0x8E
REVERSE_DIR, FRIGHTEN_END = 0x07CF, 0x0672
E1, E2, E3, E4, F2 = 0xE1, 0xE2, 0xE3, 0xE4, 0xF2
PHASE, FLASH, COUNT = 0xFC, 0xFB, 0xFD
SCORE_ADD = 0x94
REGIONS = ((0x0000, 0x0100), (0x0200, 0xA000), (0xD000, 0xD800))        # the stack page is left out: below S it holds the dead return addresses of the JSRs (checked in 28-stack.md)


def diff(m, mem):
    """the addresses at which the machine m differs from the model memory"""
    out = []
    for lo, hi in REGIONS:
        if m.mem[lo:hi] != mem[lo:hi]:
            out += [a for a in range(lo, hi) if m.mem[a] != mem[a]]
    return out


def randomize(m, rng):
    for a in range(0x80):
        m.mem[a] = rng.randrange(256)
    m.mem[A.CURRENT_PLAYER] = rng.randrange(2)
    m.mem[A.LEVEL] = rng.randrange(20)
    m.mem[A.LEVEL + 1] = rng.randrange(20)


ALL_STATES = [0x00, 0x01, 0x02, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x81, 0x82, 0x88, 0x90, 0xA0, 0xC2, 0xC4, 0xFF, 0x04, 0x40]


def random_ghosts(m, rng):
    for g in range(4):
        m.mem[GHOST_STATE + g] = rng.choice(ALL_STATES)
        m.mem[ENTITY_DIR + g] = rng.choice([1, 2, 4, 8])


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_force_chase(mem, x):
    for i in range(x, -1, -1):
        if mem[GHOST_STATE + i] in (0x08, 0x10, 0x20):
            mem[GHOST_STATE + i] = 0x02
    mem[CHASE_TIMER] = 0xFF


def model_sight(mem, g):
    """GhostSeesPacMan for ghost g: state := 2 and ChaseTimer := $A0 when the ghost sees Pac-Man"""
    if SM.sees(g, mem[ENTITY_X + g], mem[ENTITY_Y + g], mem[ENTITY_DIR + g], mem[PAC_X], mem[PAC_Y], mem[RTCLOK2]):
        mem[GHOST_STATE + g] = 0x02
        mem[CHASE_TIMER] = 0xA0


def lattice_position(rng):
    rows = [rd(A.JUNCTION_Y + i) for i in range(10)]
    cols = [rd(A.JUNCTION_X + i) for i in range(10)]
    if rng.random() < 0.8:
        return rng.choice(cols if rng.random() < 0.5 else [rng.randrange(256)]), rng.choice(rows)
    return rng.randrange(256), rng.randrange(256)


def check_sight_test(n=20000, seed=60):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, hits = [], 0
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        g = rng.randrange(4)
        gx, gy = lattice_position(rng)
        px, py = lattice_position(rng)
        if rng.random() < 0.5:                                  # same row or same column, the interesting case
            if rng.random() < 0.5:
                py = gy
            else:
                px = gx
        m.mem[ENTITY_X + g], m.mem[ENTITY_Y + g] = gx, gy
        m.mem[PAC_X], m.mem[PAC_Y] = px, py
        m.mem[ENTITY_DIR + g] = rng.choice([1, 2, 4, 8])
        m.mem[GHOST_STATE + g] = rng.choice([0x08, 0x10])
        m.mem[RTCLOK2] = rng.randrange(256)
        mem = bytearray(m.mem)
        m.call(0xBA19, x=g)
        model_sight(mem, g)
        d = diff(m, mem)
        hits += mem[GHOST_STATE + g] == 0x02
        if d:
            bad.append((g, gx, gy, px, py, [hex(a) for a in d[:4]]))
    return n, bad, hits


def check_sight_exhaustive(rows=(0, 1, 4, 7), cols=(0, 2, 6, 9)):
    """every ghost position against every Pac-Man position on four lattice rows and four lattice columns (both directions), against the model: the scans of the sight lists in full"""
    base = A.started_machine()
    m = A.fresh(base)
    bad, n, sightings = [], 0, 0
    ys = [rd(A.JUNCTION_Y + i) for i in range(10)]
    xs = [rd(A.JUNCTION_X + i) for i in range(10)]
    cases = [("row", ys[r], None) for r in rows] + [("col", None, xs[c]) for c in cols]
    for kind, row, col in cases:
        for a in range(256):
            for b in range(256):
                if kind == "row":
                    gx, px, gy, py = a, b, row, row
                    d = 8 if gx < px else 4
                else:
                    gy, py, gx, px = a, b, col, col
                    d = 2 if gy < py else 1
                m.mem[ENTITY_X], m.mem[ENTITY_Y], m.mem[ENTITY_DIR] = gx, gy, d
                m.mem[PAC_X], m.mem[PAC_Y] = px, py
                m.mem[GHOST_STATE] = 0x08
                m.mem[CHASE_TIMER] = 0
                m.mem[RTCLOK2] = 0
                m.call(0xBA19, x=0)
                want = SM.sees(0, gx, gy, d, px, py, 0)
                got = m.mem[GHOST_STATE] == 0x02 and m.mem[CHASE_TIMER] == 0xA0
                n += 1
                sightings += want
                if got != want:
                    bad.append((kind, gx, gy, px, py, d))
    return n, bad, sightings


def check_force_chase(n=4000, seed=61):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        random_ghosts(m, rng)
        x = rng.randrange(4)
        mem = bytearray(m.mem)
        m.call(0xB616, x=x)
        model_force_chase(mem, x)
        d = diff(m, mem)
        if d:
            bad.append((x, [hex(a) for a in d[:4]]))
    return n, bad


def model_chase_timer_siren(mem):
    if mem[RTCLOK2] & 7 == 0 and mem[CHASE_TIMER] != 0:
        mem[CHASE_TIMER] = (mem[CHASE_TIMER] - 1) & 0xFF
    p = mem[A.CURRENT_PLAYER]
    hi, lo = mem[DOTS_HI + p], mem[DOTS_LO + p]
    if hi != 0 or lo >= 0xF0:
        model_force_chase(mem, 3)
        step = 5
    elif lo >= 0xE0:
        model_force_chase(mem, 2)
        step = 4
    elif lo >= 0xB0:
        step = 3
    else:
        step = 2
    mem[SIREN_STEP] = step
    for g in range(3, -1, -1):
        if mem[GHOST_STATE + g] in (0x08, 0x10):
            model_sight(mem, g)


def check_chase_timer_siren(n=20000, seed=62):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, forced = [], [0, 0, 0]
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        for g in range(4):
            m.mem[GHOST_STATE + g] = rng.choice([0x08, 0x10, 0x20, 0x02, 0x01, 0x00, 0x42, 0x82])
            m.mem[ENTITY_X + g], m.mem[ENTITY_Y + g] = lattice_position(rng)
        m.mem[PAC_X], m.mem[PAC_Y] = lattice_position(rng)
        if rng.random() < 0.6:
            g = rng.randrange(4)
            m.mem[ENTITY_Y + g] = m.mem[PAC_Y]
        for p in range(2):
            m.mem[DOTS_HI + p] = rng.choice([0, 0, 0, 1])
            m.mem[DOTS_LO + p] = rng.choice([rng.randrange(256), 0xAF, 0xB0, 0xDF, 0xE0, 0xEF, 0xF0, 0xFF, 0x00])
        m.mem[RTCLOK2] = rng.choice([rng.randrange(256), 0, 8, 0x80, 0x88])
        m.mem[CHASE_TIMER] = rng.choice([0, 1, rng.randrange(256)])
        mem = bytearray(m.mem)
        m.call(0xB5C7)
        model_chase_timer_siren(mem)
        p = mem[A.CURRENT_PLAYER]
        hi, lo = mem[DOTS_HI + p], mem[DOTS_LO + p]
        forced[0 if hi == 0 and lo < 0xE0 else 1 if hi == 0 and lo < 0xF0 else 2] += 1
        d = diff(m, mem)
        if d:
            bad.append(([hex(a) for a in d[:4]],))
    return n, bad, forced


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_frightened_sound(mem):
    if mem[E4] == 0:
        mem[E3], mem[E2], mem[E4], mem[E1] = 5, 2, mem[E4] + 1, 0x90
    plus = None                                              # the value A takes on the way to $B01F, or None for $B01A
    if mem[E2] == 1:
        if mem[E1] == 0x90:
            if mem[E3] == 3:
                mem[E3] = 5
            mem[E3] = (mem[E3] - 1) & 0xFF
            mem[E2] = 2
        else:
            plus = (mem[E1] + 0x10) & 0xFF
    elif mem[E1] == 0x40:
        mem[E2] = 1
        plus = (mem[E1] + 0x10) & 0xFF
    a = plus if plus else (mem[E1] - 0x10) & 0xFF            # an addition that gives 0 falls into the subtraction ($B01A)
    mem[E1] = a
    mem[0xD202] = a
    mem[0xD203] = mem[E3] | 0xA0


def check_frightened_sound(n=12000, seed=63):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for i in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        m.mem[E4] = rng.choice([0, 1, 1])
        m.mem[E2] = rng.choice([0, 1, 2, 1])
        m.mem[E1] = rng.choice([0x90, 0x40, 0xF0, 0x80, 0x50, 0x00, 0x10, rng.randrange(256)])
        m.mem[E3] = rng.choice([3, 4, 5, 2, 1, rng.randrange(256)])
        mem = bytearray(m.mem)
        m.call(0xAFD7)
        model_frightened_sound(mem)
        d = diff(m, mem)
        if d:
            bad.append((hex(mem[E1]), [hex(a) for a in d[:4]]))
    # the whole sweep from the start: 400 frames in a row, the model and the ROM state must stay together
    m = A.fresh(base)
    for a in (E1, E2, E3, E4):
        m.mem[a] = 0
    mem = bytearray(m.mem)
    for frame in range(400):
        m.call(0xAFD7)
        model_frightened_sound(mem)
        if diff(m, mem):
            bad.append(("sweep", frame))
            break
    return n + 400, bad


def colour_flash(mem):
    y = 0x84 if mem[PHASE] & 1 else 0x0C
    for g in range(3, -1, -1):
        if mem[GHOST_STATE + g] & 0x80:
            mem[PCOLR0 + g] = y


def model_frightened_tick(mem):
    ph = mem[PHASE]
    if ph == 0:
        return                                               # F2 != 0 is forced by the test (the siren path of phase 0 is not modelled)
    if mem[F2] == 0:
        model_frightened_sound(mem)
    if mem[COUNT] != 0:
        mem[COUNT] -= 1
        colour_flash(mem)
        return
    lv = mem[A.LEVEL + mem[A.CURRENT_PLAYER]]
    if mem[FRIGHTEN_END + lv] == ph:
        for g in range(3, -1, -1):
            if mem[GHOST_STATE + g] & 0x80:
                mem[PCOLR0 + g] = rd(0xBBE2 + g)
        for g in range(3, -1, -1):
            s = mem[GHOST_STATE + g]
            if s & 0x80:
                if s == 0x80:
                    mem[GHOST_STATE + g] = 0
                elif s & 0xBB:
                    mem[GHOST_STATE + g] = 0x20
        mem[PHASE] = mem[FLASH] = mem[E4] = 0
        mem[CHASE_TIMER] = 0xA0
        return
    if mem[FLASH] == 0:
        mem[PHASE] = (mem[PHASE] + 1) & 0xFF
        mem[FLASH] = 0x18
    mem[FLASH] = (mem[FLASH] - 1) & 0xFF
    colour_flash(mem)


def check_frightened_tick(n=20000, seed=64):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, ended = [], 0
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        random_ghosts(m, rng)
        p = m.mem[A.CURRENT_PLAYER]
        lv = m.mem[A.LEVEL + p]
        end = m.mem[FRIGHTEN_END + lv]
        m.mem[PHASE] = rng.choice([0, 1, 2, end, end, max(end - 1, 0), rng.randrange(256)])
        m.mem[COUNT] = rng.choice([0, 0, 0, 1, rng.randrange(256)])
        m.mem[FLASH] = rng.choice([0, 1, 0x18, rng.randrange(256)])
        m.mem[F2] = rng.choice([0, 0, 5]) if m.mem[PHASE] else rng.randrange(1, 256)
        m.mem[E4] = rng.choice([0, 1])
        m.mem[E2] = rng.choice([1, 2])
        m.mem[E1] = rng.choice([0x90, 0x40, 0x50, rng.randrange(256)])
        m.mem[E3] = rng.choice([3, 4, 5])
        ph0 = m.mem[PHASE]
        mem = bytearray(m.mem)
        m.call(0xAF54)
        model_frightened_tick(mem)
        ended += ph0 != 0 and mem[PHASE] == 0
        d = diff(m, mem)
        if d:
            bad.append((hex(m.mem[PHASE]), [hex(a) for a in d[:4]]))
    return n, bad, ended


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
SCORE_CELLS = (0x202A, 0x2047)


def model_add_score(mem):
    """AddToScore ($B423): the cells, the final carry in $9A, the cleared amount, the extra life at 10,000 (one more life, DrawLives) and the value left in A, which is returned"""
    p = mem[A.CURRENT_PLAYER]
    base = SCORE_CELLS[p]
    cells = [mem[base + k] for k in range(6)]
    add = [mem[SCORE_ADD + k] for k in range(6)]
    flag, lives = mem[A.EXTRA_LIFE_FLAG + p], mem[A.LIVES + p]
    new, flag2, lives2 = A.model_add_to_score(cells, add, p, flag, lives)
    carry = 0
    for y in range(5, -1, -1):
        carry = 1 if (cells[y] & 0x0F) + carry + add[y] >= 10 else 0
    for k in range(6):
        mem[base + k] = new[k]
        mem[SCORE_ADD + k] = 0
    mem[0x9A] = carry
    if flag != 0:
        return flag                                           # `lda zp_2E,x / bne rts`
    if flag2 == 0:
        return 0                                              # the 10,000s cell is blank: A holds that 0
    mem[A.EXTRA_LIFE_FLAG + p] = flag2
    mem[A.LIVES + p] = lives2 & 0xFF
    draw_lives(mem)
    return lives2 & 0xFF                                      # DrawLives leaves the number of lives in A


def draw_lives(mem):
    n = mem[A.LIVES + mem[A.CURRENT_PLAYER]]
    y = 0x9B
    if n == 3:
        mem[0x0F78] = mem[0x0F76] = mem[0x0F74] = y
    elif n == 2:
        mem[0x0F78] = 0
        mem[0x0F76] = mem[0x0F74] = y
    elif n == 1:
        mem[0x0F76] = mem[0x0F78] = 0
        mem[0x0F74] = y
    else:
        mem[0x0F74] = mem[0x0F76] = mem[0x0F78] = 0


def count_dot(mem):
    p = mem[A.CURRENT_PLAYER]
    mem[DOTS_LO + p] = (mem[DOTS_LO + p] + 1) & 0xFF
    if mem[DOTS_LO + p] == 0:
        mem[DOTS_HI + p] = (mem[DOTS_HI + p] + 1) & 0xFF
    if mem[DOTS_HI + p] != 0 and mem[DOTS_LO + p] == 4:
        mem[0x26] = 1


def model_eat_dot(mem):
    if mem[0x82] or mem[0xA6]:
        return
    if mem[PAC_X] == mem[0x84] and mem[PAC_Y] == mem[0x83]:
        return
    mem[0x83], mem[0x84] = mem[PAC_Y], mem[PAC_X]
    ptr = mem[0x80] | mem[0x81] << 8
    v = mem[ptr]
    if v == 2:
        mem[ptr] = 0
        return
    if v != 1:
        return
    mem[SCORE_ADD + 4] = 1
    model_add_score(mem)
    mem[0xF4] = mem[0xA9] = 1
    mem[0xF5] = 0
    mem[0xF6] = 1 if mem[0xF6] == 0 else 0
    mem[ptr] = 0
    count_dot(mem)


def random_scores(m, rng):
    for p in range(2):
        b = SCORE_CELLS[p]
        digits = [int(c) for c in "%06d" % rng.randrange(0, 90000)]
        for k, d in enumerate(digits):
            m.mem[b + k] = 0 if (all(x == 0 for x in digits[:k]) and d == 0 and k < 5) else 0x10 | d
    for k in range(6):
        m.mem[SCORE_ADD + k] = 0
    m.mem[A.EXTRA_LIFE_FLAG] = m.mem[A.EXTRA_LIFE_FLAG + 1] = 1          # the extra life draws on the screen: out of scope here (check_add_to_score covers it)


def check_eat_dot(n=12000, seed=65):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, acted = [], 0
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        random_scores(m, rng)
        ptr = 0x0800 + rng.randrange(920)
        m.mem[0x80], m.mem[0x81] = ptr & 0xFF, ptr >> 8
        m.mem[ptr] = rng.choice([0, 1, 1, 1, 2, 3, 0x80])
        m.mem[0x82] = rng.choice([0, 0, 0, 0, 1])
        m.mem[0xA6] = rng.choice([0, 0, 0, 0, 1])
        m.mem[PAC_X], m.mem[PAC_Y] = rng.randrange(256), rng.randrange(256)
        m.mem[0x84], m.mem[0x83] = (m.mem[PAC_X], m.mem[PAC_Y]) if rng.random() < 0.3 else (rng.randrange(256), rng.randrange(256))
        m.mem[0xF6] = rng.randrange(2)
        for p in range(2):
            m.mem[DOTS_HI + p] = rng.choice([0, 0, 1])
            m.mem[DOTS_LO + p] = rng.choice([rng.randrange(256), 3, 255, 4])
        v0 = m.mem[ptr]
        mem = bytearray(m.mem)
        m.call(0xB33A)
        model_eat_dot(mem)
        acted += v0 == 1 and not (m.mem[0x82] or m.mem[0xA6]) and bool(mem[0xF4] == 1)
        d = diff(m, mem)
        if d:
            bad.append(([hex(a) for a in d[:4]],))
    return n, bad, acted


PELLET_SQUARES = ((0x3C, 0x3A), (0x3C, 0xBE), (0xA4, 0x3A), (0xA4, 0xBE))        # (PacY, PacX) of the four power-pellet squares, bit 0 .. 3 of PelletFlags


def model_power_pellet(mem):
    p = mem[A.CURRENT_PLAYER]
    flags = mem[PELLETS + p]
    mem[0x2A] = flags
    bit = None
    for i, (y, x) in enumerate(PELLET_SQUARES):
        if flags & (1 << i) and mem[PAC_Y] == y and mem[PAC_X] == x:
            bit = 1 << i
            break
    if bit is None:
        return False
    mem[PELLETS + p] = (bit ^ 0x0F) & flags
    mem[SCORE_ADD + 4] = 5
    model_add_score(mem)
    mem[PHASE] = 1
    mem[0xE9] = 0xFF
    mem[COUNT] = rd(0xBBF8 + mem[A.LEVEL + p])
    for g in range(3, -1, -1):
        s = mem[GHOST_STATE + g]
        if s & 0x40:                                         # an eaten ghost (asl a / bmi) is left alone
            continue
        s |= 0x80
        mem[GHOST_STATE + g] = s
        if (s >> 2) & 1:                                     # after the three shifts the carry is bit 2 of the state: the ghosts in state 2 (chase) are not reversed
            continue
        if (s >> 3) & 0x3B == 0:                             # a plain house ghost ($80) is not reversed
            continue
        mem[ENTITY_DIR + g] = mem[REVERSE_DIR + mem[ENTITY_DIR + g]]
    count_dot(mem)
    return True


def check_power_pellet(n=15000, seed=66):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, eaten = [], 0
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        random_ghosts(m, rng)
        random_scores(m, rng)
        for p in range(2):
            m.mem[PELLETS + p] = rng.choice([0x0F, 0x0F, rng.randrange(16), rng.randrange(256)])
            m.mem[DOTS_HI + p] = rng.choice([0, 0, 1])
            m.mem[DOTS_LO + p] = rng.choice([rng.randrange(256), 3, 255])
        y, x = rng.choice(PELLET_SQUARES) if rng.random() < 0.7 else (rng.randrange(256), rng.randrange(256))
        m.mem[PAC_Y], m.mem[PAC_X] = y, x
        mem = bytearray(m.mem)
        m.call(0xB39F)
        eaten += model_power_pellet(mem)
        d = diff(m, mem)
        if d:
            bad.append((y, x, [hex(a) for a in d[:4]]))
    return n, bad, eaten


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def report():
    L = []
    P = L.append
    P("More algorithm models against the ROM executed in tools/cpu6502.py (tools/algorithm_models2.py, OV-58); whole memory (zero page, $0200-$9FFF, $D000-$D7FF) compared after every call")
    P("")
    n, bad, hits = check_sight_test()
    P("sight_test: %d calls of GhostSeesPacMan (ghost and Pac-Man on lattice rows and columns, 4 directions, every RTCLOK2 value): %d differences (%d sightings)" % (n, len(bad), hits))
    R = [("sight_test", bad)]
    n, bad, sg = check_sight_exhaustive()
    P("sight_exhaustive: %d calls (every ghost x every Pac-Man position on four lattice rows and four lattice columns, the direction facing him): %d differences (%d sightings)" % (n, len(bad), sg))
    R.append(("sight_exhaustive", bad))
    n, bad = check_force_chase()
    P("force_chase: %d calls (every start index, 19 ghost states): %d differences" % (n, len(bad)))
    R.append(("force_chase", bad))
    n, bad, f = check_chase_timer_siren()
    P("chase_timer_siren: %d calls (dots eaten around every threshold $B0 / $E0 / $F0 / $0100, RTCLOK2 multiples of 8, ChaseTimer 0 / 1 / any): %d differences (%d below $E0, %d in $E0-$EF, %d from $F0)" % (n, len(bad), f[0], f[1], f[2]))
    R.append(("chase_timer_siren", bad))
    n, bad = check_frightened_sound()
    P("frightened_sound: %d calls (random state of the sweep, and 400 frames in a row from the start): %d differences" % (n, len(bad)))
    R.append(("frightened_sound", bad))
    n, bad, e = check_frightened_tick()
    P("frightened_tick: %d calls (phase 0 / 1 / 2 / the end phase of the Level / any, countdown, flash timer, Level 0-19, 19 ghost states): %d differences (the period ended in %d)" % (n, len(bad), e))
    R.append(("frightened_tick", bad))
    n, bad, d = check_eat_dot()
    P("eat_dot: %d calls (cell values 0 / 1 / 2 / 3 / $80, frozen and blocked flags, same-cell repeat, dot counts across 255 -> 256 and 260): %d differences (%d with a dot in the cell and not frozen)" % (n, len(bad), d))
    R.append(("eat_dot", bad))
    n, bad, e = check_power_pellet()
    P("power_pellet: %d calls (the four squares and random squares, every PelletFlags, 19 ghost states): %d differences (%d pellets eaten)" % (n, len(bad), e))
    R.append(("power_pellet", bad))
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
