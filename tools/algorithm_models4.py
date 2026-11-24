"""OV-58, fourth set: Pac-Man's step, the bonus item, eating a ghost and the pause after it (see tools/algorithm_models2.py for the method: the whole memory is compared after every call).

  move_pacman           MovePacMan $B179: joystick, wanted direction, cornering, one step, the sub-cell counters, MazePtr, the tunnel wrap, the chomp picture (A05)
  bonus_update          BonusItemUpdate $B62E: appearance at 80 / 160 dots, the time on the screen, the disappearance (A20)
  ghost_eaten           GhostEaten $A886: state $42, the pop-up picture, the points 200 / 400 / 800 / 1600 (A15)
  dot_sound_sweep       DotSoundSweep $B0BC: the six-step dot sound on channel 1 (A06, A22)
  ghost_eaten_pause     GhostEatenPause $B049: the falling sweep during the 34-frame pause and its end (A15, A22)

JunctionLookup, MovePacMan and EatDotAtPacMan, once proved equal to their models, are run as real ROM code inside the models of their callers (`run_verified`).
Usage: python -I tools/algorithm_models4.py [--write analysis/evidence-algorithms4-summary.txt]
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import algorithm_models3 as M3  # noqa: E402

ROOT = A.ROOT
rd = A.rd
diff, randomize, run_verified = M2.diff, M2.randomize, M3.run_verified
ENTITY_Y, ENTITY_X, GHOST_STATE = A.ENTITY_Y, A.ENTITY_X, A.GHOST_STATE
PAC_Y, PAC_X, PAC_DIR = 0x89, 0x8E, 0x93
PCOLR0, COLOR3, GPRIOR = 0x02C0, 0x02C7, 0x026F
SCORE_ADD = 0x94


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def inc16(mem, lo, d):
    v = (mem[lo] | mem[lo + 1] << 8) + d
    mem[lo], mem[lo + 1] = v & 0xFF, (v >> 8) & 0xFF


def model_pacman_draw(mem, y, a):
    """the end of MovePacMan ($B2E9): picture y (index into PacShapePtrs) plus offset a copied to the player page $23 and the missiles"""
    ptr = rd(0xBB65 + y) | rd(0xBB65 + y + 1) << 8
    ptr = (ptr + a) & 0xFFFF
    for k in range(10):
        mem[0x0403 + k] = mem[ptr + k] if ptr < 0xA000 else rd(ptr + k)
    mem[0x3C], mem[0x3D] = 0x00, 0x04
    mem[0x3E], mem[0x3F] = mem[PAC_Y], 0x23
    px = mem[PAC_X]
    mem[0xD007] = px
    t = px + 2
    mem[0xD006] = t & 0xFF
    t = (t & 0xFF) + 2 + (t >> 8)
    mem[0xD005] = t & 0xFF
    t = (t & 0xFF) + 2 + (t >> 8)
    mem[0xD004] = t & 0xFF
    dst = (0x23 << 8) | mem[PAC_Y]
    for k in range(16):
        mem[dst + k] = mem[0x0400 + k]


def model_move_pacman(mem, rnd):
    if mem[0xAA] & 0x80:
        return 0
    c, used = run_verified(mem, 0xB48E, 4, rnd)                # JunctionLookup for Pac-Man (entity 4): the exits mask in $2A
    mask = mem[0x2A]
    ac, pdir = mem[0xAC], mem[PAC_DIR]
    if ac & mask:
        if ac != pdir:
            y = ac | pdir
            if (y & 3) and (y & 0x0C):
                mem[0xA8] = y                                   # a perpendicular turn: forces a step
        mem[PAC_DIR] = ac
    s = mem[0x0278 + mem[A.CURRENT_PLAYER]] ^ 0x0F
    if s != 0 and bin(s & 0x0F).count("1") != 2:
        mem[0x4D] = s
        mem[0xAC] = s
        if s & mask:
            mem[PAC_DIR] = s
    pdir = mem[PAC_DIR]
    paused = mem[0xA7] != 0
    if not (pdir & mask):
        y, a = {1: (6, 0x0A), 2: (8, 0x0A), 4: (4, 0x0A), 8: (2, 0x0A)}.get(pdir, (0, 0))
    else:
        if pdir == 1:
            if not paused:
                mem[PAC_Y] = (mem[PAC_Y] - 2) & 0xFF
                if mem[0xA6] == 0:
                    mem[0xA6] = 3
                else:
                    mem[0xA6] -= 1
                    if mem[0xA6] == 0 and mem[PAC_Y] != mem[0x83]:
                        inc16(mem, 0x80, -0x28)
            y = 6
        elif pdir == 2:
            if not paused:
                mem[PAC_Y] = (mem[PAC_Y] + 2) & 0xFF
                if mem[0xA6] == 3:
                    mem[0xA6] = 0
                    if mem[PAC_Y] != mem[0x83]:
                        inc16(mem, 0x80, 0x28)
                        if mem[0x81] == 0:                      # `bne` on the new high byte: a pointer that wraps to page 0 falls into the `inc` of the counter ($B238); never happens with a real MazePtr
                            mem[0xA6] += 1
                else:
                    mem[0xA6] += 1
            y = 8
        elif pdir == 8:
            if not paused:
                if mem[PAC_X] == 0xCA:
                    mem[PAC_X] = 0x2A
                    mem[0x80] = 0x8F
                mem[PAC_X] = (mem[PAC_X] + 1) & 0xFF
                if mem[0x82] == 3:
                    mem[0x82] = 0
                    if mem[PAC_X] != mem[0x84]:
                        inc16(mem, 0x80, 1)
                        if mem[0x80] == 0 and mem[0x81] == 0:   # the same fall-through into `inc $82` ($B26B)
                            mem[0x82] += 1
                else:
                    mem[0x82] += 1
            y = 2
        elif pdir == 4:
            if not paused:
                if mem[PAC_X] == 0x2A:
                    mem[PAC_X] = 0xCA
                    mem[0x80] = 0xB7
                mem[PAC_X] = (mem[PAC_X] - 1) & 0xFF
                if mem[0x82] == 0:
                    mem[0x82] = 3
                else:
                    mem[0x82] -= 1
                    if mem[0x82] == 0 and mem[PAC_X] != mem[0x84]:
                        inc16(mem, 0x80, -1)
            y = 4
        else:
            y, a = 0, 0
        if pdir in (1, 2, 4, 8):                                # the chomp picture: the mouth steps through PacMouthOffsets
            cp = mem[0xAB]
            if cp == 0:
                mem[0xAB] = 1
                y, a = 0, 0
            else:
                x = cp - 1
                a = rd(0xBB55 + x)
                if x == 2:
                    mem[0xAB] = 0
                else:
                    mem[0xAB] = (cp + 1) & 0xFF
        else:
            a = 0
    model_pacman_draw(mem, y, a)
    return used


def check_move_pacman(n=15000, seed=80):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, turns = [], 0
    for _ in range(n):
        m = A.fresh(base)
        for a in range(0x100):
            m.mem[a] = rng.randrange(256)
        m.mem[A.CURRENT_PLAYER] = rng.randrange(2)
        m.mem[0xAA] = rng.choice([0, 0, 0, 0x80, 0x7F])
        m.mem[PAC_X], m.mem[PAC_Y] = M2.lattice_position(rng) if rng.random() < 0.8 else (rng.choice([0x2A, 0xCA, 0x2B, 0xC9]), 0x74)
        m.mem[PAC_DIR] = rng.choice([1, 2, 4, 8, 4, 8, 0, 3, 5])
        m.mem[0xAC] = rng.choice([1, 2, 4, 8, 0, 3, 5])
        m.mem[0xA6] = rng.randrange(4)
        m.mem[0x82] = rng.randrange(4)
        m.mem[0xA7] = rng.choice([0, 0, 0, 1])
        m.mem[0xAB] = rng.choice([0, 1, 2, 3, 4, rng.randrange(256)])
        m.mem[0x84], m.mem[0x83] = (m.mem[PAC_X], m.mem[PAC_Y]) if rng.random() < 0.3 else (rng.randrange(256), rng.randrange(256))
        m.mem[0x80], m.mem[0x81] = rng.randrange(256), rng.choice([0x08, 0x09, 0x0A, 0x00, 0xFF])
        if rng.random() < 0.3:                               # the cell Pac-Man steps into is the one last tested for dots: the compares that are equal
            m.mem[0x83] = (m.mem[PAC_Y] + rng.choice([-2, 2])) & 0xFF
        if rng.random() < 0.3:
            m.mem[0x84] = (m.mem[PAC_X] + rng.choice([-1, 1])) & 0xFF
        if rng.random() < 0.05:
            m.mem[0x80], m.mem[0x81] = 0xFF, 0xFF            # MazePtr at the end of memory: the carries of `inc`
        m.mem[0x0278 + 0], m.mem[0x0278 + 1] = rng.choice([0x0F, 0x0E, 0x0D, 0x0B, 0x07, 0x0A, 0x05, 0x09, 0x06, 0x0C, 0x03, 0x00, 0xFF]), rng.choice([0x0F, 0x0E, 0x07])
        mem = bytearray(m.mem)
        m.call(0xB179)
        used = model_move_pacman(mem, [])
        turns += mem[0xA8] != 0
        d = diff(m, mem)
        if d:
            bad.append((hex(m.mem[PAC_DIR]), [hex(k) for k in d[:4]]))
    return n, bad, turns


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_bonus_update(mem):
    if mem[0xA1]:
        if mem[0xA2] == 0:
            mem[0xA1] = 0
            for k in range(5):
                mem[0x0DF1 + k] = 0
        else:
            mem[0xA2] -= 1
        return
    if mem[0x9F] == 0:
        p = mem[A.CURRENT_PLAYER]
        dots, t = mem[0x34 + p], mem[0x43 + p]
        if t == 0:
            fire = dots in (0x50, 0xA0)
        elif t == 1:
            fire = dots == 0xA0
        else:
            return
        if not fire:
            return
        mem[0x43 + p] = (t + 1) & 0xFF
        code = rd(0xBD26 + min(mem[A.LEVEL + p], 0x0C))
        mem[0x0DF3] = code
        mem[0x0DF4] = (code + 1) & 0xFF
        mem[0x9F], mem[0x9D], mem[0x9E] = 1, 0xC0, 0x02
        return
    if mem[0x9E] == 0 and mem[0x9D] == 0:
        mem[0x0DF3] = mem[0x0DF4] = 0
        mem[0x9F] = 0
        return
    mem[0x9D] = (mem[0x9D] - 1) & 0xFF
    if mem[0x9D] == 0:
        mem[0x9E] = (mem[0x9E] - 1) & 0xFF


def check_bonus_update(n=15000, seed=81):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, fired = [], 0
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        for a in (0xA1, 0xA2, 0x9F, 0x9D, 0x9E):
            m.mem[a] = rng.choice([0, 0, 1, 2, rng.randrange(256)])
        for p in range(2):
            m.mem[0x34 + p] = rng.choice([0x50, 0xA0, 0x4F, 0xA1, rng.randrange(256)])
            m.mem[0x43 + p] = rng.choice([0, 1, 2, 0, 1])
        for k in range(5):
            m.mem[0x0DF1 + k] = rng.randrange(256)
        mem = bytearray(m.mem)
        m.call(0xB62E)
        model_bonus_update(mem)
        fired += mem[0x9F] == 1 and m.mem[0x9D] == 0xC0
        d = diff(m, mem)
        if d:
            bad.append(([hex(k) for k in d[:4]],))
    return n, bad, fired


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_ghost_eaten(mem, x):
    mem[GHOST_STATE + x] = 0x42
    mem[0xE8] = x
    mem[0xE9] = (mem[0xE9] + 1) & 0xFF
    a = (mem[PAC_X] - 4) & 0xFF
    mem[0xD007] = a
    carry = 0
    for yy in (2, 1, 0):
        t = a + 2 + carry
        a, carry = t & 0xFF, t >> 8
        mem[0xD004 + yy] = a
    t = a + 2 + carry
    mem[0xD000 + x] = t & 0xFF
    mem[COLOR3] = 0xDC
    mem[PCOLR0 + x] = 0xDC
    py, ey = mem[PAC_Y], mem[ENTITY_Y + x]
    if py == ey:
        a = py
    elif py < ey:
        a = (py + 2) & 0xFF
    else:
        a = (py - 2) & 0xFF
    mem[0x38] = mem[0x3A] = a
    mem[0x39] = 0x23
    mem[0x3B] = (x + 0x23 + 1) & 0xFF
    g = mem[0xE9]
    idx = (g * 2) & 0xFF
    ptr = rd(0xBCD0 + idx) | rd(0xBCD0 + idx + 1) << 8
    mem[0x3C], mem[0x3D] = ptr & 0xFF, ptr >> 8
    d1, d2 = (mem[0x38] | mem[0x39] << 8), (mem[0x3A] | mem[0x3B] << 8)
    for y in range(15, -1, -1):
        mem[d1 + y] = rd(ptr + y) if ptr >= 0xA000 else mem[ptr + y]
        mem[d2 + y] = rd(0xBC13 + y)
    mem[0xD203] = 0
    mem[0xE5] = (mem[0xE5] + 1) & 0xFF
    mem[0xE7] = 0x84
    mem[0xE6] = 2
    mem[GPRIOR] = 0x14
    if g == 0:
        mem[SCORE_ADD + 3] = 2
    elif g == 1:
        mem[SCORE_ADD + 3] = 4
    elif g == 2:
        mem[SCORE_ADD + 3] = 8
    else:
        mem[SCORE_ADD + 2] = 1
        mem[SCORE_ADD + 3] = 6
    M2.model_add_score(mem)


def check_ghost_eaten(n=9000, seed=82):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, by_g = [], [0, 0, 0, 0]
    for _ in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        M2.random_scores(m, rng)
        M3.setup_entities(m, rng)
        m.mem[PAC_X], m.mem[PAC_Y] = rng.randrange(256), rng.choice([rng.randrange(256), 0x64])
        x = rng.randrange(4)
        if rng.random() < 0.3:
            m.mem[ENTITY_Y + x] = m.mem[PAC_Y]
        m.mem[0xE9] = rng.choice([0xFF, 0, 1, 2, 3, 0xFF, 0xFE])
        m.mem[0xE5] = rng.randrange(256)
        mem = bytearray(m.mem)
        m.call(0xA886, x=x)
        model_ghost_eaten(mem, x)
        by_g[min(mem[0xE9], 3)] += 1
        d = diff(m, mem)
        if d:
            bad.append((x, [hex(k) for k in d[:4]]))
    return n, bad, by_g


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_dot_sound(mem):
    if mem[0xF4] == 0:
        return
    x = mem[0xF5]
    if x == 6:
        mem[0xF4] = mem[0xF5] = 0
        mem[0xD201] = 0
        return
    a = rd((0xBCDF if mem[0xF6] else 0xBCD8) + x)
    mem[0xF5] = (x + 1) & 0xFF
    mem[0xD200] = a
    mem[0xD201] = 0xA4


def check_dot_sound(n=6000, seed=83):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        m.mem[0xF4] = rng.choice([0, 1, 1])
        m.mem[0xF5] = rng.choice([0, 1, 2, 3, 4, 5, 6, 7])
        m.mem[0xF6] = rng.randrange(2)
        mem = bytearray(m.mem)
        m.call(0xB0BC)
        model_dot_sound(mem)
        d = diff(m, mem)
        if d:
            bad.append(([hex(k) for k in d[:4]],))
    return n, bad


def model_ghost_eaten_pause(mem):
    mem[0xE6] = (mem[0xE6] - 1) & 0xFF
    if mem[0xE6] == 0:
        mem[0xE6] = 2
        mem[0xE7] = (mem[0xE7] - 3) & 0xFF
        v = mem[0xE7]
        mem[0xD200] = mem[0xD204] = mem[0xD206] = v
        mem[0xD205] = 0xA8
        mem[0xD207] = 0xA8
        mem[0xD201] = 0xA8
        return
    mem[0xE7] = (mem[0xE7] - 4) & 0xFF
    v = mem[0xE7]
    if v != 0x10:
        mem[0xD200] = mem[0xD206] = v
        mem[0xD208] = 0x84
        mem[0xD207] = mem[0xD201] = 0xA4
        return
    for k in range(8):
        mem[0xD200 + k] = 0                                      # ClearPokeyRegisters
    mem[0xD208] = 0
    mem[0xE5] = mem[0xA7] = 0
    mem[0xE8] = 0xFF
    mem[COLOR3] = 0x2A
    mem[GPRIOR] = 0x11
    for x in (3, 2, 1, 0):
        if mem[PCOLR0 + x] == 0xDC:
            mem[PCOLR0 + x] = 0x0C
            mem[0xD01E] = 0x0C                                   # HITCLR gets the colour value left in A
            mem[0xA7] = 0
            model_move_pacman(mem, [])
            mem[0xA8] = (mem[0xA8] + 1) & 0xFF
            run_verified(mem, 0xB33A, 0, [])                     # EatDotAtPacMan (jmp)
            return


def check_ghost_eaten_pause(n=12000, seed=84):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, ended = [], 0
    for _ in range(n):
        m = A.fresh(base)
        for a in range(0x100):
            m.mem[a] = rng.randrange(256)
        m.mem[A.CURRENT_PLAYER] = rng.randrange(2)
        m.mem[0xE6] = rng.choice([1, 2, 2, 3, 1, 5])
        m.mem[0xE7] = rng.choice([0x84, 0x14, 0x18, 0x13, 0x10, 0x17, rng.randrange(256)])
        m.mem[0xAA] = 0
        m.mem[0xA7] = rng.randrange(2)
        m.mem[PAC_X], m.mem[PAC_Y] = M2.lattice_position(rng)
        m.mem[PAC_DIR] = rng.choice([1, 2, 4, 8])
        m.mem[0xAC] = rng.choice([1, 2, 4, 8])
        m.mem[0x80], m.mem[0x81] = rng.randrange(256), 0x08 + rng.randrange(3)
        m.mem[0x82], m.mem[0xA6], m.mem[0xAB] = rng.randrange(4), rng.randrange(4), rng.randrange(4)
        ptr = m.mem[0x80] | m.mem[0x81] << 8
        m.mem[ptr] = rng.choice([0, 1, 2])
        m.mem[0x0278], m.mem[0x0279] = 0x0F, 0x0F
        for g in range(4):
            m.mem[PCOLR0 + g] = rng.choice([0xDC, 0x0C, 0x44, 0xDC])
        m.mem[A.EXTRA_LIFE_FLAG] = m.mem[A.EXTRA_LIFE_FLAG + 1] = 1
        for k in range(6):
            m.mem[SCORE_ADD + k] = 0
        mem = bytearray(m.mem)
        m.call(0xB049)
        model_ghost_eaten_pause(mem)
        ended += mem[0xE8] == 0xFF
        d = diff(m, mem)
        if d:
            bad.append(([hex(k) for k in d[:4]],))
    return n, bad, ended


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def report():
    L = []
    P = L.append
    P("Fourth set of algorithm models against the ROM executed in tools/cpu6502.py (tools/algorithm_models4.py, OV-58); whole memory (zero page, $0200-$9FFF, $D000-$D7FF) compared after every call")
    P("")
    R = []
    n, bad, turns = check_move_pacman()
    P("move_pacman: %d calls (random zero page, every direction and wanted direction, every joystick value of both players, the tunnel ends, frozen and paused, the sub-cell counters 0-3, the chomp phase; JunctionLookup run as real code): %d differences (%d forced steps)" % (n, len(bad), turns))
    R.append(("move_pacman", bad))
    n, bad, fired = check_bonus_update()
    P("bonus_update: %d calls (dots 80 and 160, bonus counts 0 / 1 / 2, the time counters, both players, every Level code): %d differences (%d appearances)" % (n, len(bad), fired))
    R.append(("bonus_update", bad))
    n, bad, g = check_ghost_eaten()
    P("ghost_eaten: %d calls (4 ghosts, Pac-Man above / level with / below, ghosts eaten so far 0-3 and beyond, both players' scores): %d differences (%d / %d / %d / %d for the 1st / 2nd / 3rd / 4th and later)" % (n, len(bad), g[0], g[1], g[2], g[3]))
    R.append(("ghost_eaten", bad))
    n, bad = check_dot_sound()
    P("dot_sound_sweep: %d calls (every step 0-7, both sweep directions): %d differences" % (n, len(bad)))
    R.append(("dot_sound_sweep", bad))
    n, bad, e = check_ghost_eaten_pause()
    P("ghost_eaten_pause: %d calls (the countdown of 2, the sweep from $84 to $14, the end with the colour restore and the Pac-Man step run as real code): %d differences (%d ends)" % (n, len(bad), e))
    R.append(("ghost_eaten_pause", bad))
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
