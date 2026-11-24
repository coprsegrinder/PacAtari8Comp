"""Stage 50: executable models of the algorithms of the Pac-Man ROM, compared with the ROM code run instruction by instruction (tools/cpu6502.py).

Each check writes the algorithm down as a short Python function (a model written from the rules of the chapters and the code, not translated line by line), then runs the real routine of the ROM on many inputs
and compares everything the routine leaves behind (result registers, zero-page variables, screen cells, the number of RANDOM reads).  A mismatch would mean that the model or the reading of the code is wrong.

  start_expansion     Start $A386 up to $A477: the maze, the charset, the nibble tables, the title charset against the independent decoders of tools/decode_streams.py
  add_to_score        AddToScore $B423: BCD addition into the six screen cells with leading-zero blanking, the extra life at 10,000 (both players)
  move_delay_tick     MoveDelayTick $B590: the speed pacing of an entity, every level 0-255, every entity, every cycle position
  release_timers      SetReleaseTimers $AE2B: the house timers of ghosts 1-3, every level (clamp 3)
  junction_lookup     JunctionLookup $B48E: the exits of the lattice point under an entity, the no-reverse mask and the door-square rule
  steer_to_target     SteerToTarget $B999: the wanted directions, the mirrored (frightened) wants, the choice at a junction with RANDOM

Usage: python -I tools/algorithm_models.py [--write analysis/evidence-algorithms-summary.txt]   (about 1 minute)
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpu6502 as C  # noqa: E402
import decode_streams as S  # noqa: E402

ROOT = os.path.dirname(HERE)
with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
    ROM = fh.read()
rd = lambda a: ROM[a - 0xA000]

# zero-page addresses (tools/labels.py, docs/25)
ENTITY_Y, ENTITY_X, ENTITY_DIR = 0x85, 0x8A, 0x8F
TARGET_X, TARGET_Y = 0xC2, 0xC6
GHOST_STATE, WANT_VERT, WANT_HORIZ = 0xCE, 0xD6, 0xDA
SCRATCH2A, CURRENT_PLAYER, LIVES, LEVEL = 0x2A, 0x2B, 0x2C, 0x30
MOVE_DELAY_CYCLE, MOVE_DELAY_COUNT, GHOST_TIMER = 0xB0, 0xB5, 0xCA
SCORE_ADD = 0x94
EXTRA_LIFE_FLAG = 0x2E
JUNCTION_Y, JUNCTION_X = 0xBB83, 0xBB8D
JUNCTION_EXITS = 0x060E
NO_REVERSE = 0x07C6
MOVE_DELAY = 0x07AE


def started_machine():
    """the machine after Start's expansion: the RAM tables ($0600-$07FF), the maze, the charsets"""
    m = C.Machine(ROM)
    m.call(0xA386, until=0xA477, limit=3000000)
    return m


def fresh(base, random_values=None):
    m = C.Machine(ROM, random_values)
    m.mem[:] = base.mem
    m.mem[0xA000:0xC000] = ROM
    m.os_calls = []
    return m


def check_start_expansion():
    m = started_machine()
    a, _ = S.decode_a(0xA1E1)
    nib, _ = S.split_nibbles(0xBE95)
    cs, _ = S.decode_b(0xA003)
    tc, _ = S.decode_b(0xBE13)
    parts = [("maze $0800 (920 bytes)", bytes(m.mem[0x800:0x800 + len(a)]) == bytes(a)),
             ("nibble tables $0600 (512 bytes)", bytes(m.mem[0x600:0x600 + len(nib)]) == bytes(nib)),
             ("charset $3000 (808 bytes)", bytes(m.mem[0x3000:0x3000 + len(cs)]) == cs),
             ("title charset $1808 (160 bytes)", bytes(m.mem[0x1808:0x1808 + len(tc)]) == tc),
             ("title charset tail $18A8 (32 bytes)", bytes(m.mem[0x18A8:0x18A8 + 32]) == bytes(ROM[0xBE75 - 0xA000:0xBE75 - 0xA000 + 32]))]
    steps = m.steps
    return parts, steps


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_add_to_score(cells, add, player, flag, lives):
    """cells: the six screen codes of the player's score (0 = blank, $10 + d = the digit d), add: the six BCD digits to add (100,000 first).  Returns (cells, flag, lives)."""
    new, carry = list(cells), 0
    for y in range(5, -1, -1):
        s = (cells[y] & 0x0F) + carry + add[y]
        carry = 1 if s >= 10 else 0
        d = s % 10
        code = 0x10 | d
        if d == 0:
            if y == 0:
                code = 0
            else:
                code = 0x10 if (cells[y - 1] != 0 or carry) else 0          # the cell to the left holds its OLD value: the loop runs from the units upwards
        new[y] = code
    ten_thousands = new[1]
    if flag == 0 and ten_thousands != 0:
        flag, lives = flag + 1, lives + 1
    return new, flag, lives


