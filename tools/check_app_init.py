"""Stage 78a: the state initialisation in port form (tools/core_app_init.py) against the ROM routines on the concrete 6502.  For each call the World is loaded from the memory image, the ROM routine runs on the
machine, the port function runs on the World, and the whole zero page (except the declared scratch bytes), the maze and its three copies (the stored maze, the saved mazes), the title screen, the status rows, the
colour shadows, the player-missile pages, the eight positions, the picture buffers and the ordered chip writes are compared.
Usage: python -I tools/check_app_init.py [--write analysis/evidence-app-init-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_sound as CSO  # noqa: E402
import core_app_init as AI  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT
LEVELS = [0, 0, 0, 1, 2, 3, 5, 6, 7, 12, 19, 254, 255]


def setup(m, rng):
    """a random state: every zero-page byte random, then the ones the routines read set to the values that matter (levels around the clamp and the wrap, the player on turn, the clock, the start level), the stored
    maze, the screen maze and the saved mazes random, so that every copy changes something"""
    for a in range(0x100):
        m.mem[a] = rng.randrange(256)
    m.mem[0x2B] = rng.randrange(2)
    for p in range(2):
        m.mem[0x30 + p] = rng.choice(LEVELS + [rng.randrange(256)])
        m.mem[0x2C + p] = rng.choice([0, 1, 2, 3, 4, 255, rng.randrange(256)])
    m.mem[0x1B] = rng.choice(LEVELS + [rng.randrange(256)])
    m.mem[0x14] = rng.choice([0, 0x7F, 0x80, 0xFF, rng.randrange(256)])
    for lo, hi in ((0x0800, 0x0C00), (0x0C00, 0x1000), (0x1000, 0x1800), (0x1C00, 0x2000), (0x2300, 0x2800), (0x2000, 0x2050), (0x0200, 0x0300)):
        for a in range(lo, hi):
            m.mem[a] = rng.randrange(256)
    for a in range(0x0400, 0x0420):
        m.mem[a] = rng.randrange(256)


def diffs(m, w):
    d = CG.world_diff(m, w, None)
    exp = bytearray(m.mem)
    w.store(exp)
    for name, lo, hi in (("maze_orig", 0x0800, 0x0C00), ("saved1", 0x1000, 0x1400), ("saved2", 0x1400, 0x1800), ("title", 0x1C00, 0x2000)):
        if m.mem[lo:hi] != exp[lo:hi]:
            d.append(name)
    if CSO.LOG != w.pokey:
        d.append("pokey %s != %s" % (CSO.LOG[:4], w.pokey[:4]))
    return d


def run(addr, port, n, seed, regs=None):
    """n random states; `regs(rng)` -> the register arguments of the ROM call and of the port ({'x': ..} / {'y': ..})"""
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    C.Machine.wr = CSO._wr
    try:
        for _ in range(n):
            m = A.fresh(base)
            setup(m, rng)
            r = regs(rng) if regs else {}
            w = W.World().load(m.mem)
            del CSO.LOG[:]
            m.call(addr, **r)
            port(w, r)
            d = diffs(m, w)
            if d:
                bad.append((r, d[:4]))
    finally:
        C.Machine.wr = CSO._orig
    return n, bad


ROUTINES = [
    ("init_board", "InitBoard $ADAF (the pages, $80-$FF, the colours, the delays, the start positions, the timers, HITCLR)", 0xADAF, lambda w, r: AI.init_board(w), None),
    ("new_game_init", "NewGameInit $ADF1 (lives 3, the start level, player 2's counters, then the board)", 0xADF1, lambda w, r: AI.new_game_init(w), None),
    ("new_board_init", "NewBoardInit $AE02 (the maze copy, the lives, the timers by level and clock, the counters)", 0xAE02, lambda w, r: AI.new_board_init(w), None),
    ("clear_player_counters", "ClearPlayerCounters $AE1E", 0xAE1E, lambda w, r: AI.clear_player_counters(w, r["x"]), lambda rng: {"x": rng.randrange(2)}),
    ("set_release_timers", "SetReleaseTimers $AE2B (Y 0-255, clamped at 3)", 0xAE2B, lambda w, r: AI.set_release_timers(w, r["y"]), lambda rng: {"y": rng.choice([0, 1, 2, 3, 4, 5, 255, rng.randrange(256)])}),
    ("load_shadow_colors", "LoadShadowColors $B113", 0xB113, lambda w, r: AI.load_shadow_colors(w), None),
    ("copy_0800_to_0c00", "Copy0800To0C00 $B11F", 0xB11F, lambda w, r: AI.copy_0800_to_0c00(w), None),
    ("copy_0c00_to_1000", "Copy0C00To1000 $B13D", 0xB13D, lambda w, r: AI.copy_0c00_to_1000(w), None),
    ("copy_0c00_to_1400", "Copy0C00To1400 $B15B", 0xB15B, lambda w, r: AI.copy_0c00_to_1400(w), None),
]


def report(quick=False):
    n = 400 if quick else 3000
    L = ["The state initialisation in port form (tools/core_app_init.py) against the ROM routines on the concrete 6502 (tools/check_app_init.py, stage 78a): zero page (except the scratch), maze and its three copies, title screen, status rows, shadows, player-missile pages, positions, picture buffers and the ordered chip writes compared", ""]
    rows = []
    for name, what, addr, port, regs in ROUTINES:
        nn, bad = run(addr, port, n, 1 + len(name), regs)
        rows.append((name, bad))
        L.append("%s: %s: %d calls: %d differences" % (name, what, nn, len(bad)))
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
