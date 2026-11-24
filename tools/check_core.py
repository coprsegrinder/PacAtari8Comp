"""Stage 66: every function of tools/core_ref.py against the ROM routine it stands for, run on the concrete 6502 (tools/cpu6502.py).  A difference means the port reference is wrong.
Usage: python -I tools/check_core.py [--write analysis/evidence-core-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import core_ref as R  # noqa: E402
import core_tables as T  # noqa: E402

ROOT = A.ROOT
PHASE, FLASH, COUNT, F2 = 0xFC, 0xFB, 0xFD, 0xF2


def cells_value(m, player):
    base = M2.SCORE_CELLS[player]
    return int("".join(str(m.mem[base + k] & 15) for k in range(6)))


def set_score(m, player, v):
    base = M2.SCORE_CELLS[player]
    digits = [int(c) for c in "%06d" % v]
    for k, d in enumerate(digits):
        m.mem[base + k] = 0 if (all(x == 0 for x in digits[:k]) and d == 0 and k < 5) else 0x10 | d


def check_pacing(base):
    m = A.fresh(base)
    bad, n = [], 0
    for level in range(256):
        for entity in range(5):
            for cycle in range(4):
                for count in (1, 2, 3):
                    m.mem[A.CURRENT_PLAYER] = 0
                    m.mem[A.LEVEL] = level
                    m.mem[A.MOVE_DELAY_CYCLE + entity] = cycle
                    m.mem[A.MOVE_DELAY_COUNT + entity] = count
                    m.call(0xB590, x=entity)
                    got = (m.a == 0, m.mem[A.MOVE_DELAY_CYCLE + entity], m.mem[A.MOVE_DELAY_COUNT + entity])
                    want = R.move_delay_tick(entity, level, cycle, count)
                    n += 1
                    if got != want:
                        bad.append((level, entity, cycle, count, got, want))
    return n, bad


def check_release(base):
    bad = []
    for level in range(256):
        m = A.fresh(base)
        m.call(0xAE2B, y=level)
        if tuple(m.mem[A.GHOST_TIMER + 1 + i] for i in range(3)) != R.release_timers(level):
            bad.append(level)
    return 256, bad


def pellet_machine(base, level, player=0):
    m = A.fresh(base)
    m.mem[A.CURRENT_PLAYER] = player
    m.mem[A.LEVEL + player] = level
    m.mem[M2.PELLETS + player] = 0x0F
    m.mem[M2.PAC_Y], m.mem[M2.PAC_X] = R.PELLET_SQUARES[0]
    for g in range(4):
        m.mem[A.GHOST_STATE + g] = 0x02
        m.mem[A.ENTITY_DIR + g] = 4
    set_score(m, player, 0)
    m.mem[A.EXTRA_LIFE_FLAG + player] = 1
    return m


def check_fright(base):
    """the solid frames (read from the pellet), the end phase (every phase against every level), and the length of the whole period counted frame by frame"""
    bad, n = [], 0
    for level in range(256):
        for player in (0, 1):
            m = pellet_machine(base, level, player)
            m.call(0xB39F)
            n += 1
            if m.mem[COUNT] != R.fright_frames(level) or m.mem[PHASE] != 1:
                bad.append(("frames", level, player, m.mem[COUNT], R.fright_frames(level)))
    m = A.fresh(base)
    for level in range(256):
        end = R.fright_end_phase(level)
        m.mem[A.CURRENT_PLAYER] = 0
        m.mem[A.LEVEL] = level
        for ph in range(1, 256):
            m.mem[PHASE], m.mem[COUNT], m.mem[FLASH], m.mem[F2] = ph, 0, 5, 5
            m.mem[M2.E4], m.mem[M2.E2], m.mem[M2.E1], m.mem[M2.E3] = 1, 1, 0x90, 3
            for g in range(4):
                m.mem[A.GHOST_STATE + g] = 0x82
            m.call(0xAF54)
            n += 1
            if (m.mem[PHASE] == 0) != (ph == end):
                bad.append(("end", level, ph, end))
    lengths = 0
    for level in [l for l in range(256) if R.fright_end_phase(l) not in (0,)][:]:
        total = R.fright_total_frames(level)
        if total is None or total > 700:
            continue
        m = pellet_machine(base, level)
        m.call(0xB39F)
        frames = 0
        while m.mem[PHASE] != 0 and frames < 1000:
            m.mem[A.RTCLOK2 if hasattr(A, "RTCLOK2") else 0x14] = (m.mem[0x14] + 1) & 255
            m.call(0xAF54)
            frames += 1
        n += 1
        lengths += 1
        if frames != total:
            bad.append(("length", level, frames, total))
    return n, bad, lengths


def check_bonus(base):
    bad, n = [], 0
    for level in range(256):
        for player in (0, 1):
            m = A.fresh(base)
            m.mem[A.CURRENT_PLAYER] = player
            m.mem[A.LEVEL + player] = level
            for a in (0xA1, 0xA2, 0x9F, 0x9D, 0x9E):
                m.mem[a] = 0
            m.mem[0x34 + player] = 0x50
            m.mem[0x43 + player] = 0
            m.call(0xB62E)
            n += 1
            if m.mem[0x0DF3] != R.bonus_glyph(level) or m.mem[0x9F] != 1:
                bad.append(("glyph", level, m.mem[0x0DF3], R.bonus_glyph(level)))
            m = A.fresh(base)
            m.mem[A.CURRENT_PLAYER] = player
            m.mem[A.LEVEL + player] = level
            set_score(m, player, 0)
            m.mem[A.EXTRA_LIFE_FLAG + player] = 1
            m.call(0xA972, until=0xA98C)
            n += 1
            if cells_value(m, player) != R.bonus_points(level):
                bad.append(("points", level, cells_value(m, player), R.bonus_points(level)))
            m = A.fresh(base)
            m.mem[A.CURRENT_PLAYER] = player
            m.mem[A.LEVEL + player] = level
            m.call(0xA93D, until=0xA95A)
            n += 1
            if tuple(m.mem[0x0DF1:0x0DF6]) != tuple(R.bonus_popup_glyphs(level)):
                bad.append(("popup", level))
    return n, bad


def check_score(base, n=6000, seed=66):
    rng = random.Random(seed)
    bad, extras = [], 0
    for i in range(n):
        player = i & 1
        m = A.fresh(base)
        v = rng.choice([rng.randrange(1000), rng.randrange(100000), rng.randrange(1000000), 9990 + rng.randrange(30), 99990 + rng.randrange(20), 999990 + rng.randrange(10)])
        pts = rng.choice([10, 50, 200, 400, 800, 1600, 100, 300, 500, 700, 1000, 2000, 3000, 5000, rng.randrange(100000)])
        flag, lives = rng.choice([0, 0, 1]), rng.randrange(0, 5)
        set_score(m, player, v)
        for k, c in enumerate("%06d" % pts):
            m.mem[A.SCORE_ADD + k] = int(c)
        m.mem[A.CURRENT_PLAYER] = player
        m.mem[A.EXTRA_LIFE_FLAG + player] = flag
        m.mem[A.LIVES + player] = lives
        m.call(0xB423)
        got = (cells_value(m, player), m.mem[A.EXTRA_LIFE_FLAG + player], m.mem[A.LIVES + player])
        want = R.score_add(v, pts, flag, lives)
        extras += want[1] != flag
        if got != want:
            bad.append((v, pts, flag, lives, got, want))
    return n, bad, extras


def check_ghost_points(base):
    bad, n = [], 0
    for e9 in (0xFF, 0, 1, 2, 3, 0xFE):
        for x in range(4):
            m = A.fresh(base)
            M2.randomize(m, random.Random(e9 * 7 + x))
            p = m.mem[A.CURRENT_PLAYER]
            set_score(m, p, 0)
            m.mem[A.EXTRA_LIFE_FLAG + p] = 1
            m.mem[0xE9] = e9
            m.mem[A.ENTITY_Y + x] = 0x64
            m.mem[M2.PAC_X], m.mem[M2.PAC_Y] = 0x50, 0x64
            m.call(0xA886, x=x)
            n += 1
            before = (e9 + 1) & 0xFF                              # the count of ghosts eaten in this period, after this one: g = 0 is the first
            want = R.ghost_points(before)
            if cells_value(m, p) != want:
                bad.append((e9, x, cells_value(m, p), want))
    return n, bad


def check_junction(base):
    m = A.fresh(base)
    rng = random.Random(7)
    ys = list(T.JUNCTION_Y) + [0x00, 0x30, 0x63, 0x65, 0xFF] + [rng.randrange(256) for _ in range(4)]
    bad, n = [], 0
    for y in ys:
        for x in range(256):
            for entity, direction, state in [(4, 4, 0), (0, 1, 0x02), (1, 2, 0x82), (2, 4, 0x02), (3, 8, 0x82), (0, 2, 0x01)]:
                m.mem[A.ENTITY_X + entity], m.mem[A.ENTITY_Y + entity] = x, y
                m.mem[A.ENTITY_DIR + entity] = direction
                m.mem[A.GHOST_STATE + entity] = state if entity < 4 else 0
                m.call(0xB48E, x=entity)
                want = R.junction_exits(entity == 4, x, y, direction, state if entity < 4 else 0)
                n += 1
                if (m.a, bool(m.c)) != want:
                    bad.append((entity, x, y, direction, state, (m.a, m.c), want))
    return n, bad


def check_steer(base, n=30000, seed=52):
    rng = random.Random(seed)
    bad, used = [], [0, 0, 0]
    for _ in range(n):
        ent = rng.randrange(4)
        ey, ex = rng.randrange(256), rng.randrange(256)
        ty = ey if rng.random() < 0.2 else rng.randrange(256)
        tx = ex if rng.random() < 0.2 else rng.randrange(256)
        state = rng.choice([0x01, 0x02, 0x08, 0x10, 0x20, 0x42, 0x81, 0x82, 0x88, 0x90, 0xA0])
        mask = rng.randrange(16)
        rnd = [rng.randrange(256), rng.randrange(256)]
        m = A.fresh(base, list(rnd))
        m.mem[A.ENTITY_Y + ent], m.mem[A.ENTITY_X + ent] = ey, ex
        m.mem[A.TARGET_Y + ent], m.mem[A.TARGET_X + ent] = ty, tx
        m.mem[A.GHOST_STATE + ent] = state
        m.mem[A.SCRATCH2A] = mask
        m.call(0xB999, x=ent)
        it = iter(rnd)
        want = R.steer(ey, ex, ty, tx, state, mask, it)
        left = list(it)
        used[len(rnd) - len(left)] += 1
        if m.mem[A.ENTITY_DIR + ent] != want or len(m.random_reads) != len(rnd) - len(left):
            bad.append((ent, ey, ex, ty, tx, state, mask, rnd))
    return n, bad, used


def check_ghost_rules(base, n=8000, seed=67):
    rng = random.Random(seed)
    bad = {"force_chase": [], "power_pellet": [], "frightened_end": [], "count_dot": []}
    for _ in range(n):
        # ForceChase
        m = A.fresh(base)
        M2.randomize(m, rng)
        M2.random_ghosts(m, rng)
        states = [m.mem[A.GHOST_STATE + g] for g in range(4)]
        x = rng.randrange(4)
        m.call(0xB616, x=x)
        if [m.mem[A.GHOST_STATE + g] for g in range(4)] != R.force_chase(states, x):
            bad["force_chase"].append((states, x))
        # the power pellet
        m = pellet_machine(base, rng.randrange(20), rng.randrange(2))
        M2.random_ghosts(m, rng)
        states = [m.mem[A.GHOST_STATE + g] for g in range(4)]
        dirs = [m.mem[A.ENTITY_DIR + g] for g in range(4)]
        m.call(0xB39F)
        want = R.power_pellet_ghosts(states, dirs)
        if ([m.mem[A.GHOST_STATE + g] for g in range(4)], [m.mem[A.ENTITY_DIR + g] for g in range(4)]) != want:
            bad["power_pellet"].append((states, dirs))
        # the end of the frightened period
        m = A.fresh(base)
        M2.randomize(m, rng)
        M2.random_ghosts(m, rng)
        lv = m.mem[A.LEVEL + m.mem[A.CURRENT_PLAYER]]
        end = R.fright_end_phase(lv)
        if end == 0:
            continue
        states = [m.mem[A.GHOST_STATE + g] for g in range(4)]
        m.mem[PHASE], m.mem[COUNT], m.mem[FLASH], m.mem[F2] = end, 0, 5, 5
        m.mem[M2.E4], m.mem[M2.E2], m.mem[M2.E1], m.mem[M2.E3] = 1, 1, 0x90, 3
        m.call(0xAF54)
        if [m.mem[A.GHOST_STATE + g] for g in range(4)] != R.frightened_end(states):
            bad["frightened_end"].append(states)
        # the dot count
        m = A.fresh(base)
        M2.randomize(m, rng)
        M2.random_scores(m, rng)
        p = m.mem[A.CURRENT_PLAYER]
        ptr = 0x0800 + rng.randrange(920)
        m.mem[0x80], m.mem[0x81] = ptr & 0xFF, ptr >> 8
        m.mem[ptr] = 1
        m.mem[0x82] = m.mem[0xA6] = 0
        m.mem[M2.PAC_X], m.mem[M2.PAC_Y] = 0x10, 0x20
        m.mem[0x84], m.mem[0x83] = 0x11, 0x21
        lo, hi = rng.choice([rng.randrange(256), 3, 255, 4]), rng.choice([0, 0, 1])
        m.mem[M2.DOTS_LO + p], m.mem[M2.DOTS_HI + p] = lo, hi
        m.mem[0x26] = 0
        m.call(0xB33A)
        wl, wh, done = R.count_dot(lo, hi)
        if (m.mem[M2.DOTS_LO + p], m.mem[M2.DOTS_HI + p], m.mem[0x26] == 1) != (wl, wh, done):
            bad["count_dot"].append((lo, hi))
    return n, bad


def report(quick=False):
    base = A.started_machine()
    L, R_ = [], []
    P = L.append
    P("The core algorithms of tools/core_ref.py (port form: plain values, no memory image) against the ROM routines on the concrete 6502 (tools/check_core.py, stage 66)")
    P("")

    def row(name, what, n, bad, extra=""):
        P("%s: %s: %d calls: %d differences%s" % (name, what, n, len(bad), extra))
        R_.append((name, bad))
        for b in bad[:3]:
            P("  %s" % (b,))
    n, bad = check_pacing(base)
    row("pacing", "MoveDelayTick $B590 (every level 0-255 x 5 entities x cycle 0-3 x count 1-3)", n, bad)
    n, bad = check_release(base)
    row("release_timers", "SetReleaseTimers $AE2B (every level)", n, bad)
    n, bad, lengths = check_fright(base)
    row("frightened", "PowerPelletCheck $B39F / FrightenedTick $AF54 (the solid frames of every level and both players, every phase 1-255 against every level's end phase, and the length of %d whole periods counted frame by frame)" % lengths, n, bad)
    n, bad = check_bonus(base)
    row("bonus", "the bonus item $B62E, its pop-up glyphs $A93D and its score $A972 (every level, both players)", n, bad)
    n, bad, extras = check_score(base, 1500 if quick else 6000)
    row("score", "AddToScore $B423 (scores to 999,999 with the wrap, both players, flag, lives)", n, bad, " (%d gave an extra life)" % extras)
    n, bad = check_ghost_points(base)
    row("ghost_points", "GhostEaten $A886 (the points of the 1st to 4th ghost, the count before the first)", n, bad)
    n, bad = check_junction(base)
    row("junction", "JunctionLookup $B48E (every x on 10 lattice rows and 9 other rows, 6 entity cases)", n, bad)
    n, bad, used = check_steer(base, 6000 if quick else 30000)
    row("steer", "SteerToTarget $B999 (random positions, targets, 11 states, every mask; the same RANDOM values used)", n, bad, " (RANDOM read 0 / 1 times in %d / %d calls)" % (used[0], used[1]))
    n, bads = check_ghost_rules(base, 1500 if quick else 8000)
    for k, v in bads.items():
        row(k, {"force_chase": "ForceChase $B616", "power_pellet": "the reversal and frightened bit of the power pellet $B39F", "frightened_end": "the end of the frightened period in FrightenedTick $AF54", "count_dot": "the dot count in EatDotAtPacMan $B33A"}[k], n, v)
    return L, R_


def main():
    L, R_ = report("--quick" in sys.argv)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if any(b for _, b in R_) else 0


if __name__ == "__main__":
    sys.exit(main())