def check_add_to_score(n=6000, seed=50):
    base = started_machine()
    rng = random.Random(seed)
    bad = []
    extra = 0
    for i in range(n):
        player = i & 1
        base_addr = 0x202A if player == 0 else 0x2047
        # a score: 0 to 999,999 with the blanking of the game (leading zeros are blank, the units digit shows 0 as $10)
        v = rng.choice([rng.randrange(0, 1000), rng.randrange(0, 100000), rng.randrange(0, 1000000), 9990 + rng.randrange(0, 20), 99990 + rng.randrange(0, 20)])
        digits = [int(c) for c in "%06d" % v]
        cells = []
        for k, d in enumerate(digits):
            lead = all(x == 0 for x in digits[:k])
            cells.append(0 if (lead and d == 0 and k < 5) else 0x10 | d)
        add = [0] * 6
        amount = rng.choice([10, 50, 100, 200, 400, 800, 1600, 300, 500, 700, 1000, 2000, 3000, 5000, rng.randrange(0, 100000)])
        for k, c in enumerate("%06d" % (amount % 1000000)):
            add[k] = int(c)
        flag = rng.choice([0, 0, 1])
        lives = rng.randrange(0, 5)
        m = fresh(base)
        for k in range(6):
            m.mem[base_addr + k] = cells[k]
        for k in range(6):
            m.mem[SCORE_ADD + k] = add[k]
        m.mem[CURRENT_PLAYER] = player
        m.mem[EXTRA_LIFE_FLAG + player] = flag
        m.mem[LIVES + player] = lives
        m.mem[0x2D - player] = 77                       # the other player's lives must not change
        m.call(0xB423)
        got = ([m.mem[base_addr + k] for k in range(6)], m.mem[EXTRA_LIFE_FLAG + player], m.mem[LIVES + player])
        want = model_add_to_score(cells, add, player, flag, lives)
        if got != want or any(m.mem[SCORE_ADD + k] for k in range(6)) or m.mem[0x2D - player] != 77:
            bad.append((v, amount, player, flag, got, want))
        if want[1] != flag:
            extra += 1
    return n, bad, extra


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_move_delay(m, entity, level, cycle, count):
    """returns (A, new cycle, new count): the speed pacing of an entity.  The count falls by one; at 0 the cycle advances (0-3, then 0 again) and the count is reloaded from MoveDelay[base[level clamped to 6] + cycle]."""
    count = (count - 1) & 0xFF
    if count != 0:
        return 0xFF, cycle, count
    cycle = 0 if cycle == 3 else cycle + 1
    lv = min(level, 6)
    base = rd(0xBDB9 + lv) if entity == 4 else rd(0xBDC0 + lv)
    return 0, cycle, m.mem[MOVE_DELAY + base + cycle]


