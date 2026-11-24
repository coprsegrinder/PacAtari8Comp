"""Stage 78b: the board, turn, level-end, intro and label routines in port form (tools/core_app_board.py) against the ROM routines on the concrete 6502.  For each call the World is loaded from the memory image, the ROM
routine runs on the machine, the port function runs on the World, and the whole zero page (only the temporary `$A5` is left out), the maze and its three copies, the title screen, the status rows, the colour shadows, the
player-missile pages, the eight positions, the picture buffers and the ordered chip writes (sound chip, HITCLR, COLPF3) are compared.
Usage: python -I tools/check_app_board.py [--write analysis/evidence-app-board-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import check_app_init as CAI  # noqa: E402
import check_ghost as CG  # noqa: E402
import core_app_board as AB  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT
LOG = []
_orig = C.Machine.wr
TEMPORARY = {0xA5}                                   # JunctionTemp: a temporary of the ROM routines the port does not keep
DRAW_POINTERS = {0x3C, 0x3D, 0x3E, 0x3F}              # SrcPtr and DstPtr: what the ghost drawing of the ROM leaves in them is not modelled (the pictures themselves are compared: tools/check_ghost.py declares the same)


def _wr(m, a, v):
    a &= 0xFFFF
    if 0xD200 <= a <= 0xD20F or a in (0xD01E, 0xD019):
        LOG.append((a, 0 if a == 0xD01E else v & 0xFF))
    _orig(m, a, v)


def diffs(m, w, excluded=frozenset()):
    exp = bytearray(m.mem)
    w.store(exp)
    out = ["%02X:%02X!=%02X" % (a, m.mem[a], exp[a]) for a in range(0x100) if a not in TEMPORARY and a not in excluded and m.mem[a] != exp[a]]
    for name, lo, hi in (("maze", 0x0C00, 0x1000), ("status", 0x2000, 0x2050), ("shadow", 0x0200, 0x0300), ("pm", 0x2300, 0x2800), ("hpos", 0xD000, 0xD008), ("picbuf", 0x0400, 0x0420),
                         ("maze_orig", 0x0800, 0x0C00), ("saved1", 0x1000, 0x1400), ("saved2", 0x1400, 0x1800), ("title", 0x1C00, 0x2000)):
        if m.mem[lo:hi] != exp[lo:hi]:
            out.append(name)
    if LOG != w.pokey:
        out.append("pokey %s != %s" % (LOG[:4], w.pokey[:4]))
    return out


def setup(m, rng):
    """random game states: entities where the maze lets them stand (check_ghost.setup), then the variables of the board logic set to the values that matter"""
    CAI.setup(m, rng)
    CG.setup(m, rng)
    m.mem[0x2B] = rng.randrange(2)
    m.mem[0x1A] = rng.randrange(2)
    for p in range(2):
        m.mem[0x2C + p] = rng.choice([0, 1, 2, 3, 4, 255, rng.randrange(256)])
        m.mem[0x30 + p] = rng.choice([0, 1, 2, 5, 6, 7, 9, 10, 17, 18, 19, 254, 255, rng.randrange(256)])
        m.mem[0x32 + p] = rng.choice([0x0F, 0, rng.randrange(16)])
    for a in range(0x2000, 0x2050):
        m.mem[a] = rng.choice([0, 0x10, 0x11, 0x12, 0x19, rng.randrange(256)])


def pre_turn(m, rng):
    m.mem[0x23] = rng.choice([0, 0, 0, 0, 1, 2, 3, 4, 5, rng.randrange(256)])
    m.mem[0x25] = rng.choice([0, 0, 1, 2, 0x30, rng.randrange(256)])
    m.mem[0x2C] = rng.choice([0, 1, 3, 255])
    m.mem[0x2D] = rng.choice([0, 1, 3, 255])


def pre_level_end(m, rng):
    m.mem[0x27] = rng.choice([0, 1, 2, 3, 4, 5, 255])
    m.mem[0x28] = rng.choice([0, 0, 0, 1, 2, 0x10, 0x40, rng.randrange(256)])
    m.mem[0x29] = rng.choice([0, 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, rng.randrange(256)])


def pre_levels(m, rng):
    m.mem[0x30 + m.mem[0x2B]] = rng.choice(list(range(0, 24)) + [255, rng.randrange(256)])


def pre_label(m, rng):
    m.mem[0x14] = rng.choice([0, 16, 32, 0x10 * rng.randrange(16), 1, 8, rng.randrange(256)])
    m.mem[0xFA] = rng.choice([0, 1, rng.randrange(256)])


def pre_score(m, rng):
    digits = [0x10 + rng.randrange(10) for _ in range(6)]
    for base in (0x2A, 0x47):
        for k in range(6):
            m.mem[0x2000 + base + k] = digits[k] if rng.random() < 0.6 else 0x10 + rng.randrange(10)
    for k in range(6):
        m.mem[0x2039 + k] = digits[k] if rng.random() < 0.7 else 0x10 + rng.randrange(10)


def run(addr, port, n, seed, pre=None, regs=None, excluded=frozenset()):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    C.Machine.wr = _wr
    try:
        for _ in range(n):
            m = A.fresh(base)
            setup(m, rng)
            if pre:
                pre(m, rng)
            r = regs(rng) if regs else {}
            w = W.World().load(m.mem)
            del LOG[:]
            m.call(addr, **r)
            port(w, r)
            d = diffs(m, w, excluded)
            if d:
                bad.append((r, d[:4]))
    finally:
        C.Machine.wr = _orig
    return n, bad


ROUTINES = [
    ("turn_control", "TurnControl $AA2D (the hand-over stages, the maze swap, the next board, the end of the game, the countdown)", 0xAA2D, lambda w, r: AB.turn_control(w), pre_turn, None, DRAW_POINTERS),
    ("level_end_step", "the level-end sequence $AC18 (steps 0-3 and AdvanceLevel)", 0xAC18, lambda w, r: AB.level_end_step(w), pre_level_end, None, DRAW_POINTERS),
    ("advance_level", "AdvanceLevel $AC75", 0xAC75, lambda w, r: AB.advance_level(w), pre_levels, None, DRAW_POINTERS),
    ("draw_level_indicator", "DrawLevelIndicator $AC93 (levels 0-23, 254, 255)", 0xAC93, lambda w, r: AB.draw_level_indicator(w), pre_levels, None, frozenset()),
    ("draw_ready_screen", "DrawReadyScreen $AD0E", 0xAD0E, lambda w, r: AB.draw_ready_screen(w), None, None, DRAW_POINTERS),
    ("clear_ready_text", "ClearReadyText $AD5E", 0xAD5E, lambda w, r: AB.clear_ready_text(w), None, None, frozenset()),
    ("blink_player_label", "BlinkPlayerLabel $AD69 (every clock phase, both players)", 0xAD69, lambda w, r: AB.blink_player_label(w), pre_label, None, frozenset()),
    ("draw_label_2up", "DrawLabel2UP $AD87", 0xAD87, lambda w, r: AB.draw_label_2up(w), None, None, frozenset()),
    ("draw_label_1up", "DrawLabel1UP $AD9F", 0xAD9F, lambda w, r: AB.draw_label_1up(w), None, None, frozenset()),
    ("compare_high_score", "CompareHighScore $AB26 (both scores against the high score)", 0xAB26, lambda w, r: AB.compare_high_score(w, r["x"]), pre_score, lambda rng: {"x": rng.choice([0x2A, 0x47])}, frozenset()),
]


def report(quick=False):
    n = 500 if quick else 3000
    L = ["The board, turn, level-end, intro and label routines in port form (tools/core_app_board.py) against the ROM routines on the concrete 6502 (tools/check_app_board.py, stage 78b): zero page (except $A5), maze and its three copies, title screen, status rows, shadows, player-missile pages, positions, picture buffers and the ordered chip writes compared", ""]
    rows = []
    for name, what, addr, port, pre, regs, excl in ROUTINES:
        nn, bad = run(addr, port, n, 3 + len(name), pre, regs, excl)
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