def check_move_delay_tick():
    base = started_machine()
    bad, n = [], 0
    m = fresh(base)
    for level in range(256):
        for entity in range(5):
            for cycle in range(4):
                for count in (1, 2):
                    m.mem[CURRENT_PLAYER] = 0
                    m.mem[LEVEL] = level
                    m.mem[MOVE_DELAY_CYCLE + entity] = cycle
                    m.mem[MOVE_DELAY_COUNT + entity] = count
                    m.call(0xB590, x=entity)
                    got = (m.a, m.mem[MOVE_DELAY_CYCLE + entity], m.mem[MOVE_DELAY_COUNT + entity])
                    want = model_move_delay(m, entity, level, cycle, count)
                    n += 1
                    if got != want:
                        bad.append((level, entity, cycle, count, got, want))
    # the second player's level is read through CurrentPlayer
    m.mem[CURRENT_PLAYER] = 1
    m.mem[LEVEL + 1] = 9
    m.mem[LEVEL] = 0
    m.mem[MOVE_DELAY_CYCLE + 4] = 3
    m.mem[MOVE_DELAY_COUNT + 4] = 1
    m.call(0xB590, x=4)
    n += 1
    if (m.a, m.mem[MOVE_DELAY_CYCLE + 4], m.mem[MOVE_DELAY_COUNT + 4]) != model_move_delay(m, 4, 9, 3, 1):
        bad.append(("player 2", 9))
    return n, bad


def check_release_timers():
    base = started_machine()
    bad, n = [], 0
    for level in range(256):
        m = fresh(base)
        m.call(0xAE2B, y=level)
        got = [m.mem[GHOST_TIMER + 1 + i] for i in range(3)]
        y = min(level, 3)
        want = [rd(0xBBF2 + y + 2), rd(0xBBF2 + y + 1), rd(0xBBF2 + y)]            # $CB gets T[y+2], $CC T[y+1], $CD T[y]
        n += 1
        if got != want or m.mem[GHOST_TIMER] != 0:
            bad.append((level, got, want))
    return n, bad


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_junction(m, entity, x, y, direction, state):
    rows = [rd(JUNCTION_Y + i) for i in range(10)]
    cols = [rd(JUNCTION_X + i) for i in range(10)]
    if y in rows:
        r = rows.index(y)
        if x in cols:
            mask, carry = m.mem[JUNCTION_EXITS + 10 * r + cols.index(x)], 1
        else:
            mask, carry = 0x0C, 0
    else:
        # the row loop found nothing: the code scans the columns (B4A4); a match -> $03 (vertical corridor); no match -> falls into B4AC (the column scan again, no match) -> $0C
        mask, carry = (0x03, 0) if x in cols else (0x0C, 0)
    if entity != 4:
        mask &= m.mem[NO_REVERSE + direction]
        if y == 0x64 and x in (0x76, 0x82):
            mask = 1 if (state & 0x80) else (mask & 0x0E or 1)
    return mask, carry


def check_junction_lookup():
    base = started_machine()
    m = fresh(base)
    rng = random.Random(51)
    rows = [rd(JUNCTION_Y + i) for i in range(10)]
    ys = rows + [0x00, 0x30, 0x63, 0x65, 0xFF] + [rng.randrange(256) for _ in range(4)]
    bad, n = [], 0
    for y in ys:
        for x in range(256):
            for entity, direction, state in [(4, 4, 0), (0, 1, 0x02), (1, 2, 0x82), (2, 4, 0x02), (3, 8, 0x82), (0, 2, 0x01)]:
                m.mem[ENTITY_X + entity] = x
                m.mem[ENTITY_Y + entity] = y
                m.mem[ENTITY_DIR + entity] = direction
                m.mem[GHOST_STATE + entity] = state if entity < 4 else 0
                m.call(0xB48E, x=entity)
                want = model_junction(m, entity, x, y, direction, state)
                n += 1
                if (m.a, m.c) != want or m.mem[SCRATCH2A] != want[0]:
                    bad.append((entity, x, y, direction, state, (m.a, m.c), want))
    return n, bad


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_steer(ey, ex, ty, tx, state, mask, rnd):
    """returns (direction, wantvert, wanthoriz, number of RANDOM values used)"""
    fr = bool(state & 0x80)
    if ey == ty:
        wv = 0
    elif ey > ty:
        wv = 2 if fr else 1
    else:
        wv = 1 if fr else 2
    if ex == tx:
        wh = 0
    elif ex > tx:
        wh = 8 if fr else 4
    else:
        wh = 4 if fr else 8
    used = 0
    if wv and (mask & wv):
        if wh and (mask & wh):
            r = rnd[used]
            used += 1
            d = wh if (r & 0x80) else wv
        else:
            d = wv
    elif wh and (mask & wh):
        d = wh
    else:
        r = rnd[used] & mask
        used += 1
        if r == 0:
            r = mask
        d = 1 if r & 1 else 2 if r & 2 else 4 if r & 4 else 8 if r & 8 else 8
        if r == 0:
            d = 8
    return d, wv, wh, used


def check_steer_to_target(n=30000, seed=52):
    base = started_machine()
    rng = random.Random(seed)
    bad = []
    reads = [0, 0, 0]
    for i in range(n):
        ent = rng.randrange(4)
        ey, ex = rng.randrange(256), rng.randrange(256)
        ty = ey if rng.random() < 0.2 else rng.randrange(256)
        tx = ex if rng.random() < 0.2 else rng.randrange(256)
        state = rng.choice([0x01, 0x02, 0x08, 0x10, 0x20, 0x42, 0x81, 0x82, 0x88, 0x90, 0xA0])
        mask = rng.randrange(16)
        rnd = [rng.randrange(256), rng.randrange(256)]
        m = fresh(base, list(rnd))
        m.mem[ENTITY_Y + ent], m.mem[ENTITY_X + ent] = ey, ex
        m.mem[TARGET_Y + ent], m.mem[TARGET_X + ent] = ty, tx
        m.mem[GHOST_STATE + ent] = state
        m.mem[SCRATCH2A] = mask
        m.call(0xB999, x=ent)
        want = model_steer(ey, ex, ty, tx, state, mask, rnd)
        got = (m.mem[ENTITY_DIR + ent], m.mem[WANT_VERT + ent], m.mem[WANT_HORIZ + ent], len(m.random_reads))
        reads[want[3]] += 1
        if got != want or m.a != want[0]:
            bad.append((ent, ey, ex, ty, tx, state, mask, rnd, got, want))
    return n, bad, reads


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def report():
    L = []
    P = L.append
    parts, steps = check_start_expansion()
    P("Algorithm models against the ROM executed in tools/cpu6502.py (tools/algorithm_models.py, tests/test_algorithms.py)")
    P("")
    P("start_expansion: Start $A386 run from the entry to $A477 (%d instructions): %s" % (steps, "; ".join("%s %s" % (n, "equal" if ok else "DIFFERENT") for n, ok in parts)))
    n, bad, extra = check_add_to_score()
    P("add_to_score: %d additions (both players, scores 0-999,999, amounts 10 ... 99,999, extra-life flag 0/1) compared on the six cells, the flag, the lives, the other player's lives and the cleared ScoreAdd: %d differences (%d of them gave an extra life)" % (n, len(bad), extra))
    n2, bad2 = check_move_delay_tick()
    P("move_delay_tick: %d calls (levels 0-255 x entities 0-4 x cycle 0-3 x count 1-2, and player 2's level): %d differences" % (n2, len(bad2)))
    n3, bad3 = check_release_timers()
    P("release_timers: %d calls (every level 0-255, Y clamped to 3): %d differences" % (n3, len(bad3)))
    n4, bad4 = check_junction_lookup()
    P("junction_lookup: %d calls (every x on 10 lattice rows and 9 other rows, Pac-Man and ghosts in 4 directions, frightened and not): %d differences" % (n4, len(bad4)))
    n5, bad5, reads = check_steer_to_target()
    P("steer_to_target: %d calls (random positions, targets with equal axes 20 %%, 11 states, every mask 0-15, random POKEY values): %d differences; RANDOM read 0 / 1 times in %d / %d calls" % (n5, len(bad5), reads[0], reads[1]))
    for name, b in (("add_to_score", bad), ("move_delay_tick", bad2), ("release_timers", bad3), ("junction_lookup", bad4), ("steer_to_target", bad5)):
        for t in b[:3]:
            P("  %s: %s" % (name, t))
    return L, (parts, bad, bad2, bad3, bad4, bad5)


def main():
    L, res = report()
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
